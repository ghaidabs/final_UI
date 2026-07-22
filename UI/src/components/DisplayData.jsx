const FIELD_LABELS = {
  fr: {
    invoice_number: 'Facture', client_name: 'Client', status: 'Statut',
    total_ht: 'Total HT', total_ttc: 'Total TTC', tva: 'TVA', currency: 'Devise',
    phone: 'Téléphone', address: 'Adresse', email: 'Email', designation: 'Désignation',
    quantity: 'Quantité', unit_price: 'Prix unitaire', unit: 'Unité',
    first_name: 'Prénom', last_name: 'Nom', payment_method: 'Mode de paiement', date_issued: 'Date',
  },
  en: {
    invoice_number: 'Invoice', client_name: 'Client', status: 'Status',
    total_ht: 'Subtotal', total_ttc: 'Total', tva: 'VAT', currency: 'Currency',
    phone: 'Phone', address: 'Address', email: 'Email', designation: 'Item',
    quantity: 'Quantity', unit_price: 'Unit price', unit: 'Unit',
    first_name: 'First name', last_name: 'Last name', payment_method: 'Payment method', date_issued: 'Date',
  },
};

function humanize(key) {
  return key.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

function fieldLabel(key, lang) {
  return FIELD_LABELS[lang]?.[key] || FIELD_LABELS.fr[key] || humanize(key);
}

function itemSummary(item) {
  if (item.invoice_number) return `${item.invoice_number}${item.client_name ? ` — ${item.client_name}` : ''}`;
  if (item.first_name) return `${item.first_name} ${item.last_name || ''}`.trim();
  if (item.designation) return item.designation;
  return null;
}

export function DisplayData({ data, lang = 'fr' }) {
  if (data == null) return null;

  if (Array.isArray(data)) {
    if (!data.length) return null;
    return (
      <ul className="va-data-list">
        {data.map((item, i) => (
          <li key={item.id ?? item.invoice_number ?? i}>{itemSummary(item) || `#${i + 1}`}</li>
        ))}
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
        <div key={k} className="va-data-row">
          <dt>{fieldLabel(k, lang)}</dt>
          <dd>{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}