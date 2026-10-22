import type { Language } from '../i18n'
import { idempotencyKey, request } from './api'
import type { Category } from './marketApi'

// Public services from SRD sections 21 to 23: the Free Check, complaints and
// the paid Full Check. Free checks and complaints need no account; links to
// them carry a secret token instead.

export type Verdict = { status: 'LAND' | 'OUTSIDE' | 'MATCH' | 'MISMATCH' | 'FOUND' | 'NONE' | 'UNAVAILABLE'; message: string }

// Mirrors free_checks.services.public_result. It never carries coordinates.
export type FreeCheckResult = {
  id: string
  reference: string
  date: string
  description: string
  category: Category
  size: string
  size_unit: string
  verdicts: Partial<Record<'land' | 'duplicates' | 'photos' | 'description_match', Verdict>>
  disclaimer: string
  full_check: string
  expires_at: string
}

export type FreeCheckCreated = FreeCheckResult & { report_link: string; download_path: string; whatsapp_link: string }

export type FreeCheckInput = {
  pin: { type: 'Point'; coordinates: [number, number] }
  category: Category
  size: string
  size_unit: SizeUnit
  description: string
  phone: string
  email?: string
  external_url?: string
  language: Language
  photos: File[]
}

export const SIZE_UNITS = ['sqm', 'acres', 'hectares'] as const
export type SizeUnit = (typeof SIZE_UNITS)[number]

export const COMPLAINT_ROLES = ['buyer', 'owner', 'agent', 'local_official', 'professional', 'other'] as const
export type ComplaintRole = (typeof COMPLAINT_ROLES)[number]

export const COMPLAINT_TYPES = ['FAKE_LISTING', 'WRONG_LISTING', 'CONDUCT', 'PAYMENT', 'PAYOUT', 'PRIVACY', 'VERIFICATION', 'OTHER'] as const
export type ComplaintType = (typeof COMPLAINT_TYPES)[number]

// CMP-05, in the order a complaint moves through them.
export const COMPLAINT_STATUSES = ['RECEIVED', 'IN_REVIEW', 'WAITING_INFORMATION', 'RESOLVED', 'UNDER_FINAL_REVIEW', 'CLOSED'] as const
export type ComplaintStatus = (typeof COMPLAINT_STATUSES)[number]

export type ComplaintSummary = {
  id: string
  reference: string
  status: ComplaintStatus
  outcome: string
  reasons: string
  version: number
  resolution_due_at: string
}

export type ComplaintInput = {
  name: string
  phone: string
  email?: string
  complainant_role: ComplaintRole
  category: ComplaintType
  description: string
  property_reference?: string
  language: Language
  evidence: File[]
}

export const FULL_CHECK_STATUSES = ['AWAITING_PAYMENT', 'AWAITING_CONSENT', 'IN_PROGRESS', 'UNDER_REVIEW', 'PASSED', 'PROBLEM_FOUND', 'NOT_COMPLETED'] as const
export type FullCheckStatus = (typeof FULL_CHECK_STATUSES)[number]

export type FullCheckQuote = { fee: string; scope: string; scope_sw?: string; currency: string; quote: string }

// The scope is frozen in English and Swahili; older checks froze English only.
export type ScopeSnapshot = { scope?: string; scope_sw?: string }

export function scopeText(scope: ScopeSnapshot | undefined, language: string) {
  return (language.startsWith('sw') && scope?.scope_sw) || scope?.scope || ''
}

export type FullCheck = {
  id: string
  kind: 'FULL' | 'OUTSIDE_FULL'
  property_id: string
  status: FullCheckStatus
  fee: string
  scope_snapshot: ScopeSnapshot
  payment_reference: string
  consent_due_at: string | null
  completed_at: string | null
  expires_at: string | null
  refresh_limit_at?: string | null
  invalidated_at: string | null
  created_at: string
  result?: { result: 'PASSED' | 'PROBLEM_FOUND'; risk_assessment: string; not_checked: string[] }
  reports?: { id: string; version: number; language: string }[]
}

// FUL-02: a full check waiting on the signed-in Owner's consent, or on the
// Agent to give the owner's contact.
export type OwnerRequest = {
  kind: 'consent' | 'contact'
  job_id: string
  property_id: string
  area: string
  scope: ScopeSnapshot
  deadline: string
  owner_name: string
}

export type PaymentInstructions = {
  amount: string
  currency: string
  reference: string
  bank: { bank_name: string; account_name: string; account_number: string; branch: string }
}

export type PaymentProofs = { proofs: { id: string; document_id: string; created_at: string }[] }

type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }

// The API returns links that point at itself; screens need only the token.
export function tokenFrom(link: string): string | null {
  try {
    return new URL(link, window.location.origin).searchParams.get('token')
  } catch {
    return null
  }
}

function withToken(path: string, token: string): string {
  return `${path}?${new URLSearchParams({ token }).toString()}`
}

function freeCheckBody(input: FreeCheckInput): FormData | Omit<FreeCheckInput, 'photos'> {
  const { photos, ...values } = input
  if (photos.length === 0) return values
  // Multipart sends every field as text, so the pin travels JSON-encoded.
  const form = new FormData()
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === '') continue
    form.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value))
  }
  for (const photo of photos) form.append('photos', photo)
  return form
}

function complaintBody(input: ComplaintInput): FormData {
  const form = new FormData()
  const { evidence, ...values } = input
  for (const [key, value] of Object.entries(values)) if (value) form.append(key, value)
  for (const file of evidence) form.append('evidence', file)
  return form
}

export const servicesApi = {
  // FRC-01. The key is made once per form, so a retried submit is not a second check.
  submitFreeCheck: (input: FreeCheckInput, key: string) =>
    request<FreeCheckCreated>('/free-checks/', { method: 'POST', body: freeCheckBody(input), headers: { 'Idempotency-Key': key } }),

  freeCheck: (id: string, token: string) => request<FreeCheckResult>(withToken(`/free-checks/${id}/`, token)),

  freeCheckPdf: (id: string, token: string) => request<{ url: string; reference: string }>(withToken(`/free-checks/${id}/pdf/`, token)),

  // CMP-01: no sign-in. Always multipart, since evidence files are optional.
  lodgeComplaint: (input: ComplaintInput) =>
    request<ComplaintSummary & { status_link: string }>('/complaints/', { method: 'POST', body: complaintBody(input) }),

  complaint: (id: string, token: string) => request<ComplaintSummary>(withToken(`/complaints/${id}/status/`, token)),

  replyToComplaint: (id: string, token: string, text: string, evidence: File[]) => {
    const form = new FormData()
    form.append('token', token)
    form.append('text', text)
    for (const file of evidence) form.append('evidence', file)
    return request<{ id: string }>(`/complaints/${id}/response/`, { method: 'POST', body: form })
  },

  // CMP-07: the complainant may ask the Director to review a resolution.
  requestFinalReview: (id: string, token: string, reason: string) =>
    request<ComplaintSummary>(`/complaints/${id}/final-review/`, { method: 'POST', body: { token, reason } }),

  // FUL-01: the fee and scope are shown, and signed, before ordering.
  fullCheckQuote: () => request<FullCheckQuote>('/full-checks/quote/'),

  orderFullCheck: (listingId: string, quote: string, key: string) =>
    request<{ job_id: string; status: FullCheckStatus; fee: string; payment_reference: string }>('/full-checks/', {
      method: 'POST',
      body: { listing_id: listingId, quote_token: quote },
      auth: true,
      headers: { 'Idempotency-Key': key },
    }),

  fullChecks: () => request<Page<FullCheck>>('/full-checks/', { auth: true }),

  fullCheck: (id: string) => request<FullCheck>(`/full-checks/${id}/`, { auth: true }),

  paymentInstructions: (id: string) => request<PaymentInstructions>(`/full-checks/${id}/instructions/`, { auth: true }),

  paymentProofs: (id: string) => request<PaymentProofs>(`/full-checks/${id}/proof/`, { auth: true }),

  uploadPaymentProof: (id: string, file: File) => {
    const form = new FormData()
    form.append('upload', file)
    return request<{ proof_id: string }>(`/full-checks/${id}/proof/`, {
      method: 'POST',
      body: form,
      auth: true,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  paymentDocument: (id: string, documentId: string) => request<{ url: string }>(`/full-checks/${id}/payment-documents/${documentId}/`, { auth: true }),

  ownerRequests: () => request<OwnerRequest[]>('/full-checks/requests/', { auth: true }),

  ownerConsent: (id: string, decision: 'CONFIRM' | 'DECLINE') =>
    request<{ consent_id: string; status: FullCheckStatus }>(`/full-checks/${id}/owner-consent/`, { method: 'POST', body: { decision }, auth: true }),

  ownerContact: (id: string, ownerName: string, ownerPhone: string) =>
    request<{ job_id: string; status: FullCheckStatus }>(`/full-checks/${id}/owner-contact/`, { method: 'POST', body: { owner_name: ownerName, owner_phone: ownerPhone }, auth: true }),

  refreshFullCheck: (id: string, riskAssessment: string) =>
    request<FullCheck>(`/full-checks/${id}/refresh/`, { method: 'POST', body: { risk_assessment: riskAssessment }, auth: true }),

  fullCheckReport: (id: string, reportId: string) => request<{ url: string; version: number }>(`/full-checks/${id}/reports/${reportId}/`, { auth: true }),
}
