import { idempotencyKey, request } from './api'

// The page behind OWNER_CONFIRMATION_URL: Oweru sends a WhatsApp link with a
// delivery id and a single-use token, and the person opens it here. No
// sign-in; the token is the proof. Phone, owner price and owner receipt links
// answer at payments.views.DecisionView; a full check consent link carries
// ?purpose=FULL_CHECK_CONSENT and answers at its own full check endpoint.

export type ConfirmationPurpose = 'PHONE' | 'OWNER_PRICE' | 'OWNER_RECEIPT' | 'FULL_CHECK_CONSENT'

export type ConfirmationDetails = {
  expires_at: string
  property_id?: string
  category?: 'LAND' | 'HOUSE' | 'COMMERCIAL'
  area?: string
  agent_name?: string
  selling_price?: string
}

export type Confirmation = { purpose: ConfirmationPurpose; context: Record<string, unknown>; details?: ConfirmationDetails }

export type Bank = { bank_name: string; account_name: string; account_number: string; branch: string }

export type Decision = 'CONFIRM' | 'DECLINE'

function path(delivery: string, consent: boolean) {
  const id = encodeURIComponent(delivery)
  return consent ? `/full-checks/consent/${id}/` : `/payments/confirmations/${id}/`
}

export const confirmApi = {
  open: (delivery: string, token: string, consent = false) =>
    request<Confirmation>(`${path(delivery, consent)}?token=${encodeURIComponent(token)}`),

  decide: (delivery: string, token: string, decision: Decision, extra: { bank?: Bank; bank_reference?: string } = {}, consent = false) =>
    request<{ decision?: string; status?: string }>(path(delivery, consent), {
      method: 'POST',
      body: { token, decision, ...extra },
      headers: { 'Idempotency-Key': idempotencyKey() },
    }),
}
