export const INTENTS = [
  {
    id: 'create_invoice',
    icon: 'invoice',
    label: { fr: 'Créer une facture', en: 'Create an invoice' },
    example: {
      fr: 'Crée une facture pour Ahmed Salem, 3 jours de Consultation IT à 500 dinars.',
      en: 'Create an invoice for Ahmed Salem, 3 days of IT Consulting at 500 dinars.',
    },
  },
  {
    id: 'lookup_client',
    icon: 'search',
    label: { fr: 'Rechercher un client', en: 'Look up a client' },
    example: {
      fr: 'Cherche le client Sarra Trabelsi.',
      en: 'Look up client Sarra Trabelsi.',
    },
  },
  {
    id: 'check_invoice',
    icon: 'document',
    label: { fr: 'Consulter une facture', en: 'Check an invoice' },
    example: {
      fr: 'Où en est la facture numéro 202606 001 ?',
      en: "What's the status of invoice number 202606 001?",
    },
  },
  {
    id: 'add_line_item',
    icon: 'plus',
    label: { fr: 'Ajouter un article', en: 'Add a line item' },
    example: {
      fr: 'Ajoute 2 jours de Développement web à la facture numéro 202606 001.',
      en: 'Add 2 days of Web Development to invoice number 202606 001.',
    },
  },
  {
    id: 'check_payment',
    icon: 'coin',
    label: { fr: 'Vérifier un paiement', en: 'Check a payment' },
    example: {
      fr: 'Est-ce que la facture numéro 202606 001 a été payée ?',
      en: 'Has invoice number 202606 001 been paid?',
    },
  },
];