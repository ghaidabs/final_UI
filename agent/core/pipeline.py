from agent.core.session import SessionState
from agent.nlp.nlu import extract_intent_with_context
from agent.core.dispatcher import dispatch, resume_awaiting_field
from api.mock_saas_client import MockSaasClient
from schemas.responses import VoiceResponse


async def run_turn(transcript: str, session: SessionState, saas: MockSaasClient, language: str = "fr") -> VoiceResponse:
        if session.awaiting_field:
            resumed = await resume_awaiting_field(transcript, session, saas, language)
            if resumed is not None:
                return resumed

        intent = extract_intent_with_context(transcript, session, language=language)
        return await dispatch(intent, saas, session)