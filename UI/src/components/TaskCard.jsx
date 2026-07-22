import { InvoiceDraftCard } from './InvoiceDraftCard.jsx';
import { LineItemCard } from './LineItemCard.jsx';
import { DisplayData } from './DisplayData.jsx';

const STATUS_META = {
  idle: { key: 'statusClarifying', tone: 'amber' },
  in_progress: { key: 'statusInProgress', tone: 'amber' },
  collecting: { key: 'statusClarifying', tone: 'amber' },
  disambiguating: { key: 'statusDisambiguating', tone: 'amber' },
  confirming: { key: 'statusWaitingConfirm', tone: 'amber' },
  completed: { key: 'statusDone', tone: 'teal' },
  cancelled: { key: 'statusCancelled', tone: 'muted' },
  error: { key: 'statusError', tone: 'red' },
};

function StatusBadge({ status, strings }) {
  const meta = STATUS_META[status] || STATUS_META.in_progress;
  return <span className={`va-task-status va-task-status-${meta.tone}`}>{strings[meta.key]}</span>;
}

function MessageBody({ message, lang }) {
  const { text, data } = message;
  const hasDraftCard = data && Array.isArray(data.articles);
  const hasLineItem =
    data && !Array.isArray(data.articles) && typeof data.unit_price === 'number' && data.designation;

  return (
    <>
      {text && <p className="va-bubble-text">{text}</p>}
      {hasDraftCard ? (
        <InvoiceDraftCard draft={data} />
      ) : hasLineItem ? (
        <LineItemCard item={data} lang={lang} />
      ) : (
        <DisplayData data={data} lang={lang} />
      )}
    </>
  );
}

export function TaskCard({ task, lang, strings, requiresConfirmation, onConfirm, onCancel, readOnly = false }) {
  const tone = STATUS_META[task.status]?.tone || 'amber';

  return (
    <section className={`va-task-card va-task-tone-${tone}`}>
      <header className="va-task-card-header">
        <StatusBadge status={task.status} strings={strings} />
      </header>
      <div className="va-task-body">
        {task.messages.map((m) => {
          const isErrorState = m.role === 'assistant' && m.success === false;
          return (
            <div
              key={m.id}
              className={`va-bubble va-bubble-${m.role}${isErrorState ? ' va-bubble-assistant-error' : ''}`}
            >
              {m.role === 'assistant' ? <MessageBody message={m} lang={lang} /> : <p>{m.text}</p>}
              {m.clarification && m.clarification !== m.text && (
                <div className="va-clarification">{m.clarification}</div>
              )}
            </div>
          );
        })}
      </div>
      {!readOnly && requiresConfirmation && (
        <div className="va-confirm-row">
          <button className="va-btn va-btn-mint" onClick={onConfirm}>{strings.confirm}</button>
          <button className="va-btn va-btn-secondary" onClick={onCancel}>{strings.cancel}</button>
        </div>
      )}
    </section>
  );
}