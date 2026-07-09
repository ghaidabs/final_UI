from __future__ import annotations
import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional
from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from agent.validator import redact_pii
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")


DEFAULT_STT_CONFIG = {
    "model": "nova-3",
    "language": "multi",
    "smart_format": True,
    "punctuate": True,
    "numerals": True,
    "interim_results": True,   
    "utterance_end_ms": "1000",
    "vad_events": True,
    "endpointing": 500,
    "encoding": "linear16",
    "sample_rate": 16000,
    "channels": 1,
}

WORD_CONFIDENCE_FLOOR = 0.55
TRANSCRIPT_CONFIDENCE_FLOOR = 0.6



@dataclass
class WordResult:
    word: str
    punctuated_word: str
    start: float
    end: float
    confidence: float


@dataclass
class TranscriptResult:
    transcript: str
    confidence: float                
    words: list[WordResult] = field(default_factory=list)
    language: Optional[str] = None

    @property
    def low_confidence(self) -> bool:
        return self.confidence < TRANSCRIPT_CONFIDENCE_FLOOR

    def low_confidence_words(self) -> list[WordResult]:
        return [w for w in self.words if w.confidence < WORD_CONFIDENCE_FLOOR]


TranscriptCallback = Callable[[TranscriptResult], Awaitable[None]]
ErrorCallback = Callable[[Exception], Awaitable[None]]
SpeakingStateCallback = Callable[[bool], Awaitable[None]]  # True = started, False = ended


class STTSession:
    def __init__(
        self,
        on_transcript: TranscriptCallback,
        on_error: Optional[ErrorCallback] = None,
        on_speaking_state_change: Optional[SpeakingStateCallback] = None,
        config: Optional[dict] = None,
        api_key: Optional[str] = None,
    ):
        key = api_key or DEEPGRAM_API_KEY
        if not key:
            raise RuntimeError(
                "DEEPGRAM_API_KEY is not set. Add it to .env (see .env.example)."
            )

        self._config = {**DEFAULT_STT_CONFIG, **(config or {})}
        self._on_transcript = on_transcript
        self._on_error = on_error
        self._on_speaking_state_change = on_speaking_state_change
        self._client = AsyncDeepgramClient(api_key=key)
        self._connect_ctx = None
        self._connection = None
        self._listen_task: Optional[asyncio.Task] = None
        self._started = False

        self._segment_buffer: list[str] = []
        self._word_buffer: list[WordResult] = []
        self._last_language: Optional[str] = None
        self._speech_final_seen_for_current_utterance = False
        self._is_speaking = False  

    async def start(self) -> None:
        if self._started:
            return

        self._connect_ctx = self._client.listen.v1.connect(**self._config)
        self._connection = await self._connect_ctx.__aenter__()

        self._connection.on(EventType.MESSAGE, self._handle_message)
        self._connection.on(EventType.ERROR, self._handle_error)
        self._connection.on(EventType.CLOSE, self._handle_close)
        self._connection.on(EventType.OPEN, self._handle_open)

        self._listen_task = asyncio.create_task(self._connection.start_listening())

        self._started = True
        logger.info(
            "Deepgram STT session started (model=%s, language=%s)",
            self._config["model"], self._config["language"],
        )

    async def send_audio(self, chunk: bytes) -> None:
        if not self._started or self._connection is None:
            raise RuntimeError("STTSession.start() must be awaited before sending audio.")
        await self._connection.send_media(chunk)

    async def finish(self) -> None:
        if self._connection is not None and self._started:
            try:
                await self._connection.send_close_stream()
            except Exception:
                pass
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._connect_ctx is not None:
            await self._connect_ctx.__aexit__(None, None, None)
        self._started = False


    def _handle_open(self, *args, **kwargs) -> None:
        logger.debug("Deepgram: connection open")

    def _handle_message(self, message) -> None:
        msg_type = getattr(message, "type", None)

        if msg_type == "Results":
            asyncio.create_task(self._on_results(message))
        elif msg_type == "UtteranceEnd":
            asyncio.create_task(self._on_utterance_end())
        elif msg_type == "SpeechStarted":
            logger.debug("Deepgram: speech started")
            self._set_speaking(True)

    def _set_speaking(self, speaking: bool) -> None:
        if speaking == self._is_speaking:
            return
        self._is_speaking = speaking
        if self._on_speaking_state_change:
            asyncio.create_task(self._on_speaking_state_change(speaking))

    async def _on_results(self, result) -> None:
        try:
            alt = result.channel.alternatives[0]
            transcript_text = alt.transcript

            if not result.is_final:
                return

            if transcript_text:
                self._segment_buffer.append(transcript_text)
                self._word_buffer.extend(
                    WordResult(
                        word=w.word,
                        punctuated_word=getattr(w, "punctuated_word", w.word),
                        start=w.start,
                        end=w.end,
                        confidence=w.confidence,
                    )
                    for w in (alt.words or [])
                )
                if getattr(alt, "languages", None):
                    self._last_language = alt.languages[0]

            if result.speech_final:
                self._speech_final_seen_for_current_utterance = True
                await self._flush_utterance()

        except Exception as exc:
            logger.exception("Error handling Deepgram Results message")
            if self._on_error:
                await self._on_error(exc)

    async def _on_utterance_end(self) -> None:
        if self._speech_final_seen_for_current_utterance:
            return
        if self._segment_buffer:
            await self._flush_utterance()

    async def _flush_utterance(self) -> None:
        full_transcript = " ".join(s for s in self._segment_buffer if s).strip()
        words = list(self._word_buffer)

        self._segment_buffer = []
        self._word_buffer = []
        self._speech_final_seen_for_current_utterance = False

        self._set_speaking(False)

        if not full_transcript:
            return

        confidences = [w.confidence for w in words]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        parsed = TranscriptResult(
            transcript=redact_pii(full_transcript),
            confidence=overall_confidence,
            words=words,
            language=self._last_language or self._config.get("language"),
        )

        await self._on_transcript(parsed)

    def _handle_error(self, error) -> None:
        logger.error("Deepgram STT error: %s", error)
        if self._on_error:
            asyncio.create_task(
                self._on_error(error if isinstance(error, Exception) else RuntimeError(str(error)))
            )

    def _handle_close(self, *args, **kwargs) -> None:
        logger.info("Deepgram STT connection closed")
        self._started = False
        self._set_speaking(False)



_RESET, _BOLD, _DIM = "\033[0m", "\033[1m", "\033[2m"
_GREEN, _YELLOW, _RED, _CYAN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"
_WORDS_PER_LINE = 6


def _confidence_color(value: float, floor: float) -> str:
    if value >= floor:
        return _GREEN
    if value >= floor - 0.15:
        return _YELLOW
    return _RED


async def _print_transcript(result: TranscriptResult) -> None:
    overall_color = _confidence_color(result.confidence, TRANSCRIPT_CONFIDENCE_FLOOR)
    status = "OK" if not result.low_confidence else "LOW CONFIDENCE"

    print(f'{_BOLD}Transcript{_RESET} : "{result.transcript}"')
    print(
        f"{_BOLD}Confidence{_RESET} : {overall_color}{result.confidence:.3f}{_RESET} "
        f"({status}, threshold {TRANSCRIPT_CONFIDENCE_FLOOR:.2f})"
    )

    if result.words:
        print(f"{_DIM}Per-word confidence:{_RESET}")
        line = []
        for w in result.words:
            color = _confidence_color(w.confidence, WORD_CONFIDENCE_FLOOR)
            line.append(f"{color}{w.word}={w.confidence:.2f}{_RESET}")
            if len(line) == _WORDS_PER_LINE:
                print("  " + "  ".join(line))
                line = []
        if line:
            print("  " + "  ".join(line))

        low_words = result.low_confidence_words()
        if low_words:
            names = ", ".join(w.word for w in low_words)
            print(f"{_YELLOW}⚠ Low-confidence words (<{WORD_CONFIDENCE_FLOOR}):{_RESET} {names}")

    print(f"{_DIM}{'─' * 60}{_RESET}\n")


async def _print_error(error: Exception) -> None:
    print(f"{_RED}[error] {error}{_RESET}\n")


async def _on_speaking_state_change(speaking: bool) -> None:
    print(f"\n{_CYAN}🎤 start speaking{_RESET}" if speaking else f"{_CYAN}🛑 end speaking{_RESET}")


async def _stream_microphone(language: str) -> None:
    try:
        import sounddevice as sd
    except ImportError:
        raise SystemExit(
            "sounddevice is required to run this test. Install with: pip install sounddevice numpy"
        )

    session = STTSession(
        on_transcript=_print_transcript,
        on_error=_print_error,
        on_speaking_state_change=_on_speaking_state_change,
        config={"sample_rate": 16000, "channels": 1, "language": language},
    )
    await session.start()

    loop = asyncio.get_event_loop()
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

    def _callback(indata, frames, time_info, status):
        if status:
            logger.debug("sounddevice status: %s", status)
        loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))

    stream = sd.RawInputStream(
        samplerate=16000, channels=1, dtype="int16", blocksize=1024, callback=_callback,
    )

    with stream:
        try:
            while True:
                chunk = await audio_queue.get()
                await session.send_audio(chunk)
        except KeyboardInterrupt:
            pass
        finally:
            await session.finish()


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Deepgram live STT mic test")
    parser.add_argument("--language", default="multi")
    
    args = parser.parse_args()

    asyncio.run(_stream_microphone(args.language))


if __name__ == "__main__":
    _main()