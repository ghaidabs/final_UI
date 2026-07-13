import asyncio
import logging
from typing import Optional
from agent.session import SessionState, UserContext
from agent.nlu import extract_intent_with_context
from agent.dispatcher import dispatch, resume_awaiting_field
from agent.stt import STTSession, TranscriptResult, annotate_low_confidence
from agent.tts import TTSSession
from api.mock_saas_client import MockSaasClient
from mock.db import get_user_by_id, get_company_by_id
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MOCK_USERS = {
    "1": 1,  # admin@acme.tn   / ADMIN / ACME
    "2": 2,  # admin@nova.tn   / ADMIN / NOVA
    "3": 3,  # owner@platform.tn / OWNER / ACME
}

_tts_session: Optional[TTSSession] = None
_tts_enabled = True
_tts_init_failed = False


def _get_tts_session() -> Optional[TTSSession]:
    global _tts_session, _tts_init_failed
    if _tts_init_failed:
        return None
    if _tts_session is None:
        try:
            _tts_session = TTSSession()
        except RuntimeError as exc:
            print(f"[tts] disabled: {exc}")
            _tts_init_failed = True
            return None
    return _tts_session


def _toggle_tts(enabled: bool) -> None:
    global _tts_enabled
    _tts_enabled = enabled
    print(f"[tts] {'enabled' if enabled else 'disabled'}")

def play_pcm(result: SynthesisResult) -> None:
    if not result.audio_bytes:
        return
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        raise SystemExit(
            "sounddevice and numpy are required to play audio. Install with: pip install sounddevice numpy"
        )

    audio_array = np.frombuffer(result.audio_bytes, dtype=np.int16)
    sd.play(audio_array, samplerate=result.sample_rate, blocking=True)

def _speak(text: str, language: str) -> None:
    if not _tts_enabled or not text or not text.strip():
        return
    session = _get_tts_session()
    if session is None:
        return
    try:
        result = session.synthesize(text, language=language)
        play_pcm(result)
    except Exception as exc:
        logger.exception("TTS playback failed")
        print(f"[tts] error: {exc}")


def _build_session(user_id: int) -> SessionState:
    user_row = get_user_by_id(user_id)
    if not user_row:
        raise ValueError(f"No mock user with id {user_id}")
    company = get_company_by_id(user_row["company_id"])
    if not company:
        raise ValueError(f"No mock company with id {user_row['company_id']}")

    ctx = UserContext(
        user_id=user_row["id"],
        company_id=user_row["company_id"],
        role=user_row["role"],
        company_slug=company["slug"],
    )
    return SessionState(user=ctx)


def _select_user() -> int:
    print("Select a mock user to test as:")
    print("  1) admin@acme.tn     (ADMIN, ACME)")
    print("  2) admin@nova.tn     (ADMIN, NOVA)")
    print("  3) owner@platform.tn (OWNER, ACME)")
    choice = input("> ").strip()
    return MOCK_USERS.get(choice, 1)


def _print_response(resp) -> None:
    print(f"\n🗣  {resp.spoken_text}")
    if resp.clarification_question:
        print(f"   [clarification needed: {resp.clarification_question}]")
    if resp.requires_confirmation:
        print("   [awaiting confirm/cancel]")
    if resp.error:
        print(f"   [error: {resp.error}]")
    if resp.display_data is not None:
        print(f"   [display_data: {resp.display_data}]")
    print()


async def _run_pipeline(transcript: str, session: SessionState, saas: MockSaasClient, language: str = "fr") -> None:
    if session.awaiting_field:
        resumed = await resume_awaiting_field(transcript, session, saas, language)
        if resumed is not None:
            _print_response(resumed)
            _speak(resumed.spoken_text, language)
            return

    intent = extract_intent_with_context(transcript, session, language=language)
    print(f"   [intent: {intent.intent}  confidence={intent.confidence}]")

    resp = await dispatch(intent, saas, session)
    _print_response(resp)
    _speak(resp.spoken_text, language)


async def _voice_turn(session: SessionState, saas: MockSaasClient) -> None:
    try:
        import sounddevice as sd
    except ImportError:
        print("[voice] sounddevice not installed. Run: pip install sounddevice numpy")
        return

    done = asyncio.Event()

    async def on_transcript(result: TranscriptResult) -> None:
        marked_text = annotate_low_confidence(result)

        print(f'\n🎧 transcript: "{result.transcript}"')
        print(f"   confidence: {result.confidence:.3f}" + (" (LOW)" if result.low_confidence else ""))
        if marked_text != result.transcript:
            print(f"   annotated:  \"{marked_text}\"")

        detected_lang = result.language
        await _run_pipeline(marked_text, session, saas, language=detected_lang)
        done.set()

    async def on_error(exc: Exception) -> None:
        print(f"[voice] STT error: {exc}")
        done.set()

    async def on_speaking_state_change(speaking: bool) -> None:
        print("🎤 listening..." if speaking else "🛑 processing...")

    stt = STTSession(
        on_transcript=on_transcript,
        on_error=on_error,
        on_speaking_state_change=on_speaking_state_change,
    )
    await stt.start()

    loop = asyncio.get_event_loop()
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

    def _callback(indata, frames, time_info, status):
        if status:
            logger.debug("sounddevice status: %s", status)
        loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))

    stream = sd.RawInputStream(
        samplerate=16000, channels=1, dtype="int16", blocksize=1024, callback=_callback,
    )

    print("[voice] speak now — say one full request, then pause.")
    with stream:
        try:
            while not done.is_set():
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                await stt.send_audio(chunk)
        except KeyboardInterrupt:
            pass
        finally:
            await stt.finish()


async def repl() -> None:
    user_id = _select_user()
    session = _build_session(user_id)
    saas = MockSaasClient(company_id=session.user.company_id, user_id=session.user.user_id, company_slug=session.user.company_slug)

    print(
        f"\nSession started — user_id={session.user.user_id} "
        f"company={session.user.company_slug} role={session.user.role}"
    )
    print("Type a transcript, or type 'voice' to speak instead.")
    print("Type 'switch' to change user, 'exit' to quit.\n")

    while True:
        try:
            transcript = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return

        if not transcript:
            continue
        if transcript.lower() in ("exit", "quit"):
            print("bye")
            return
        if transcript.lower() == "switch":
            user_id = _select_user()
            session = _build_session(user_id)
            saas = MockSaasClient(company_id=session.user.company_id, user_id=session.user.user_id, company_slug=session.user.company_slug)
            print(f"Switched to user_id={session.user.user_id} company={session.user.company_slug}\n")
            continue
        if transcript.lower() == "voice":
            await _voice_turn(session, saas)
            continue

        await _run_pipeline(transcript, session, saas)


if __name__ == "__main__":
    asyncio.run(repl())