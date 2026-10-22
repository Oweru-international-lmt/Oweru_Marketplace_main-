import { request } from './api'
import type { ProfessionalType } from './tasksApi'

// Phase 3: local officials (LOC-01, LOC-06, LOC-07, SRD 14.2) and
// professionals (PRO-01) as management sees them.

export type Place = { id: string; name: string; kind: 'street' | 'village'; ward: string; district: string; region: string }
export type OfficialStatus = 'AWAITING_APPROVAL' | 'ACTIVE' | 'DEACTIVATED'
export type Position = 'MWENYEKITI' | 'MTENDAJI'

export type Official = {
  official_id: string
  name: string
  phone: string
  email: string
  position: Position | ''
  status: OfficialStatus
  national_id: string
  locality: Place | null
  covers: string[]
  documents: { received: number; total: number }
  has_photo: boolean
  has_stamp: boolean
  confirmed_by: string
  confirmed_at: string | null
  deactivated_reason: string
  created_at: string
}

export type Invite = {
  id: string
  locality: Place
  phone: string
  status: 'INVITED' | 'EXPIRED' | 'REGISTERED' | 'CANCELLED'
  expires_at: string
  created_at: string
  invited_by: string
  replaces: { official_id: string; name: string } | null
  delivery?: { link: string; message: string; whatsapp_link: string }
}

export type ProfessionalRow = {
  id: string
  name: string
  professional_type: ProfessionalType
  registration_number: string
  status: 'ACTIVE' | 'INACTIVE'
  regions: string[]
  districts: string[]
  region_names: string[]
  district_names: string[]
  phone: string
  email: string
  national_id: string
  verified_by: string
  verified_at: string
  created_at: string
}

export type CoverageRow = { id: string; name: string; localities: number; covered: number; officials: number; waiting: number; professionals: Partial<Record<ProfessionalType, number>> }
export type Coverage = { level: 'region' | 'district' | 'ward' | 'locality'; crumbs: { id: string; name: string }[]; rows: CoverageRow[]; professionals: Partial<Record<ProfessionalType, number>> }

type Paged<T> = { results: T[]; next: string | null }

async function allPages<T>(path: string): Promise<T[]> {
  const rows: T[] = []
  let page = 1
  for (;;) {
    const data = await request<Paged<T>>(`${path}${path.includes('?') ? '&' : '?'}page=${page}&page_size=100`, { auth: true })
    rows.push(...data.results)
    if (!data.next) return rows
    page += 1
  }
}

const base = '/management/local-officials'

export const partnersApi = {
  officials: () => request<Official[]>(`${base}/overview/`, { auth: true }),
  invites: () => request<Invite[]>(`${base}/invites/`, { auth: true }),
  invite: (locality: string, phone: string) => request<Invite>(`${base}/invites/`, { method: 'POST', body: { locality, phone }, auth: true }),
  resend: (id: string) => request<Invite>(`${base}/invites/${id}/resend/`, { method: 'POST', auth: true }),
  cancel: (id: string) => request<Invite>(`${base}/invites/${id}/cancel/`, { method: 'POST', auth: true }),
  approve: (officialId: string) => request<Official>(`${base}/${officialId}/approve/`, { method: 'POST', auth: true }),
  deactivate: (officialId: string, reason: string, replacementPhone: string) =>
    request<{ official: Official; invite?: Invite }>(`${base}/${officialId}/deactivate/`, { method: 'POST', body: { reason, ...(replacementPhone ? { replacement_phone: replacementPhone } : {}) }, auth: true }),
  photo: (officialId: string, kind: 'photo' | 'stamp') => request<{ url: string }>(`${base}/${officialId}/photos/${kind}/`, { auth: true }),
  coverage: (scope: { region?: string; district?: string; ward?: string }) => {
    const query = new URLSearchParams(Object.entries(scope).filter(([, value]) => value) as [string, string][]).toString()
    return request<Coverage>(`${base}/coverage/${query ? `?${query}` : ''}`, { auth: true })
  },

  professionals: () => allPages<ProfessionalRow>('/management/professionals/'),
  registerProfessional: (body: { full_name: string; email: string; phone: string; professional_type: ProfessionalType; registration_number: string; national_id_number: string; regions: string[]; districts: string[] }) =>
    request<ProfessionalRow>('/management/professionals/', { method: 'POST', body, auth: true }),
  updateProfessional: (id: string, body: { status?: 'ACTIVE' | 'INACTIVE'; reason?: string; regions?: string[]; districts?: string[] }) =>
    request<ProfessionalRow>(`/management/professionals/${id}/`, { method: 'PATCH', body, auth: true }),

  localities: (ward: string) => request<{ id: string; name: string; kind: 'street' | 'village' }[] | Paged<{ id: string; name: string; kind: 'street' | 'village' }>>(`/localities/?ward=${ward}`),
}

// SRD 14.2: the official's own one-time registration link (no sign-in).
export const registrationApi = {
  get: (token: string) => request<{ locality: Place; phone: string; expires_at: string; replacement: boolean }>(`/local-official/register/${encodeURIComponent(token)}/`),
  submit: (token: string, values: { full_name: string; position: Position; national_id_number: string; email: string; password: string; photo: File; stamp_photo: File }) => {
    const form = new FormData()
    for (const [key, value] of Object.entries(values)) form.append(key, value)
    return request<{ official_id: string; status: OfficialStatus }>(`/local-official/register/${encodeURIComponent(token)}/`, { method: 'POST', body: form })
  },
}
