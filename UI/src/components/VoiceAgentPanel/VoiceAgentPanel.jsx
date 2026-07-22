import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useVoiceAgent } from '../../hooks/useVoiceAgent.js';
import './VoiceAgentPanel.css';
import { TaskCard } from '../TaskCard.jsx';
import { IntentChips, OnboardingCard } from '../IntentSuggestions.jsx';
import { groupIntoTasks, CANCELABLE_STATES } from '../../utils/taskGrouping.js';
import { useStrings } from '../../utils/i18n.js';

const PIPELINE_DOT_CLASS = {
  idle: 'va-dot-idle',
  mic_starting: 'va-dot-mic-starting',
  listening: 'va-dot-listening',
  speech_detected: 'va-dot-speech',
  processing: 'va-dot-processing',
  agent_speaking: 'va-dot-speaking',
};

function defaultUiLang() {
  const nav = typeof navigator !== 'undefined' ? navigator.language : 'fr';
  return (nav || 'fr').toLowerCase().startsWith('en') ? 'en' : 'fr';
}

export default function VoiceAgentPanel() {
  const [devToken, setDevToken] = useState('');
  const [uiLang, setUiLang] = useState(defaultUiLang);
  const [draft, setDraft] = useState('');
  const [taskBoundaryId, setTaskBoundaryId] = useState(0);
  const inputRef = useRef(null);

  const {
    status, error, live, messages,
    pipelineState, canTalk, listening, micReady,
    audioContainerRef, connect, disconnect,
    sendAction, sendText, toggleMic, bargeIn,
  } = useVoiceAgent();

  const strings = useStrings(uiLang);
  const connected = status === 'connected';

  useEffect(() => {
    if (status === 'disconnected') setTaskBoundaryId(0);
  }, [status]);

  const tasks = useMemo(() => groupIntoTasks(messages), [messages]);
  const currentTasks = useMemo(
    () => tasks.filter((t) => t.messages[0].id > taskBoundaryId),
    [tasks, taskBoundaryId]
  );
  const historyTasks = useMemo(
    () => tasks.filter((t) => t.messages[0].id <= taskBoundaryId),
    [tasks, taskBoundaryId]
  );

  const lastCurrentTask = currentTasks[currentTasks.length - 1] || null;
  const lastCurrentMessage = lastCurrentTask?.messages[lastCurrentTask.messages.length - 1];

  const taskOpen = Boolean(
    lastCurrentTask?.status === 'in_progress' && CANCELABLE_STATES.has(lastCurrentMessage?.turnState)
  );

  const requiresConfirmation = Boolean(
    lastCurrentMessage?.role === 'assistant' && lastCurrentMessage.requiresConfirmation
  );

  const handlePick = useCallback((example) => {
    setDraft(example);
    inputRef.current?.focus();
  }, []);

  const handleNewRequest = useCallback(() => {
    if (taskOpen) sendAction('cancel');
    setTaskBoundaryId(messages.length ? messages[messages.length - 1].id : 0);
    setDraft('');
  }, [taskOpen, sendAction, messages]);

  const pipelineLabel = strings.pipeline[pipelineState];
  const pipelineDotClass = PIPELINE_DOT_CLASS[pipelineState];

  return (
    <div className="va-panel">
      <div className="va-header">
        <div>
          <h3>
            {strings.appName}
            {live.response?.language && (
              <span className="va-lang-badge">{live.response.language.toUpperCase()}</span>
            )}
          </h3>
          <p>
            <span className={`va-status-dot va-status-${status}`} />
            {status}
          </p>
        </div>
        <div className="va-header-actions">
          <div className="va-lang-toggle" role="group" aria-label="UI language">
            <button type="button" className={uiLang === 'fr' ? 'active' : ''} onClick={() => setUiLang('fr')}>FR</button>
            <button type="button" className={uiLang === 'en' ? 'active' : ''} onClick={() => setUiLang('en')}>EN</button>
          </div>
          {connected && (
            <button className="va-btn va-btn-danger va-btn-small" onClick={disconnect}>
              {strings.disconnect}
            </button>
          )}
        </div>
      </div>

      <div className="va-body">
        {!connected ? (
          <>
            <div className="va-token-row">
              <input
                type="password"
                placeholder={strings.tokenPlaceholder}
                value={devToken}
                onChange={(e) => setDevToken(e.target.value)}
              />
            </div>
            <button
              className="va-btn va-btn-primary va-btn-full"
              disabled={status === 'connecting'}
              onClick={() => connect(devToken)}
            >
              {status === 'connecting' ? strings.connecting : strings.connect}
            </button>
            {error && <div className="va-response error">{error}</div>}
          </>
        ) : (
          <>
            <div className="va-pipeline-row">
              <span className={`va-live-dot ${pipelineDotClass}`} />
              <span className="va-pipeline-label">{pipelineLabel}</span>
              <button
                type="button"
                className="va-btn va-btn-secondary va-btn-small va-new-request"
                onClick={handleNewRequest}
                disabled={currentTasks.length === 0}
              >
                {strings.newRequest}
              </button>
            </div>

            <div className="va-task-list">
              {currentTasks.length === 0 ? (
                <OnboardingCard lang={uiLang} strings={strings} onPick={handlePick} />
              ) : (
                currentTasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    lang={uiLang}
                    strings={strings}
                    requiresConfirmation={task === lastCurrentTask && requiresConfirmation}
                    onConfirm={() => sendAction('confirm')}
                    onCancel={() => sendAction('cancel')}
                  />
                ))
              )}

              {currentTasks.length > 0 && !taskOpen && (
                <div className="va-task-followup">
                  <p className="va-task-followup-label">{strings.quickActionsTitle}</p>
                  <IntentChips lang={uiLang} onPick={handlePick} />
                </div>
              )}
            </div>

            {historyTasks.length > 0 && (
              <details className="va-history">
                <summary>{strings.history} ({historyTasks.length})</summary>
                <div className="va-history-list">
                  {historyTasks.map((task) => (
                    <TaskCard key={task.id} task={task} lang={uiLang} strings={strings} readOnly />
                  ))}
                </div>
              </details>
            )}

            <Composer
              value={draft}
              onChange={setDraft}
              inputRef={inputRef}
              canTalk={canTalk}
              listening={listening}
              micReady={micReady}
              onToggleMic={toggleMic}
              onSend={sendText}
              onBargeIn={bargeIn}
              agentSpeaking={live.agentSpeaking}
              strings={strings}
            />
          </>
        )}
      </div>

      <div ref={audioContainerRef} style={{ display: 'none' }} />
    </div>
  );
}

function Composer({ value, onChange, inputRef, canTalk, listening, micReady, onToggleMic, onSend, onBargeIn, agentSpeaking, strings }) {
  const submit = () => {
    if (value.trim()) {
      onSend(value);
      onChange('');
    }
  };

  const micStarting = listening && !micReady;
  const micLabel = agentSpeaking
    ? strings.interrupt
    : micStarting
      ? strings.pipeline.mic_starting
      : listening
        ? strings.pipeline.listening
        : strings.pipeline.idle;

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
        ref={inputRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder={strings.composerPlaceholder}
        disabled={!canTalk}
      />
      <button className="va-btn va-btn-primary va-btn-small" onClick={submit} disabled={!canTalk || !value.trim()}>
        {strings.send}
      </button>
    </div>
  );
}