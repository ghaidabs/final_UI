import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

const TOKEN_ENDPOINT = import.meta.env.VITE_LIVEKIT_TOKEN_URL;

const initialLiveState = {
  micHeld: false,
  vadSpeaking: false,
  processing: false,
  agentSpeaking: false,
  finalTranscript: '',
  response: null,
};

export function useVoiceAgent() {
  const roomRef = useRef(null);
  const audioContainerRef = useRef(null);

  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [live, setLive] = useState(initialLiveState);

  const patchLive = useCallback((patch) => {
    setLive((prev) => ({ ...prev, ...patch }));
  }, []);

  const disconnect = useCallback(async () => {
    if (roomRef.current) {
      await roomRef.current.disconnect();
      roomRef.current = null;
    }
    setStatus('disconnected');
    setLive(initialLiveState);
  }, []);

  const connect = useCallback(async (devToken) => {
    if (!devToken) {
      setError('Missing dev JWT — paste one from server/dev_token.py');
      return;
    }
    setStatus('connecting');
    setError(null);
    setLive(initialLiveState);

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
              patchLive({ finalTranscript: msg.text });
              break;
            case 'processing':
              patchLive({ processing: msg.active });
              break;
            case 'agent_speaking':
              patchLive({ agentSpeaking: msg.speaking });
              break;
            case 'response':
              patchLive({ response: msg });
              break;
            default:
              break;
          }
        })
        .on(RoomEvent.Disconnected, () => {
          setStatus('disconnected');
          setLive(initialLiveState);
        });

      await room.connect(url, token);
      setStatus('connected');
    } catch (err) {
      console.error(err);
      setError(err.message || String(err));
      setStatus('error');
    }
  }, [patchLive]);

  const setMicHeld = useCallback(async (held) => {
    const room = roomRef.current;
    if (!room || status !== 'connected') return;
    await room.localParticipant.setMicrophoneEnabled(held);
    patchLive({
      micHeld: held,
      ...(held ? { finalTranscript: '' } : { vadSpeaking: false }), 
    });
  }, [status, patchLive]);

  const sendAction = useCallback((action) => {
    const room = roomRef.current;
    if (!room || status !== 'connected') return;
    const payload = { type: 'user_action', action, language: live.response?.language || 'fr' };
    room.localParticipant.publishData(new TextEncoder().encode(JSON.stringify(payload)), {
      reliable: true,
      topic: 'user_action',
    });
  }, [status, live.response]);

  const pipelineState = useMemo(() => {
    if (live.agentSpeaking) return 'agent_speaking';
    if (live.processing) return 'processing';
    if (live.vadSpeaking) return 'speech_detected';
    if (live.micHeld) return 'listening';
    return 'idle';
  }, [live]);

  const canTalk = status === 'connected' && !live.processing && !live.agentSpeaking;

  useEffect(() => () => { roomRef.current?.disconnect(); }, []);

  return {
    status, error, live, pipelineState, canTalk,
    audioContainerRef, connect, disconnect, sendAction, setMicHeld,
  };
}