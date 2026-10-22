import { idempotencyKey, request } from './api'
import type { ComplaintStatus, ComplaintType, FullCheck } from './servicesApi'

// Staff side of the public services: the complaints desk (CMP-02 to CMP-08)
// and full check payment confirmation and results (PAY-13, FUL-07).

export type ComplaintRoute = 'HEAD_OPERATIONS' | 'MANAGEMENT' | 'VERIFIER' | 'DIRECTOR'

// Mirrors complaints.api.DeskView's list rows.
export type DeskComplaint = {
  id: string
  reference: string
  status: ComplaintStatus
  outcome: string
  reasons: string
  version: number
  resolution_due_at: string
  name: string
  category: ComplaintType
  created_at: string
  route: ComplaintRoute
  overdue: boolean
}

export type ComplaintHistoryEntry = { status: ComplaintStatus; reason: string; version: number; created_at: string }

// Mirrors DeskView's detail.
export type DeskComplaintDetail = {
  id: string
  reference: string
  status: ComplaintStatus
  outcome: string
  reasons: string
  version: number
  resolution_due_at: string
  name: string
  phone: string
  description: string
  category: ComplaintType
  handler: string | null
  evidence: string[]
  responses: { text: string; from_complainant: boolean; date: string }[]
  history: ComplaintHistoryEntry[]
}

// complaints.services.EDGES: where each status may go next.
export const NEXT_STATUSES: Record<ComplaintStatus, ComplaintStatus[]> = {
  RECEIVED: ['IN_REVIEW'],
  IN_REVIEW: ['WAITING_INFORMATION', 'RESOLVED'],
  WAITING_INFORMATION: ['IN_REVIEW', 'RESOLVED'],
  RESOLVED: ['CLOSED'],
  UNDER_FINAL_REVIEW: ['CLOSED'],
  CLOSED: [],
}

export type Transition = { status: ComplaintStatus; version: number; reason: string; outcome?: string }

export type PaymentConfirmation = {
  amount: string
  reference: string
  bank_reference: string
  // D3: optional; a copy needs its number.
  tax_receipt_number?: string
  tax_receipt?: File | null
}

type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }

// IDV-03: lister identities waiting for Management, oldest first.
export type IdentityQueueItem = {
  id: string
  user_id: string
  user_full_name: string
  status: 'PENDING'
  submitted_at: string
  created_at: string
  updated_at: string
}

// Mirrors lister_identity ListerIdentityManagementSerializer.
export type IdentityReview = {
  id: string
  user_id: string
  user_full_name: string
  national_id_number: string
  national_id_photo_ref: string
  live_selfie_ref: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED'
  submitted_at: string | null
  reviewed_at: string | null
  reviewed_by_id: string | null
  review_reason: string
  expires_at: string | null
  created_at: string
  updated_at: string
  whatsapp_confirmed: boolean
}

export type IdentityPhoto = 'national_id_photo' | 'live_selfie'

// NTF-02: one row of the central staff outbox (notifications.services.outbox_payload).
export type OutboxMessage = {
  id: string
  recipient_name: string
  phone: string
  purpose: string
  message: string
  language: string
  created_at: string
  created_by: string | null
  sent_by: string | null
  sent_at: string | null
  status: 'WAITING' | 'SENT'
  overdue: boolean
  whatsapp_link: string
}

// VER-02: the verifier's location check desk (verification.review_desk).
export type CheckPoint = 'pin_on_land' | 'photos_match' | 'no_conflicting_duplicate' | 'description_fits'
export type CheckStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'REVOKED'
export type LatLng = { lat: number; lng: number }

export type LocationCheckRow = {
  id: string
  property_id: string
  status: CheckStatus
  submitted_at: string
  reviewed_at: string | null
  expires_at: string | null
  category: 'LAND' | 'HOUSE' | 'COMMERCIAL'
  title_type: string
  stated_size: string
  size_unit: string
  area: string
  lister_name: string
  cover_url: string | null
  duplicate_count: number
  late: boolean
}

export type PossibleDuplicate = {
  id: string
  property_id: string
  status: 'PENDING' | 'CONFIRMED_DUPLICATE' | 'NOT_DUPLICATE'
  signals: string[]
  distance_meters: number | null
  size_difference_percent: number | null
  category: string
  stated_size: number
  size_unit: string
  area: string
  pin: LatLng | null
  cover_url: string | null
}

export type LocationCheck = LocationCheckRow & {
  reason: string | null
  reviewer_name: string | null
  pin: LatLng | null
  boundary: LatLng[] | null
  listing: { listing_id: string; status: string; lister_kind: 'OWNER' | 'AGENT'; description: string; features: string[]; photo_count: number } | null
  documents: { id: string; evidence_type: string; created_at: string }[]
  duplicates: PossibleDuplicate[]
  checklist: CheckPoint[]
}

export type CheckSummary = { waiting: number; late: number; passed_this_month: number; failed_this_month: number }
export type Checklist = Record<CheckPoint, boolean>

export const staffApi = {
  checkSummary: () => request<CheckSummary>('/management/verifications/documents/summary/', { auth: true }),
  checks: (state: 'waiting' | 'decided') =>
    request<Page<LocationCheckRow>>(`/management/verifications/documents/?page_size=100${state === 'decided' ? '&state=decided' : ''}`, { auth: true }),
  check: (id: string) => request<LocationCheck>(`/management/verifications/documents/${id}/`, { auth: true }),
  checkPhotos: (id: string) => request<{ position: number; url: string }[]>(`/management/verifications/documents/${id}/photos/`, { auth: true }),
  // Each opening is recorded as sensitive access; the link is short-lived.
  checkDocument: (id: string, documentId: string) =>
    request<{ url: string; expires_in: number; mime_type: string }>(`/management/verifications/documents/${id}/evidence/${documentId}/`, { auth: true }),
  passCheck: (id: string, checklist: Checklist) =>
    request<LocationCheck>(`/management/verifications/documents/${id}/approve/`, { method: 'POST', body: { checklist }, auth: true }),
  failCheck: (id: string, reason: string, checklist?: Checklist) =>
    request<LocationCheck>(`/management/verifications/documents/${id}/reject/`, { method: 'POST', body: checklist ? { reason, checklist } : { reason }, auth: true }),

  complaints: () => request<DeskComplaint[]>('/management/complaints/', { auth: true }),

  complaint: (id: string) => request<DeskComplaintDetail>(`/management/complaints/${id}/`, { auth: true }),

  evidence: (id: string, evidenceId: string) => request<{ url: string }>(`/management/complaints/${id}/evidence/${evidenceId}/`, { auth: true }),

  respond: (id: string, text: string, files: File[]) => {
    const form = new FormData()
    form.append('text', text)
    for (const file of files) form.append('evidence', file)
    return request<{ id: string }>(`/management/complaints/${id}/response/`, { method: 'POST', body: form, auth: true })
  },

  // CMP-07: a reason always; an outcome when resolving or closing a final review.
  transition: (id: string, change: Transition) =>
    request<DeskComplaint>(`/management/complaints/${id}/transition/`, { method: 'POST', body: { outcome: '', ...change }, auth: true }),

  assign: (id: string, handlerId: string, version: number, escalate = false) =>
    request<DeskComplaint>(`/management/complaints/${id}/assign/`, { method: 'POST', body: { handler_id: handlerId, version, escalate }, auth: true }),

  // Management sees every full check; a Verifier sees the ones assigned to them.
  fullChecks: () => request<Page<FullCheck>>('/full-checks/?page_size=100', { auth: true }),

  confirmPayment: (id: string, input: PaymentConfirmation) => {
    const form = new FormData()
    for (const [key, value] of Object.entries(input)) if (value) form.append(key, value)
    return request<{ receipt_id: string; status: string }>(`/full-checks/${id}/payment-confirm/`, {
      method: 'POST',
      body: form,
      auth: true,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  assignVerifier: (id: string, verifierId: string) =>
    request<FullCheck>(`/full-checks/${id}/verifier/`, { method: 'POST', body: { verifier: verifierId }, auth: true }),

  identities: () => request<IdentityQueueItem[]>('/management/lister-identities/', { auth: true }),
  identity: (id: string) => request<IdentityReview>(`/management/lister-identities/${id}/`, { auth: true }),
  // A short-lived signed link; ask again when it runs out.
  identityPhoto: (id: string, kind: IdentityPhoto) =>
    request<{ url: string; expires_in: number }>(`/management/lister-identities/${id}/evidence/${kind}/`, { auth: true }),
  approveIdentity: (id: string) => request<IdentityReview>(`/management/lister-identities/${id}/approve/`, { method: 'POST', body: {}, auth: true }),
  rejectIdentity: (id: string, reason: string) =>
    request<IdentityReview>(`/management/lister-identities/${id}/reject/`, { method: 'POST', body: { reason }, auth: true }),

  // Waiting messages, or the last 100 sent with history.
  outbox: (history = false) => request<OutboxMessage[]>(`/management/notifications/outbox/${history ? '?history=1' : ''}`, { auth: true }),
  // Staff send it from their own WhatsApp first; this only records that it went.
  markSent: (id: string) =>
    request<{ id: string; status: string; sent_at: string }>(`/management/notifications/outbox/${id}/sent/`, { method: 'POST', auth: true }),

  // FUL-07. "Not completed" is set by the deadline process, not here.
  recordResult: (id: string, result: 'PASSED' | 'PROBLEM_FOUND', riskAssessment: string, notChecked: string[]) =>
    request<unknown>(`/full-checks/${id}/result/`, {
      method: 'POST',
      body: { result, risk_assessment: riskAssessment, not_checked: notChecked },
      auth: true,
    }),
}
