import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

const TOKEN_ENDPOINT = import.meta.env.VITE_LIVEKIT_TOKEN_URL;

const initialLiveState = {
  vadSpeaking: false,
  processing: false,
  agentSpeaking: false,
  response: null,
};

export function useVoiceAgent() {
  const roomRef = useRef(null);
  const audioContainerRef = useRef(null);
  const msgIdRef = useRef(0);

  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [live, setLive] = useState(initialLiveState);
  const [messages, setMessages] = useState([]);
  const [listening, setListening] = useState(false);

  const patchLive = useCallback((patch) => {
    setLive((prev) => ({ ...prev, ...patch }));
  }, []);

  const nextId = useCallback(() => {
    msgIdRef.current += 1;
    return msgIdRef.current;
  }, []);

  const pushMessage = useCallback((msg) => {
    setMessages((prev) => [...prev, { id: nextId(), ...msg }]);
  }, [nextId]);

  const setAgentAudioMuted = useCallback((muted) => {
    const container = audioContainerRef.current;
    if (!container) return;
    container.querySelectorAll('audio').forEach((el) => {
      el.muted = muted;
    });
  }, []);

  const disconnect = useCallback(async () => {
    if (roomRef.current) {
      await roomRef.current.disconnect();
      roomRef.current = null;
    }
    setStatus('disconnected');
    setLive(initialLiveState);
    setMessages([]);
    setListening(false);
  }, []);

  const connect = useCallback(async (devToken) => {
    if (!devToken) {
      setError('Missing dev JWT — paste one from server/dev_token.py');
      return;
    }
    setStatus('connecting');
    setError(null);
    setLive(initialLiveState);
    setMessages([]);
    setListening(false);

    try {
      const tokenRes = await fetch(TOKEN_ENDPOINT, {
        method: 'POST',
        headers: { Authorization: `Bearer ${devToken}` },
      });
      if (!tokenRes.ok) throw new Error(`Token endpoint returned ${tokenRes.status}`);
      const { url, token } = await tokenRes.json();

      const room = new Room();
      roomRef.current = room;

      room
        .on(RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === Track.Kind.Audio) {
            const el = track.attach();
            el.autoplay = true;
            audioContainerRef.current?.appendChild(el);
          }
        })
        .on(RoomEvent.TrackUnsubscribed, (track) => {
          track.detach().forEach((el) => el.remove());
        })
        .on(RoomEvent.DataReceived, (payload) => {
          let msg;
          try {
            msg = JSON.parse(new TextDecoder().decode(payload));
          } catch {
            console.warn('Malformed data payload from agent');
            return;
          }

          switch (msg.type) {
            case 'vad_state':
              patchLive({ vadSpeaking: msg.speaking });
              break;

            case 'transcript_final':
              pushMessage({ role: 'user', text: msg.text });
              break;

            case 'processing':
              patchLive({ processing: msg.active });
              break;

            case 'agent_speaking':
              patchLive({ agentSpeaking: msg.speaking });
              if (msg.speaking) setAgentAudioMuted(false);
              break;

            case 'response':
              pushMessage({
                role: 'assistant',
                text: msg.display_text,
                data: msg.display_data ?? msg.draft_payload,
                turnState: msg.turn_state,
                requiresConfirmation: msg.requires_confirmation,
                clarification: msg.clarification_question,
                error: msg.error,
                language: msg.language,
              });
              patchLive({ response: msg });
              break;

            default:
              break;
          }
        })
        .on(RoomEvent.Disconnected, () => {
          setStatus('disconnected');
          setLive(initialLiveState);
          setMessages([]);
          setListening(false);
        });

      await room.connect(url, token);
      setStatus('connected');
    } catch (err) {
      console.error(err);
      setError(err.message || String(err));
      setStatus('error');
    }
  }, [patchLive, pushMessage, setAgentAudioMuted]);

  const toggleMic = useCallback(async () => {
    const room = roomRef.current;
    if (!room || status !== 'connected') return;
    const next = !listening;
    await room.localParticipant.setMicrophoneEnabled(next);
    setListening(next);
  }, [status, listening]);

  const sendAction = useCallback((action) => {
    const room = roomRef.current;
    if (!room || status !== 'connected') return;
    const payload = { type: 'user_action', action, language: live.response?.language || 'fr' };
    room.localParticipant.publishData(new TextEncoder().encode(JSON.stringify(payload)), {
      reliable: true,
      topic: 'user_action',
    });
  }, [status, live.response]);

  const sendText = useCallback((text, language) => {
    const room = roomRef.current;
    const trimmed = (text || '').trim();
    if (!room || status !== 'connected' || !trimmed) return;

    pushMessage({ role: 'user', text: trimmed });

    const payload = {
      type: 'text_input',
      text: trimmed,
      language: language || live.response?.language || 'fr',
    };
    room.localParticipant.publishData(new TextEncoder().encode(JSON.stringify(payload)), {
      reliable: true,
      topic: 'user_action',
    });
  }, [status, live.response, pushMessage]);

  const bargeIn = useCallback(async () => {
    setAgentAudioMuted(true);
    patchLive({ agentSpeaking: false });
    sendAction('barge_in');
    // Ensure mic is on after barge-in (don't toggle off if already listening)
    const room = roomRef.current;
    if (room && status === 'connected' && !listening) {
      await room.localParticipant.setMicrophoneEnabled(true);
      setListening(true);
    }
  }, [setAgentAudioMuted, patchLive, sendAction, status, listening]);

  const lastAssistantMessage = useMemo(
    () => [...messages].reverse().find((m) => m.role === 'assistant') || null,
    [messages]
  );

  const pipelineState = useMemo(() => {
    if (live.agentSpeaking) return 'agent_speaking';
    if (live.processing) return 'processing';
    if (live.vadSpeaking) return 'speech_detected';
    if (listening) return 'listening';
    return 'idle';
  }, [live, listening]);

  const canTalk = status === 'connected' && !live.processing && !live.agentSpeaking;

  useEffect(() => () => { roomRef.current?.disconnect(); }, []);

  return {
    status, error, live, messages, lastAssistantMessage,
    pipelineState, canTalk, listening,
    audioContainerRef, connect, disconnect,
    sendAction, sendText, toggleMic, bargeIn,
  };
}