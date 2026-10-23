import { request } from './api'
import type { Category, PublicListing } from './marketApi'

// Phase 6: the public lister profile (IDV-06), the lister's customers and
// notes (LEAD-02, LEAD-06), a buyer's own enquiries (SRD 24), screen
// notifications (NTF-01) and marketing consent (MAR-03).

export type ListerProfile = {
  id: string
  name: string
  is_verified: boolean
  lister_roles: ('owner' | 'agent')[]
  member_since: string
  areas: { district: string; region: string }[]
  property_types: Category[]
  listings: PublicListing[]
}

export type LeadSource = 'ENQUIRY' | 'WHATSAPP_CONTACT' | 'VIEWING_REQUEST'
export type CustomerNote = { id: string; text: string; actor_id: string; created_at: string }
export type CustomerLead = { id: string; stage: string; source: LeadSource; listing_id: string; category: Category; area: string; created_at: string; follow_up_at: string | null; notes: CustomerNote[] }
export type Customer = { name: string; whatsapp: string; leads: CustomerLead[]; last_activity: string }

export type MyEnquiry = { id: string; listing_id: string; category: Category; area: string; source: LeadSource; created_at: string; deal_id: string | null }

export type ScreenNotice = { id: string; purpose: string; message: string; created_at: string; read_at: string | null }

export const peopleApi = {
  profile: (id: string) => request<ListerProfile>(`/listers/${encodeURIComponent(id)}/`),

  customers: () => request<Customer[]>('/leads/customers/', { auth: true }),
  addNote: (leadId: string, text: string) => request<CustomerNote>(`/leads/${leadId}/notes/`, { method: 'POST', body: { text }, auth: true }),
  myEnquiries: () => request<MyEnquiry[]>('/leads/mine/', { auth: true }),

  notifications: () => request<ScreenNotice[]>('/notifications/', { auth: true }),
  markRead: (id: string) => request<{ id: string; read_at: string }>(`/notifications/${id}/read/`, { method: 'POST', auth: true }),

  consent: () => request<{ agreed: boolean; version: number }>('/marketing/consent/', { auth: true }),
  saveConsent: (agreed: boolean, version: number) =>
    request<{ agreed: boolean; version: number }>('/marketing/consent/', { method: 'PUT', body: { agreed, version, policy_version: 'marketing-2026-10' }, auth: true }),
}
