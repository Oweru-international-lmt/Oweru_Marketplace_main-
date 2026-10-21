import { idempotencyKey, request } from './api'

// Phase 1 money (LEAD-03 to 05, PAY-01 to 12). The API records bank transfers;
// it never moves money. Every money action sends an Idempotency-Key, and the
// deal read is shaped by role: the buyer sees their slips, the lister the
// split and payout, management everything including the frozen bank details.

export type Transfer = 'OWNER' | 'OWERU'
export type DealState = 'OPEN' | 'COMPLETE' | 'CANCELLED'
export type PaymentStatus = 'AWAITING_PAYMENT' | 'PROOF_UPLOADED' | 'OWNER_CONFIRMED' | 'OWERU_CONFIRMED' | 'BOTH_CONFIRMED' | 'COMPLETE'
export type PayoutStatus = 'PENDING' | 'DUE' | 'ON_HOLD' | 'PAID'

export type DealSteps = {
  created_at: string
  owner_paid_at: string | null
  oweru_paid_at: string | null
  owner_confirmed_at: string | null
  oweru_confirmed_at: string | null
  agreement_uploaded_at: string | null
  agreement_price_confirmed_at: string | null
  agreement_approved_at: string | null
  tax_receipt_at: string | null
  completed_at: string | null
}

export type Bank = { bank_name: string; account_name: string; account_number: string; branch: string }
export type Proof = { transfer: Transfer; media_id: string; uploaded_at: string }

export type DealPayout = {
  status: PayoutStatus
  amount: string
  due_at: string
  paid_at: string | null
  hold_reason: string
  bank_reference: string
  proof_media_id: string | null
}

export type Deal = {
  id: string
  lead_id: string
  listing_id: string
  buyer_name: string
  lister_name: string
  lister_kind: 'OWNER' | 'AGENT'
  final_selling_price: string
  buyer_to_owner: string
  buyer_to_oweru: string
  payment_reference: string
  state: DealState
  payment_status: PaymentStatus
  property: { property_id: string; category: 'LAND' | 'HOUSE' | 'COMMERCIAL'; area: string; cover_url: string | null }
  steps: DealSteps
  agreement_media_id: string | null
  agreement_price_confirmed_at: string | null
  agreement_approved_at: string | null
  tax_receipt: { number: string; kind: 'EFD' | 'VFD'; media_id: string; recorded_at: string } | null
  completed_at: string | null
  created_at: string
  // Lister and management only.
  owner_price?: string
  oweru_keeps?: string
  agent_payout?: string
  payout?: DealPayout | null
  // Buyer and management only.
  proofs?: Proof[]
  // Management only.
  buyer_whatsapp?: string
  confirmations?: { transfer: Transfer; amount: string; bank_reference: string; by_owner_link: boolean; confirmed_at: string }[]
  banks?: { owner: Partial<Bank>; oweru: Partial<Bank> }
}

export type Instructions = {
  deal_id: string
  owner: { amount: string; bank: Partial<Bank> }
  oweru: { amount: string; bank: Partial<Bank>; reference: string }
}

export type PayoutRow = {
  id: string
  deal_id: string
  amount: string
  status: PayoutStatus
  due_at: string
  paid_at: string | null
  hold_reason: string
  bank_reference: string
  listing_id: string
  property_id: string
  final_selling_price: string
  buyer_name: string
  created_at: string
  agent_name?: string
  agent_bank_id?: string | null
}

export type RateBand = { lower: string; upper: string | null; oweru_rate: string; agent_rate: string }
export type RateTable = { id: string; version: number; total_rate: string; published_at: string | null; bands: RateBand[] }

function money(body: unknown) {
  return { method: 'POST' as const, body, auth: true, headers: { 'Idempotency-Key': idempotencyKey() } }
}

function upload(fields: Record<string, string | File>) {
  const form = new FormData()
  for (const [name, value] of Object.entries(fields)) form.append(name, value)
  return money(form)
}

export const dealsApi = {
  list: () => request<Deal[]>('/deals/', { auth: true }),
  get: (id: string) => request<Deal>(`/deals/${id}/`, { auth: true }),
  document: (id: string, mediaId: string) => request<{ url: string }>(`/deals/${id}/documents/${encodeURIComponent(mediaId)}/`, { auth: true }),

  // Buyer (PAY-06, PAY-07).
  instructions: (id: string) => request<Instructions>(`/payments/deals/${id}/instructions/`, { auth: true }),
  submitProof: (id: string, transfer: Transfer, file: File) => request<{ media_id: string }>(`/payments/deals/${id}/proofs/`, upload({ transfer, file })),

  // Lister (LEAD-05, PAY-08 on owner listings).
  uploadAgreement: (id: string, file: File) => request<unknown>(`/deals/${id}/agreement/upload/`, upload({ file })),
  confirmAgreement: (id: string) => request<unknown>(`/deals/${id}/agreement/confirm/`, money({ confirms_exact_final_price: true })),
  confirmOwnerReceipt: (id: string, bankReference: string) => request<unknown>(`/payments/deals/${id}/confirm/owner/`, money({ bank_reference: bankReference })),
  // Agent listings: Oweru sends the owner a WhatsApp link from the outbox (PAY-08).
  requestOwnerReceipt: (id: string) => request<{ delivery_id: string }>('/payments/confirmation-requests/', { method: 'POST', body: { purpose: 'OWNER_RECEIPT', deal_id: id }, auth: true }),
  // The lister shares the buyer's payment page from their own WhatsApp (NTF-03).
  shareInstructions: (id: string) => request<{ whatsapp_link: string }>(`/notifications/self-service/deals/${id}/`, { auth: true }),

  // Management (PAY-09, PAY-11, LEAD-05).
  confirmOweruReceipt: (id: string, bankReference: string) => request<unknown>(`/payments/deals/${id}/confirm/oweru/`, money({ bank_reference: bankReference })),
  approveAgreement: (id: string) => request<unknown>(`/deals/${id}/agreement/approve/`, money({ confirms_exact_final_price: true })),
  recordTaxReceipt: (id: string, number: string, kind: 'EFD' | 'VFD', file: File) => request<unknown>(`/payments/deals/${id}/tax-receipt/`, upload({ number, kind, file })),
  complete: (id: string) => request<unknown>(`/deals/${id}/complete/`, money({})),

  // Payouts (PAY-10, PAY-12).
  payouts: () => request<PayoutRow[]>('/payouts/', { auth: true }),
  holdPayout: (dealId: string, reason: string) => request<unknown>(`/payouts/deals/${dealId}/hold/`, money({ reason })),
  releasePayout: (dealId: string) => request<unknown>(`/payouts/deals/${dealId}/release/`, money({})),
  payPayout: (dealId: string, bankReference: string, file: File) => request<unknown>(`/payouts/deals/${dealId}/paid/`, upload({ bank_reference: bankReference, file })),
  agentBank: (bankId: string) => request<Bank>(`/management/finance/banks/${bankId}/`, { auth: true }),

  // Bank account and rate table (PAY-02, PAY-04).
  bank: () => request<Bank>('/payments/bank-account/', { auth: true }),
  saveBank: (bank: Bank) => request<{ bank_account_id: string }>('/payments/bank-account/', { method: 'PUT', body: bank, auth: true, headers: { 'Idempotency-Key': idempotencyKey() } }),
  rateTable: () => request<RateTable | null>('/commissions/rate-tables/', { auth: true }),
}

// SRD 9.1 with the frozen rate band: what each side gets for a pair of prices.
// Whole shillings; rounding matches CommissionService (half up, residual to Oweru).
// Owner listings: the owner price is the selling price and Oweru takes only its share.
export function splitFor(table: RateTable, ownerPrice: number, sellingPrice: number, kind: 'OWNER' | 'AGENT' = 'AGENT') {
  const band = table.bands.find((row) => sellingPrice >= Number(row.lower) && (row.upper === null || sellingPrice <= Number(row.upper)))
  if (!band || ownerPrice <= 0 || sellingPrice < ownerPrice) return null
  const total = Number(table.total_rate)
  const oweruRate = Number(band.oweru_rate)
  const toOwner = Math.round(kind === 'OWNER' ? sellingPrice * (1 - oweruRate) : ownerPrice * (1 - total))
  const agent = kind === 'OWNER' ? 0 : Math.round(ownerPrice * (total - oweruRate) + (sellingPrice - ownerPrice))
  const toOweru = sellingPrice - toOwner
  return { band, toOwner, toOweru, oweruKeeps: toOweru - agent, agent, totalRate: total, oweruRate, agentRate: Number(band.agent_rate) }
}

// The SRD 9.5 steps in order, for the timelines (D6, D7, D3).
export const DEAL_STEPS = ['created', 'ownerPaid', 'oweruPaid', 'ownerConfirmed', 'oweruConfirmed', 'agreement', 'approved', 'completed'] as const
export type DealStep = (typeof DEAL_STEPS)[number]

export function stepTimes(steps: DealSteps): Record<DealStep, string | null> {
  return {
    created: steps.created_at,
    ownerPaid: steps.owner_paid_at,
    oweruPaid: steps.oweru_paid_at,
    ownerConfirmed: steps.owner_confirmed_at,
    oweruConfirmed: steps.oweru_confirmed_at,
    agreement: steps.agreement_price_confirmed_at,
    approved: steps.agreement_approved_at,
    completed: steps.completed_at,
  }
}

// The first step not yet done, or null when the deal is complete.
export function currentStep(steps: DealSteps): DealStep | null {
  const times = stepTimes(steps)
  return DEAL_STEPS.find((step) => !times[step]) ?? null
}
