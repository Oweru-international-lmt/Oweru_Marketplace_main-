import { idempotencyKey, request } from './api'

// Phase 5: management administration (ADM-01 to ADM-05, LST-03, LST-12,
// NTF-04, PAY-01, D5).

export type OldestItem = { queue: string; reference: string; since: string; link: string }

export type Dashboard = {
  identities_to_approve: number
  duplicates: number
  flagged_listings: number
  partner_approvals: { count: number; available: boolean }
  localities_to_approve: number
  tasks_needing_official: number
  full_check_payments_to_confirm: number
  deal_payments_to_confirm: number
  payouts_due: number
  payouts_on_hold: number
  complaints_by_status: Record<string, number>
  overdue_complaints: number
  outbox_waiting: number
  oldest: OldestItem[]
}

export type SettingValue = number | string | null
export type SettingRow = { key: string; value: SettingValue; version: number; changed_by: string; changed_at: string | null }
export type Band = { lower: string; upper: string | null; oweru_rate: string; agent_rate: string }
export type Examples = {
  rate_table: { total_rate: string; bands: Band[] }
  full_check_fee: number
  full_check_fee_parts: { key: string; amount: number }[]
}
export type SettingsPayload = { settings: SettingRow[]; is_director: boolean; examples: Examples }
export type SettingHistory = { key: string; value: SettingValue; version: number; history: { version: number; value: SettingValue; created_at: string; actor: string }[] }

export type RateTable = { id: string; version: number; total_rate: string; published_at: string | null; bands: Band[]; current: boolean; published_by: string }
export type Bank = { bank_name: string; account_name: string; account_number: string; branch: string; updated_at?: string }

export type AuditRow = { id: string; actor_id: string | null; actor: string; action: string; entity_type: string; entity_id: string; before: Record<string, unknown>; after: Record<string, unknown>; created_at: string }
export type AuditPage = { results: AuditRow[]; page: number; has_next: boolean; groups: string[] }
export type AuditFilters = { q?: string; action?: string; actor?: string; date_from?: string; date_to?: string; page?: number }

export type PendingLocality = {
  id: string
  name: string
  kind: 'street' | 'village'
  ward: string
  district: string
  region: string
  created_at: string
  created_by: string
  properties: number
  approved_in_ward: { id: string; name: string; kind: 'street' | 'village' }[]
}

export type DuplicateSide = {
  property_id: string
  category: string
  region: string
  district: string
  ward: string
  locality: string
  locality_kind: string
  stated_size: string
  size_unit: string
  title_type: string
  created_at: string
  created_by: string
  listings: { listing_id: string; status: string; lister: string; lister_kind: 'OWNER' | 'AGENT'; created_at: string; photos: string[] }[]
}
export type Duplicate = {
  id: string
  status: 'PENDING' | 'CONFIRMED_DUPLICATE' | 'NOT_DUPLICATE'
  signals: string[]
  distance_meters: string | null
  size_difference_percent: string | null
  created_at: string
  reviewed_at: string | null
  property_a: DuplicateSide
  property_b: DuplicateSide
}

export type Template = {
  key: string
  title: { en: string; sw: string }
  version: number
  en: string
  sw: string
  default: { en: string; sw: string }
  history: { version: number; en: string; sw: string; actor: string; created_at: string }[]
}

export type ListingLookup = { listing_id: string; status: string; property_id: string; category: string; area: string; lister: string; lister_kind: 'OWNER' | 'AGENT'; created_at: string; version: string }

type Paged<T> = T[] | { results: T[] }
const list = <T,>(value: Paged<T>) => (Array.isArray(value) ? value : value.results)

function query(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== '') search.set(key, String(value))
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const adminApi = {
  dashboard: () => request<Dashboard>('/management/dashboard/', { auth: true }),

  settings: () => request<SettingsPayload>('/management/settings/', { auth: true }),
  settingHistory: (key: string) => request<SettingHistory>(`/management/settings/${key}/`, { auth: true }),
  saveSetting: (key: string, value: SettingValue, version: number) => request<{ key: string; value: SettingValue; version: number }>(`/management/settings/${key}/`, { method: 'PUT', body: { value, version }, auth: true }),

  rateVersions: () => request<RateTable[]>('/commissions/rate-tables/versions/', { auth: true }),
  saveRateDraft: (body: { version: number; total_rate: string; bands: Band[] }, id?: string) =>
    request<RateTable>(id ? `/commissions/rate-tables/${id}/` : '/commissions/rate-tables/', { method: id ? 'PUT' : 'POST', body, auth: true }),
  publishRate: (id: string) => request<RateTable>(`/commissions/rate-tables/${id}/publish/`, { method: 'POST', body: {}, auth: true }),

  oweruBank: () => request<Bank | null>('/management/finance/oweru-bank/', { auth: true }),
  saveOweruBank: (bank: Bank) => request<{ bank_account_id: string }>('/management/finance/oweru-bank/', { method: 'PUT', body: bank, auth: true, headers: { 'Idempotency-Key': idempotencyKey() } }),

  audit: (filters: AuditFilters) => request<AuditPage>(`/management/audit/${query(filters)}`, { auth: true }),

  pendingLocalities: () => request<PendingLocality[]>('/localities/review-queue/', { auth: true }),
  approveLocality: (id: string) => request<unknown>(`/localities/${id}/approve/`, { method: 'POST', auth: true }),
  mergeLocality: (id: string, into: string) => request<{ properties_moved: number }>(`/localities/${id}/merge/`, { method: 'POST', body: { into }, auth: true }),

  duplicates: (status = 'PENDING') => request<Paged<Duplicate>>(`/management/property-duplicates/?status=${status}`, { auth: true }).then(list),
  duplicate: (id: string) => request<Duplicate>(`/management/property-duplicates/${id}/`, { auth: true }),
  decideDuplicate: (id: string, action: 'confirm' | 'dismiss') => request<Duplicate>(`/management/property-duplicates/${id}/${action}/`, { method: 'POST', body: {}, auth: true }),

  templates: () => request<Template[]>('/management/notifications/message-templates/', { auth: true }),
  saveTemplate: (key: string, en: string, sw: string, version: number) => request<{ key: string; version: number }>(`/management/notifications/message-templates/${key}/`, { method: 'PUT', body: { en, sw, version }, auth: true }),

  listing: (id: string) => request<ListingLookup>(`/management/listing-actions/${encodeURIComponent(id)}/`, { auth: true }),
  listingAction: (id: string, version: string, reason: string, action: 'suspend' | 'restore') =>
    request<{ listing_id: string; status: string; version: string }>(`/management/listing-actions/${encodeURIComponent(id)}/`, { method: 'POST', body: { version, reason, action }, auth: true }),
}
