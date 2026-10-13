import { idempotencyKey, request } from './api'

// The page behind OWNER_CONFIRMATION_URL: Oweru sends a WhatsApp link with a
// delivery id and a single-use token, and the person opens it here. No
// sign-in; the token is the proof (payments.views.DecisionView).

export type ConfirmationPurpose = 'PHONE' | 'OWNER_PRICE' | 'OWNER_RECEIPT' | 'FULL_CHECK_CONSENT'

export type Confirmation = { purpose: ConfirmationPurpose; context: Record<string, string> }

export const confirmApi = {
  open: (delivery: string, token: string) =>
    request<Confirmation>(`/payments/confirmations/${encodeURIComponent(delivery)}/?token=${encodeURIComponent(token)}`),

  decide: (delivery: string, token: string, decision: 'CONFIRM' | 'DECLINE') =>
    request<{ delivery_id: string; decision: string }>(`/payments/confirmations/${encodeURIComponent(delivery)}/`, {
      method: 'POST',
      body: { token, decision },
      headers: { 'Idempotency-Key': idempotencyKey() },
    }),
}
