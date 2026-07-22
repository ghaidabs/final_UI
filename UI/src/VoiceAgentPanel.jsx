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
  idle: { label: 'Appuyez pour parler', dotClass: 'va-dot-idle' },
  mic_starting: { label: 'Activation du micro…', dotClass: 'va-dot-mic-starting' },
  listening: { label: 'À l\'écoute…', dotClass: 'va-dot-listening' },
  speech_detected: { label: 'Parole détectée', dotClass: 'va-dot-speech' },
  processing: { label: 'Traitement…', dotClass: 'va-dot-processing' },
  agent_speaking: { label: 'L\'assistant parle…', dotClass: 'va-dot-speaking' },
};

function MessageBody({ message }) {
  const { text, data } = message;
  const hasDraftCard = data && Array.isArray(data.articles);

  return (
    <>
      {text && <p className="va-bubble-text">{text}</p>}
      {hasDraftCard ? <InvoiceDraftCard draft={data} /> : <DisplayData data={data} />}
    </>
  );
}

function ChatThread({ messages }) {
  if (!messages.length) {
    return (
      <div className="va-chat-empty">
        Dites ou écrivez votre demande pour commencer, par exemple
        « Crée une facture pour Ahmed, 3 jours de consultation IT à 500 dinars ».
      </div>
    );
  }
  return (
    <div className="va-chat-thread">
      {messages.map((m) => {
        const isErrorState = m.role === 'assistant' && m.success === false;
        return (
          <div
            key={m.id}
            className={`va-bubble va-bubble-${m.role}${isErrorState ? ' va-bubble-assistant-error' : ''}`}
          >
            {m.role === 'assistant' ? <MessageBody message={m} /> : <p>{m.text}</p>}
            {m.clarification && m.clarification !== m.text && (
              <div className="va-clarification">{m.clarification}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Composer({ canTalk, listening, micReady, onToggleMic, onSendText, onBargeIn, agentSpeaking }) {
  const [text, setText] = useState('');
  const submit = () => { if (text.trim()) { onSendText(text); setText(''); } };

  const micStarting = listening && !micReady;
  const micLabel = agentSpeaking
    ? 'Interrompre'
    : micStarting
      ? 'Activation du micro…'
      : listening
        ? "Arrêter l'écoute"
        : 'Activer le micro';

  return (
    <div className="va-composer">
      <button
        className={`va-mic-toggle ${listening ? 'va-mic-on' : ''} ${micStarting ? 'va-mic-connecting' : ''} ${agentSpeaking ? 'va-mic-stop' : ''}`}
        onClick={agentSpeaking ? onBargeIn : onToggleMic}
        disabled={!canTalk && !agentSpeaking}
        aria-label={micLabel}
        title={micLabel}
      >
        {agentSpeaking ? '⏹' : micStarting ? '…' : '🎙'}
      </button>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="Écrivez ou parlez…"
        disabled={!canTalk}
      />
      <button className="va-btn va-btn-primary va-btn-small" onClick={submit} disabled={!canTalk || !text.trim()}>
        Envoyer
      </button>
    </div>
  );
}

export default function VoiceAgentPanel() {
  const [devToken, setDevToken] = useState('');
  const {
    status, error, live, messages, lastAssistantMessage,
    pipelineState, canTalk, listening, micReady,
    audioContainerRef, connect, disconnect,
    sendAction, sendText, toggleMic, bargeIn,
  } = useVoiceAgent();

  const connected = status === 'connected';
  const { label, dotClass } = PIPELINE_LABELS[pipelineState];

  useEffect(() => {
    if (!connected) return;
    const onKeyDown = (e) => {
      if (
        e.code === 'Space' &&
        !e.repeat &&
        live.agentSpeaking &&
        document.activeElement?.tagName !== 'INPUT'
      ) {
        e.preventDefault();
        bargeIn();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [connected, live.agentSpeaking, bargeIn]);

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

            <ChatThread messages={messages} />

            {lastAssistantMessage?.requiresConfirmation && (
              <div className="va-confirm-row">
                <button className="va-btn va-btn-mint" onClick={() => sendAction('confirm')}>
                  Confirmer
                </button>
                <button className="va-btn va-btn-secondary" onClick={() => sendAction('cancel')}>
                  Annuler
                </button>
              </div>
            )}

            <Composer
              canTalk={canTalk}
              listening={listening}
              micReady={micReady}
              onToggleMic={toggleMic}
              onSendText={sendText}
              onBargeIn={bargeIn}
              agentSpeaking={live.agentSpeaking}
            />
          </>
        )}
      </div>

      <div ref={audioContainerRef} style={{ display: 'none' }} />
    </div>
  );
}