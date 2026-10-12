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
  tax_receipt_number: string
  tax_receipt: File
}

type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }

export const staffApi = {
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
    for (const [key, value] of Object.entries(input)) form.append(key, value)
    return request<{ receipt_id: string; status: string }>(`/full-checks/${id}/payment-confirm/`, {
      method: 'POST',
      body: form,
      auth: true,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  assignVerifier: (id: string, verifierId: string) =>
    request<FullCheck>(`/full-checks/${id}/verifier/`, { method: 'POST', body: { verifier: verifierId }, auth: true }),

  // FUL-07. "Not completed" is set by the deadline process, not here.
  recordResult: (id: string, result: 'PASSED' | 'PROBLEM_FOUND', riskAssessment: string, notChecked: string[]) =>
    request<unknown>(`/full-checks/${id}/result/`, {
      method: 'POST',
      body: { result, risk_assessment: riskAssessment, not_checked: notChecked },
      auth: true,
    }),
}
