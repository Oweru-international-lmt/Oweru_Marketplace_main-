// Display helpers. Money is whole Tanzanian shillings (SRD 9.1); the API sends
// decimals as strings, so parse before formatting.

function locale(language: string): string {
  return language === 'sw' ? 'sw-TZ' : 'en-GB'
}

export function formatTsh(value: string | number, language: string): string {
  const amount = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(amount)) return String(value)
  return `TSh ${new Intl.NumberFormat(locale(language), { maximumFractionDigits: 0 }).format(amount)}`
}

// Short form for cards: TSh 120M, TSh 850K.
export function formatTshShort(value: string | number, language: string): string {
  const amount = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(amount)) return String(value)
  return `TSh ${new Intl.NumberFormat(locale(language), { notation: 'compact', maximumFractionDigits: 1 }).format(amount)}`
}

export function formatNumber(value: string | number, language: string): string {
  const amount = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(amount)) return String(value)
  return new Intl.NumberFormat(locale(language), { maximumFractionDigits: 2 }).format(amount)
}

export function formatDate(value: string, language: string): string {
  return new Intl.DateTimeFormat(locale(language), { dateStyle: 'long' }).format(new Date(value))
}

// "11 Oct 2026", for dense staff tables.
export function formatShortDate(value: string, language: string): string {
  return new Intl.DateTimeFormat(locale(language), { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value))
}

// Digits only, for price and size inputs ("120,000,000" -> "120000000").
export function digitsOnly(value: string): string {
  return value.replace(/[^\d]/g, '')
}
