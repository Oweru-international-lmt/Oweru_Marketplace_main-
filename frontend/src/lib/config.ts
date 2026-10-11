export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// Oweru support number from oweru.com/contact, in wa.me format (no "+").
export const SUPPORT_WHATSAPP = import.meta.env.VITE_SUPPORT_WHATSAPP || '255711890764'

export function whatsappLink(message: string): string {
  return `https://wa.me/${SUPPORT_WHATSAPP}?text=${encodeURIComponent(message)}`
}

// Click-to-chat from Oweru staff to a person (SRD 20 self-service). Without a
// number, WhatsApp lets the sender pick the contact.
export function whatsappTo(phone: string | null, message: string): string {
  const digits = phone ? phone.replace(/\D/g, '') : ''
  return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`
}
