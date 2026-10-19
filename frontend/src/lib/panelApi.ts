import { request, requestBlob } from './api'

// SRD 18 and 19: the non-personal market panel (apps.analytics) and the
// Marketer's tools (apps.marketing). The panel only ever returns counts by
// administrative area; no names, phones or exact pins (MON-03).

export type PanelKind = 'STOCK' | 'ACTIVITY' | 'COVERAGE' | 'MONTHLY'
export type Stats = { count: number; average: number | null; median: number | null }
export type PanelRow = {
  day: string
  kind: PanelKind
  region: string | null
  district: string | null
  ward: string | null
  category: string
  metrics: Record<string, unknown> & {
    active_listings?: number
    selling_price?: Stats
    price_per_sqm?: Stats
    verification_mix?: Record<string, number>
    searches?: number
    views?: number
    enquiries?: number
    enquiry_events?: number
    won_deals?: number
    cohort_stages?: Record<string, number>
    first_enquiry_days_sum?: number
    first_enquiry_count?: number
    sale_days_sum?: number
    sale_count?: number
    demand_price_ranges?: Record<string, number>
    sources_search?: Record<string, number>
    sources_view?: Record<string, number>
    sources_enquiry?: Record<string, number>
    sources_won?: Record<string, number>
  }
}
export type Panel = { areas: Record<string, string>; generated_at: string | null; stale: boolean; rows: PanelRow[]; limitations: string[] }
export type PanelFilters = { start: string; end: string; region?: string; district?: string; category?: string }

export type Campaign = {
  id: string
  source_tag: string
  subject_en: string
  subject_sw: string
  target_path: string
  created_at: string
  recipients: number
  sent: number
  failed: number
  cancelled: number
  clicks: number
}
export type CampaignInput = { subject_en: string; subject_sw: string; body_en: string; body_sw: string; target_path: string; source_tag: string }

export type Featured = {
  id: string
  version: number
  enabled: boolean
  starts_at: string
  ends_at: string
  listing_id: string
  listing_status: string
  category: string
  selling_price: number
  area: string
  cover_url: string | null
}
export type Content = {
  id: string
  version: number
  slug: string
  kind: 'BANNER' | 'PAGE'
  title_en: string
  title_sw: string
  body_en: string
  body_sw: string
  target_path: string
  source_tag: string
  starts_at: string
  ends_at: string
  enabled: boolean
  created_at: string
}
export type ContentInput = Omit<Content, 'id' | 'created_at'>
export type Region = { id: string; name: string }
export type District = { id: string; name: string; region: string }

function query(filters: PanelFilters) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value)
  return params.toString()
}

export const panelApi = {
  panel: (filters: PanelFilters) => request<Panel>(`/analytics/?${query(filters)}`, { auth: true }),
  exportPanel: (filters: PanelFilters) => requestBlob(`/analytics/export/?${query(filters)}`),
  regions: () => request<Region[] | { results: Region[] }>('/localities/regions/', { auth: true }),
  districts: (region: string) => request<District[] | { results: District[] }>(`/localities/districts/?region=${region}`, { auth: true }),

  campaigns: () => request<Campaign[]>('/marketing/staff/campaigns/', { auth: true }),
  sendCampaign: (input: CampaignInput) =>
    request<{ id: string; recipients: number }>('/marketing/staff/campaigns/', { method: 'POST', body: input, auth: true }),

  featured: () => request<Featured[]>('/marketing/staff/featured/', { auth: true }),
  saveFeatured: (values: { listing_id: string; starts_at: string; ends_at: string; enabled: boolean; version: number }, id?: string) =>
    request<{ id: string; version: number }>(`/marketing/staff/featured/${id ? `${id}/` : ''}`, { method: 'POST', body: values, auth: true }),

  content: () => request<Content[]>('/marketing/staff/content/', { auth: true }),
  saveContent: (values: ContentInput, id?: string) =>
    request<{ id: string; version: number }>(`/marketing/staff/content/${id ? `${id}/` : ''}`, { method: 'POST', body: values, auth: true }),
}

export function list<T>(value: T[] | { results: T[] }): T[] {
  return Array.isArray(value) ? value : value.results
}
