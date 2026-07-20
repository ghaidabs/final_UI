import { useState } from 'react';
import { useVoiceAgent } from './useVoiceAgent';
import './VoiceAgentPanel.css';

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

export default function VoiceAgentPanel() {
  const [devToken, setDevToken] = useState('');
  const {
    status, error, response, micEnabled, agentSpeaking,
    audioContainerRef, connect, disconnect, sendAction, toggleMic,
  } = useVoiceAgent();

  const connected = status === 'connected';

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
        {agentSpeaking && (
          <span className="va-speaking-badge">
            <span className="va-speaking-dot" />
            speaking
          </span>
        )}
      </div>

      <div className="va-body">
        {!connected && (
          <div className="va-token-row">
            <input
              type="password"
              placeholder="Paste dev JWT (server/dev_token.py)"
              value={devToken}
              onChange={(e) => setDevToken(e.target.value)}
            />
          </div>
        )}

        <div className="va-actions-row">
          {!connected ? (
            <button
              className="va-btn va-btn-primary"
              disabled={status === 'connecting'}
              onClick={() => connect(devToken)}
            >
              {status === 'connecting' ? 'Connecting…' : 'Connect'}
            </button>
          ) : (
            <>
              <button className="va-btn va-btn-danger" onClick={disconnect}>Disconnect</button>
              <button className="va-btn va-btn-secondary" onClick={toggleMic}>
                {micEnabled ? 'Mute mic' : 'Unmute mic'}
              </button>
            </>
          )}
        </div>

        {error && <div className="va-response error">{error}</div>}

        {response && (
          <>
            <div className="va-response">{response.display_text}</div>

            {response.clarification_question && (
              <div className="va-clarification">{response.clarification_question}</div>
            )}

            <DisplayData data={response.display_data} />

            {response.requires_confirmation && (
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
      </div>

      {/* hidden container for the agent's remote audio element */}
      <div ref={audioContainerRef} style={{ display: 'none' }} />
    </div>
  );
}