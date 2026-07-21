export function InvoiceDraftCard({ draft }) {
  if (!draft) return null;
  const articles = draft.articles || [];
  return (
    <div className="va-draft-card">
      <div className="va-draft-header">
        <strong>{draft.client_name}</strong>
        <span>{draft.client_address}</span>
      </div>
      <table className="va-draft-table">
        <thead>
          <tr><th>Article</th><th>Quantité</th><th>Unité</th><th>PU</th><th>Total HT</th></tr>
        </thead>
        <tbody>
          {articles.map((a, i) => (
            <tr key={i}>
              <td>{a.designation}</td>
              <td>{a.quantity}</td>
              <td>{a.unit}</td>
              <td>{a.unit_price} {draft.currency}</td>
              <td>{a.total_ht} {draft.currency}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="va-draft-totals">
        <div>Total HT: {draft.total_ht} {draft.currency}</div>
        {draft.is_tva_applicable && <div>TVA: {draft.tva} {draft.currency}</div>}
        {draft.is_stamp_applicable && <div>Timbre: 1.000 {draft.currency}</div>}
        <div className="va-draft-grand-total">Total TTC: {draft.total_ttc} {draft.currency}</div>
      </div>
    </div>
  );
}