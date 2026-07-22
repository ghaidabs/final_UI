import { Receipt, UserSearch, FileSearch, ListPlus, CircleDollarSign } from 'lucide-react';
import { INTENTS } from '../utils/intents';


const ICON_MAP = {
  invoice: Receipt,
  search: UserSearch,
  document: FileSearch,
  plus: ListPlus,
  coin: CircleDollarSign,
};

function IntentIcon({ name, size = 16 }) {
  const Cmp = ICON_MAP[name];
  if (!Cmp) return null;
  return <Cmp size={size} strokeWidth={1.8} aria-hidden="true" />;
}

export function IntentChips({ lang, onPick }) {
  return (
    <div className="va-quick-actions" role="list">
      {INTENTS.map((intent) => (
        <button
          key={intent.id}
          type="button"
          role="listitem"
          className="va-chip"
          onClick={() => onPick(intent.example[lang] || intent.example.fr)}
          title={intent.example[lang] || intent.example.fr}
        >
          <IntentIcon name={intent.icon} size={16} />
          <span>{intent.label[lang] || intent.label.fr}</span>
        </button>
      ))}
    </div>
  );
}

export function OnboardingCard({ lang, strings, onPick }) {
  return (
    <div className="va-onboarding">
      <h4>{strings.onboardingTitle}</h4>
      <p>{strings.onboardingSubtitle}</p>
      <div className="va-onboarding-grid">
        {INTENTS.map((intent) => (
          <button
            key={intent.id}
            type="button"
            className="va-onboarding-card"
            onClick={() => onPick(intent.example[lang] || intent.example.fr)}
          >
            <span className="va-onboarding-icon">
              <IntentIcon name={intent.icon} size={20} />
            </span>
            <span className="va-onboarding-label">{intent.label[lang] || intent.label.fr}</span>
            <span className="va-onboarding-example">“{intent.example[lang] || intent.example.fr}”</span>
          </button>
        ))}
      </div>
    </div>
  );
}