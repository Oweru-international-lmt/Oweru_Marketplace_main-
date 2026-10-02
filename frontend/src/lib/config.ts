export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// Oweru support number from oweru.com/contact, in wa.me format (no "+").
export const SUPPORT_WHATSAPP = import.meta.env.VITE_SUPPORT_WHATSAPP || '255711890764'

export function whatsappLink(message: string): string {
  return `https://wa.me/${SUPPORT_WHATSAPP}?text=${encodeURIComponent(message)}`
}
