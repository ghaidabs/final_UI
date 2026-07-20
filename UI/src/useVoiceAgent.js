import { useCallback, useEffect, useRef, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

const TOKEN_ENDPOINT = import.meta.env.VITE_LIVEKIT_TOKEN_URL;

export function useVoiceAgent() {
  const roomRef = useRef(null);
  const audioContainerRef = useRef(null);

  const [status, setStatus] = useState('idle'); 
  const [micEnabled, setMicEnabled] = useState(false);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [response, setResponse] = useState(null); // last VoiceResponse-shaped payload
  const [error, setError] = useState(null);

  const disconnect = useCallback(async () => {
    if (roomRef.current) {
      await roomRef.current.disconnect();
      roomRef.current = null;
    }
    setStatus('disconnected');
    setMicEnabled(false);
    setAgentSpeaking(false);
  }, []);

  const connect = useCallback(async (devToken) => {
    if (!devToken) {
      setError('Missing dev JWT — paste one from server/dev_token.py');
      return;
    }
    setStatus('connecting');
    setError(null);

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
        .on(RoomEvent.TrackSubscribed, (track, publication) => {
          if (track.kind === Track.Kind.Audio) {
            const el = track.attach();
            el.autoplay = true;
            audioContainerRef.current?.appendChild(el);
            if (publication.trackName === 'assistant-voice') setAgentSpeaking(true);
          }
        })
        .on(RoomEvent.TrackUnsubscribed, (track, publication) => {
          track.detach().forEach((el) => el.remove());
          if (track.kind === Track.Kind.Audio && publication.trackName === 'assistant-voice') {
            setAgentSpeaking(false);
          }
        })
        .on(RoomEvent.DataReceived, (payload) => {
          try {
            setResponse(JSON.parse(new TextDecoder().decode(payload)));
          } catch {
            console.warn('Malformed data payload from agent');
          }
        })
        .on(RoomEvent.Disconnected, () => {
          setStatus('disconnected');
          setMicEnabled(false);
        });

      await room.connect(url, token);
      setStatus('connected');
    } catch (err) {
      console.error(err);
      setError(err.message || String(err));
      setStatus('error');
    }
  }, []);

  const setMicActive = useCallback(async (active) => {
    const room = roomRef.current;
    if (!room) return;
    await room.localParticipant.setMicrophoneEnabled(active);
    setMicEnabled(active);
  }, []);

  const sendAction = useCallback(
    (action) => {
      const room = roomRef.current;
      if (!room || status !== 'connected') return;
      const payload = { type: 'user_action', action, language: response?.language || 'fr' };
      room.localParticipant.publishData(new TextEncoder().encode(JSON.stringify(payload)), {
        reliable: true,
        topic: 'user_action',
      });
    },
    [status, response]
  );

  const toggleMic = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;
    const next = !micEnabled;
    await room.localParticipant.setMicrophoneEnabled(next);
    setMicEnabled(next);
  }, [micEnabled]);

  useEffect(() => () => { roomRef.current?.disconnect(); }, []);

  return {
    status, error, response, micEnabled, agentSpeaking,
    audioContainerRef, connect, disconnect, sendAction, toggleMic, setMicActive,
  };
}