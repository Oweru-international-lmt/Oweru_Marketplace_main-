// The backend matches phone numbers as exact strings, so every form sends
// Tanzanian mobile numbers in one format (+255XXXXXXXXX). Without this,
// "0712 345 678" at sign-up and "+255712345678" at sign-in would be two
// different accounts.
export function normalizePhone(input: string): string | null {
  const compact = input.replace(/[\s\-().]/g, '')
  let local: string
  if (/^\+255\d{9}$/.test(compact)) local = compact.slice(4)
  else if (/^255\d{9}$/.test(compact)) local = compact.slice(3)
  else if (/^0\d{9}$/.test(compact)) local = compact.slice(1)
  else if (/^\d{9}$/.test(compact)) local = compact
  else return null
  return /^[67]\d{8}$/.test(local) ? `+255${local}` : null
}

export function formatPhone(phone: string): string {
  const match = /^\+255(\d{3})(\d{3})(\d{3})$/.exec(phone)
  return match ? `+255 ${match[1]} ${match[2]} ${match[3]}` : phone
}
