import type { Language } from '../i18n'
import { request } from './api'

export const CATEGORIES = ['LAND', 'HOUSE', 'COMMERCIAL'] as const
export type Category = (typeof CATEGORIES)[number]

export const TITLE_TYPES = [
  'REGISTERED_TITLE',
  'RESIDENTIAL_LICENCE',
  'SALE_AGREEMENT',
  'CCRO',
  'VILLAGE_RECORDS',
  'NONE',
  'UNKNOWN',
] as const
export type TitleType = (typeof TITLE_TYPES)[number]

export const SORTS = ['NEWEST', 'PRICE_ASC', 'PRICE_DESC'] as const
export type Sort = (typeof SORTS)[number]

export const LEVELS = [0, 1, 2, 3] as const
export type Level = (typeof LEVELS)[number]

// Mirrors listings.serializers.ListingPublicSerializer. Owner name, contact,
// bank details and owner's price are never in the public payload (LST-T2).
export type PublicVerification = {
  level: Level
  label: string
  is_verified: boolean
  completed_at?: string
  expires_at?: string
  title_warning?: string
  checks?: {
    name: string
    result: string
    date: string
    expires_at: string
    staff_reference: string
    not_checked: unknown
    partners: { name: string; role: string }[]
  }[]
}

export type PublicListing = {
  listing_id: string
  selling_price: string
  currency: string
  status: 'ACTIVE' | 'UNDER_OFFER'
  description: string
  features: unknown
  created_at: string
  property: {
    property_id: string
    category: Category
    stated_size: string | null
    size_unit: string
    title_type: TitleType
    location: { region: string; district: string; ward: string; locality: string; locality_kind: string }
  }
  lister: {
    display_name: string
    lister_kind: 'OWNER' | 'AGENT'
    verification: PublicVerification
    member_since: string
  }
  photos: { position: number; url: string }[]
}

export type SearchPage = { count: number; next: number | null; previous: number | null; results: PublicListing[] }

// Every filter the backend accepts; it rejects anything else (public_search.py).
export type SearchParams = Partial<{
  category: Category
  region: string
  district: string
  ward: string
  min_price: string
  max_price: string
  min_size: string
  max_size: string
  title_type: TitleType
  min_verification_level: string
  sort: Sort
  page: string
  page_size: string
}>

export const SEARCH_KEYS = [
  'category',
  'region',
  'district',
  'ward',
  'min_price',
  'max_price',
  'min_size',
  'max_size',
  'title_type',
  'min_verification_level',
  'sort',
  'page',
] as const

export type Place = { id: string; name: string }

export type LeadSource = 'ENQUIRY' | 'WHATSAPP_CONTACT' | 'VIEWING_REQUEST'

function query(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value) search.set(key, value)
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const marketApi = {
  search: (params: SearchParams) => request<SearchPage>(`/public/listings/${query(params)}`),

  listing: (listingId: string) => request<PublicListing>(`/public/listings/${encodeURIComponent(listingId)}/`),

  regions: () => request<Place[]>('/localities/regions/'),
  districts: (region: string) => request<Place[]>(`/localities/districts/${query({ region })}`),
  wards: (district: string) => request<Place[]>(`/localities/wards/${query({ district })}`),

  // SRD 20.1 self-service: opens the buyer's own WhatsApp to the lister.
  contactLink: (listingId: string, language: Language) =>
    request<{ whatsapp_link: string }>(
      `/notifications/self-service/listings/${encodeURIComponent(listingId)}/${query({ language })}`,
    ),

  // LEAD-01: needs a signed-in buyer; the API snapshots their name and phone.
  createLead: (listingId: string, source: LeadSource) =>
    request<{ id: string }>('/leads/', { method: 'POST', body: { listing_id: listingId, source }, auth: true }),
}
