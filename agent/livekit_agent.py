from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from agent.speech.stt import STTSession, TranscriptResult, LiveKitAudioSource, annotate_low_confidence
from agent.speech.tts import TTSSession
from agent.core.pipeline import run_turn
from agent.core.user_context import build_session_for_user
from agent.core.session import SessionState
from agent.core.dispatcher import dispatch, build_button_intent
from agent.core.warmup import start_warmup_thread
from api.mock_saas_client import MockSaasClient

load_dotenv()

logger = logging.getLogger("invoice-agent.livekit")

TTS_SAMPLE_RATE = 24_000     
TTS_FRAME_MS = 20
TTS_BYTES_PER_FRAME = int(TTS_SAMPLE_RATE * TTS_FRAME_MS / 1000) * 2  # 16-bit mono

start_warmup_thread()

class ParticipantVoiceHandler:
    def __init__(self, ctx: JobContext, participant: rtc.RemoteParticipant, session: SessionState):
        self._ctx = ctx
        self._participant = participant
        self._session = session
        self._saas = MockSaasClient(
            company_id=session.user.company_id,
            user_id=session.user.user_id,
            company_slug=session.user.company_slug,
        )
        self._stt: Optional[STTSession] = None
        self._audio_bridge: Optional[LiveKitAudioSource] = None
        self._tts = TTSSession()
        self._out_source = rtc.AudioSource(sample_rate=TTS_SAMPLE_RATE, num_channels=1)
        self._out_track = rtc.LocalAudioTrack.create_audio_track("assistant-voice", self._out_source)
        self._published = False
        self._reply_lock = asyncio.Lock()
        self._agent_speaking = False
        self._barge_in_requested = False

    async def start(self, track: rtc.Track) -> None:
        if not self._published:
            await self._ctx.room.local_participant.publish_track(
                self._out_track,
                rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
            )
            self._published = True

        self._stt = STTSession(
            on_transcript=self._on_transcript,
            on_error=self._on_stt_error,
            on_speaking_state_change=self._on_vad_state,  
        )
        await self._stt.start()

        audio_stream = rtc.AudioStream(track, sample_rate=16000, num_channels=1)
        self._audio_bridge = LiveKitAudioSource(audio_stream, self._stt)
        self._audio_bridge.start()

    async def stop(self) -> None:
        if self._audio_bridge:
            await self._audio_bridge.stop()
        if self._stt:
            await self._stt.finish()

    async def _speak(self, text: str, language: str) -> None:
        if not text or not text.strip():
            return
        self._agent_speaking = True
        self._barge_in_requested = False
        await self._publish_event({"type": "agent_speaking", "speaking": True})
        try:
            result = await asyncio.to_thread(self._tts.synthesize, text, language=language)
            pcm = result.audio_bytes
            for offset in range(0, len(pcm), TTS_BYTES_PER_FRAME):
                if self._barge_in_requested:
                    logger.info("Barge-in: stopping TTS playback")
                    break
                chunk = pcm[offset:offset + TTS_BYTES_PER_FRAME]
                if len(chunk) < TTS_BYTES_PER_FRAME:
                    chunk = chunk + b"\x00" * (TTS_BYTES_PER_FRAME - len(chunk))
                frame = rtc.AudioFrame(
                    data=chunk, sample_rate=TTS_SAMPLE_RATE,
                    num_channels=1, samples_per_channel=len(chunk) // 2,
                )
                await self._out_source.capture_frame(frame)
        except Exception:
            logger.exception("TTS synthesis failed")
        finally:
            self._agent_speaking = False                                         
            await self._publish_event({"type": "agent_speaking", "speaking": False})

    async def handle_client_action(self, payload: dict) -> None:
        # Handle a button-triggered confirm/cancel/barge-in from the frontend
        
        action = (payload.get("action") or "").strip().lower()

        if action == "barge_in":
            self._barge_in_requested = True
            logger.info("Barge-in requested by %s", self._participant.identity)
            return

        if action not in ("confirm", "cancel"):
            logger.warning("Ignoring unknown client action: %r", payload)
            return

        language = payload.get("language") or "fr"
        
        try:
            intent = build_button_intent(action, language=language)
        except ValueError:
            logger.warning("Ignoring unknown client action: %r", payload)
            return
        async with self._reply_lock:
            resp = await dispatch(intent, self._saas, self._session)
            await self._publish_text(resp, language)
            await self._speak(resp.spoken_text, language)

    async def _publish_text(self, resp, language: str) -> None:
        payload = {
            "type": "response",
            "display_text": resp.display_text or resp.spoken_text,
            "success": resp.success,
            "requires_confirmation": resp.requires_confirmation,
            "clarification_question": resp.clarification_question,
            "error": resp.error,
            "display_data": resp.display_data,
            "draft_payload": resp.draft_payload,
            "turn_state": resp.turn_state,
            "language": language,
        }
        await self._publish_event(payload)

    async def _publish_event(self, payload: dict) -> None:
        try:
            await self._ctx.room.local_participant.publish_data(
                json.dumps(payload, default=str).encode("utf-8"),
                reliable=True,
            )
        except Exception:
            logger.exception("Failed to publish event: %s", payload.get("type"))

    async def _run_and_publish(self, text: str, language: str, echo_transcript: bool) -> None:
        async with self._reply_lock:
            if echo_transcript:
                await self._publish_event({"type": "transcript_final", "text": text})
            await self._publish_event({"type": "processing", "active": True})
            resp = await run_turn(text, self._session, self._saas, language=language)
            await self._publish_event({"type": "processing", "active": False})
            await self._publish_text(resp, language)
            await self._speak(resp.spoken_text, language)

    async def handle_text_input(self, text: str, language: str) -> None:
        if self._agent_speaking:
            return
        await self._run_and_publish(text, language, echo_transcript=False)

    async def _on_transcript(self, result: TranscriptResult) -> None:
        if self._agent_speaking:
            logger.debug("Dropping transcript during agent turn: %r", result.transcript)
            return
        marked = annotate_low_confidence(result)
        await self._run_and_publish(marked, result.language or "fr", echo_transcript=True)

    async def _on_stt_error(self, exc: Exception) -> None:
        logger.exception("STT error for %s: %s", self._participant.identity, exc)    

    async def _on_vad_state(self, speaking: bool) -> None:
        await self._publish_event({"type": "vad_state", "speaking": speaking})


def _parse_user_id(participant: rtc.RemoteParticipant) -> int:
    if participant.metadata:
        try:
            data = json.loads(participant.metadata)
            return int(data["user_id"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
    if participant.identity.startswith("user-"):
        return int(participant.identity.removeprefix("user-"))
    raise ValueError(f"Cannot resolve app user_id for participant {participant.identity!r}")


async def entrypoint(ctx: JobContext) -> None:
    handlers: dict[str, ParticipantVoiceHandler] = {}

    async def _handle_new_audio_track(track: rtc.Track, participant: rtc.RemoteParticipant) -> None:
        try:
            user_id = _parse_user_id(participant)
            session = build_session_for_user(user_id)
        except Exception:
            logger.exception("Rejecting participant %s: could not resolve app user", participant.identity)
            return

        handler = ParticipantVoiceHandler(ctx, participant, session)
        handlers[participant.identity] = handler
        await handler.start(track)
        logger.info("Voice session ready for %s (company=%s role=%s)",
                    participant.identity, session.user.company_slug, session.user.role)

    def _on_data_received(data: rtc.DataPacket) -> None:
        participant = data.participant
        if participant is None:
            return
        handler = handlers.get(participant.identity)
        if handler is None:
            return
        try:
            payload = json.loads(data.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Malformed data packet from %s", participant.identity)
            return

        msg_type = payload.get("type")
        if msg_type == "user_action":
            asyncio.create_task(handler.handle_client_action(payload))
        elif msg_type == "text_input":
            text = (payload.get("text") or "").strip()
            if text:
                asyncio.create_task(handler.handle_text_input(text, payload.get("language") or "fr"))

    @ctx.room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        _on_data_received(data)

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(_handle_new_audio_track(track, participant))

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        handler = handlers.pop(participant.identity, None)
        if handler:
            asyncio.create_task(handler.stop())

    # Register handlers *before* connecting so nothing is missed.
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))