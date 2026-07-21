import { useEffect, useState } from 'react';
import { useVoiceAgent } from './useVoiceAgent';
import './VoiceAgentPanel.css';
import { InvoiceDraftCard } from './InvoiceDraftCard.jsx';

function formatListItem(item) {
  if (item.invoice_number) return `${item.invoice_number} — ${item.client_name || ''}`;
  if (item.first_name) return `${item.first_name} ${item.last_name}`;
  if (item.designation) return item.designation;
  return JSON.stringify(item);
}

function DisplayData({ data }) {
  if (data == null) return null;
  if (Array.isArray(data)) {
    return (
      <ul className="va-data-list">
        {data.map((item, i) => <li key={i}>{formatListItem(item)}</li>)}
      </ul>
    );
  }
  const entries = Object.entries(data).filter(
    ([k, v]) => !k.startsWith('_') && v !== null && typeof v !== 'object'
  );
  if (!entries.length) return null;
  return (
    <dl className="va-data-grid">
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: 'contents' }}>
          <dt>{k}</dt>
          <dd>{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

const PIPELINE_LABELS = {
  idle: { label: 'Press and hold to talk', dotClass: 'va-dot-idle' },
  listening: { label: 'Listening…', dotClass: 'va-dot-listening' },
  speech_detected: { label: 'Speech detected', dotClass: 'va-dot-speech' },
  processing: { label: 'Processing…', dotClass: 'va-dot-processing' },
  agent_speaking: { label: 'Agent speaking…', dotClass: 'va-dot-speaking' },
};

function MessageBody({ message }) {
  const { data } = message;
  if (data && Array.isArray(data.articles)) {
    return <InvoiceDraftCard draft={data} />;
  }
  return <DisplayData data={data} />;
}

function ChatThread({ messages }) {
  return (
    <div className="va-chat-thread">
      {messages.map((m) => (
        <div key={m.id} className={`va-bubble va-bubble-${m.role}`}>
          {m.role === 'assistant' ? <MessageBody message={m} /> : <p>{m.text}</p>}
          {m.clarification && m.clarification !== m.text && (
            <div className="va-clarification">{m.clarification}</div>
          )}
        </div>
      ))}
    </div>
  );
}

function Composer({ canTalk, listening, onToggleMic, onSendText, onBargeIn, agentSpeaking }) {
  const [text, setText] = useState('');
  const submit = () => { if (text.trim()) { onSendText(text); setText(''); } };

  return (
    <div className="va-composer">
      <button
        className={`va-mic-toggle ${listening ? 'va-mic-on' : ''}`}
        onClick={agentSpeaking ? onBargeIn : onToggleMic}
        disabled={!canTalk && !agentSpeaking}
      >
        {agentSpeaking ? '⏹' : listening ? '🎙 (écoute…)' : '🎙'}
      </button>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="Écrivez ou parlez…"
        disabled={!canTalk}
      />
      <button onClick={submit} disabled={!canTalk || !text.trim()}>Envoyer</button>
    </div>
  );
}


export default function VoiceAgentPanel() {
  const [devToken, setDevToken] = useState('');
  const {
    status, error, live, pipelineState, canTalk,
    audioContainerRef, connect, disconnect, sendAction, setMicHeld,
  } = useVoiceAgent();

  const connected = status === 'connected';
  const { label, dotClass } = PIPELINE_LABELS[pipelineState];

  useEffect(() => {
    if (!connected) return;
    const onKeyDown = (e) => {
      if (e.code === 'Space' && !e.repeat && canTalk) {
        e.preventDefault();
        setMicHeld(true);
      }
    };
    const onKeyUp = (e) => {
      if (e.code === 'Space') {
        e.preventDefault();
        setMicHeld(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, [connected, canTalk, setMicHeld]);

  return (
    <div className="va-panel">
      <div className="va-header">
        <div>
          <h3>Assistant Facturation</h3>
          <p>
            <span className={`va-status-dot va-status-${status}`} />
            {status}
          </p>
        </div>
        {connected && (
          <button className="va-btn va-btn-danger va-btn-small" onClick={disconnect}>
            Disconnect
          </button>
        )}
      </div>

      <div className="va-body">
        {!connected ? (
          <>
            <div className="va-token-row">
              <input
                type="password"
                placeholder="Paste dev JWT (server/dev_token.py)"
                value={devToken}
                onChange={(e) => setDevToken(e.target.value)}
              />
            </div>
            <button
              className="va-btn va-btn-primary va-btn-full"
              disabled={status === 'connecting'}
              onClick={() => connect(devToken)}
            >
              {status === 'connecting' ? 'Connecting…' : 'Connect'}
            </button>
            {error && <div className="va-response error">{error}</div>}
          </>
        ) : (
          <>
            <div className="va-pipeline-row">
              <span className={`va-live-dot ${dotClass}`} />
              <span className="va-pipeline-label">{label}</span>
            </div>

            <div className="va-ptt-wrap">
              <button
                className={`va-ptt-btn ${live.micHeld ? 'va-ptt-active' : ''} ${live.vadSpeaking ? 'va-ptt-speech' : ''}`}
                disabled={!canTalk}
                onMouseDown={() => canTalk && setMicHeld(true)}
                onMouseUp={() => setMicHeld(false)}
                onMouseLeave={() => live.micHeld && setMicHeld(false)}
                onTouchStart={() => canTalk && setMicHeld(true)}
                onTouchEnd={() => setMicHeld(false)}
              >
                🎙
              </button>
              <span className="va-ptt-hint">
                {canTalk ? 'Hold to talk (or press Space)' : 'Please wait…'}
              </span>
            </div>

            {live.finalTranscript && (
              <div className="va-transcript-box">
                <span className="va-transcript-label">🎙 You</span>
                <p>{live.finalTranscript}</p>
              </div>
            )}

            {live.response && (
              <>
                <div className={`va-response ${live.response.error ? 'error' : ''}`}>
                  {live.response.display_text}
                </div>

                {live.response.clarification_question &&
                  live.response.clarification_question !== live.response.display_text && (
                    <div className="va-clarification">{live.response.clarification_question}</div>
                  )}

                <DisplayData data={live.response.display_data ?? live.response.draft_payload} />

                {live.response.requires_confirmation && (
                  <div className="va-confirm-row">
                    <button className="va-btn va-btn-mint" onClick={() => sendAction('confirm')}>
                      Confirmer
                    </button>
                    <button className="va-btn va-btn-secondary" onClick={() => sendAction('cancel')}>
                      Annuler
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      <div ref={audioContainerRef} style={{ display: 'none' }} />
    </div>
  );
}