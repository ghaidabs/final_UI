export function LineItemCard({ item, lang = 'fr' }) {
  if (!item) return null;
  const qty = item.quantity;
  const qtyLabel = Number.isInteger(qty) ? qty : qty?.toFixed?.(2) ?? qty;

  return (
    <div className="va-line-item-card">
      <div className="va-line-item-main">
        <strong>{item.designation}</strong>
        <span className="va-line-item-qty">
          {qtyLabel}{item.unit ? ` × ${item.unit}` : ''}
        </span>
      </div>
      <div className="va-line-item-meta">
        <span>{lang === 'en' ? 'Unit price' : 'Prix unitaire'}: {item.unit_price}</span>
        {item.invoice_number && (
          <span>{lang === 'en' ? 'Invoice' : 'Facture'}: {item.invoice_number}</span>
        )}
      </div>
    </div>
  );
}