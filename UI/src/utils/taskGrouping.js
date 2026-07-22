const TERMINAL_STATES = new Set(['completed', 'cancelled', 'error', 'idle']);
export const CANCELABLE_STATES = new Set(['collecting', 'disambiguating', 'confirming']);

export function groupIntoTasks(messages) {
  const tasks = [];
  let current = null;

  for (const message of messages) {
    if (!current) {
      current = { id: message.id, status: 'in_progress', messages: [] };
      tasks.push(current);
    }
    current.messages.push(message);

    if (message.role === 'assistant' && TERMINAL_STATES.has(message.turnState)) {
      current.status = message.turnState;
      current = null;
    }
  }

  return tasks;
}