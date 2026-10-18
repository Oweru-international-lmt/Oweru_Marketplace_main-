import { ApiError, idempotencyKey, request } from './api'
import type { Category, LeadSource, Place, TitleType } from './marketApi'

// The lister's side of the marketplace: property records, listings and their
// photos (LST-01 to LST-09), identity (IDV-01 to IDV-04) and leads (LEAD-02 to LEAD-06).

export type ListerKind = 'OWNER' | 'AGENT'
export type ListingStatus = 'DRAFT' | 'ACTIVE' | 'UNDER_OFFER' | 'SOLD' | 'WITHDRAWN' | 'SUSPENDED'
export type LocalityKind = 'street' | 'village'
export type GeoPoint = { type: 'Point'; coordinates: [number, number] }

// Mirrors properties.serializers.PropertyRecordPrivateSerializer.
export type PropertyRecord = {
  property_id: string
  category: Category
  pin: GeoPoint | null
  region: string
  district: string
  ward: string
  locality: { id: string; name: string; kind: LocalityKind; approved: boolean } | null
  stated_size: string | null
  size_unit: string
  title_type: TitleType
  created_at: string
  updated_at: string
}

export type PropertyInput = {
  category: Category
  pin: GeoPoint
  region: string
  district: string
  ward: string
  locality_name?: string
  locality_kind?: LocalityKind
  stated_size: string
  size_unit: string
  title_type: TitleType
}

// Mirrors listings.serializers.ListingPrivateSerializer.
export type Listing = {
  listing_id: string
  property_id: string
  lister_kind: ListerKind
  selling_price: string
  owner_price: string
  currency: string
  status: ListingStatus
  description: string
  features: unknown
  created_at: string
  updated_at: string
}

export type ListingInput = {
  selling_price: string
  owner_price: string
  description: string
  features: string[]
}

export type ListingPhoto = { id: string; media_id: string; position: number; created_at: string }

// Mirrors verification.serializers.PropertyVerificationListerSerializer.
export type PropertyCheck = {
  id: string
  kind: 'DOCUMENT' | 'FIELD'
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'REVOKED'
  submitted_at: string
  reviewed_at: string | null
  expires_at: string | null
  reason?: string | null
}
export type PropertyCheckStatus = { effective_verification_level: number; verifications: PropertyCheck[] }

// activate_listing's refusal codes.
export type ActivationBlocker = 'lister_identity_verified' | 'listing_required_media' | 'lister_phone_confirmed' | 'listing_frozen_rate_version'
export const MINIMUM_PHOTOS = 3
// Our own cap, to keep uploads sensible on slow connections.
export const MAXIMUM_PHOTOS = 10

export type IdentityStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED'

// Mirrors lister_identity.serializers.ListerIdentityPrivateSerializer.
export type ListerIdentity = {
  id: string
  national_id_number: string
  national_id_photo_ref: string
  live_selfie_ref: string
  status: IdentityStatus
  submitted_at: string | null
  reviewed_at: string | null
  review_reason: string
  expires_at: string | null
  created_at: string
  // ACC-01: the account's WhatsApp number has been confirmed by link.
  whatsapp_confirmed: boolean
}

export type EvidenceKind = 'national_id_photo' | 'live_selfie'

export type LeadStage = 'NEW' | 'CONTACTED' | 'VIEWING' | 'NEGOTIATION' | 'CLOSING' | 'WON' | 'LOST'

export type Lead = {
  id: string
  listing_id: string
  buyer_name: string
  buyer_whatsapp: string
  source: LeadSource
  stage: LeadStage
  follow_up_at: string | null
  created_at: string
  updated_at: string
}

// leads.services.LeadTransitionService.NEXT; Lost is open until Won or Lost.
export const NEXT_STAGE: Partial<Record<LeadStage, LeadStage>> = {
  NEW: 'CONTACTED',
  CONTACTED: 'VIEWING',
  VIEWING: 'NEGOTIATION',
  NEGOTIATION: 'CLOSING',
}
export const OPEN_STAGES: LeadStage[] = ['NEW', 'CONTACTED', 'VIEWING', 'NEGOTIATION', 'CLOSING']

export type LeadMetrics = { enquiries: number; viewings: number; won_deals: number; stage_counts: Record<LeadStage, number> }

// Names for region, district and ward ids; they never change, so ask once.
const placeNames = new Map<string, Promise<string>>()

function placeName(kind: 'regions' | 'districts' | 'wards', id: string): Promise<string> {
  const key = `${kind}:${id}`
  let name = placeNames.get(key)
  if (!name) {
    name = request<Place>(`/localities/${kind}/${id}/`).then((place) => place.name)
    name.catch(() => placeNames.delete(key))
    placeNames.set(key, name)
  }
  return name
}

export async function propertyPlace(record: PropertyRecord): Promise<{ region: string; district: string; ward: string }> {
  const [region, district, ward] = await Promise.all([
    placeName('regions', record.region),
    placeName('districts', record.district),
    placeName('wards', record.ward),
  ])
  return { region, district, ward }
}

// Display URLs are short-lived signed links; keep them for the page's life.
const photoUrls = new Map<string, Promise<string>>()

export function photoUrl(mediaId: string): Promise<string> {
  let url = photoUrls.get(mediaId)
  if (!url) {
    url = request<{ url: string }>(`/media/${mediaId}/access/?variant=DISPLAY`, { auth: true }).then((access) => access.url)
    url.catch(() => photoUrls.delete(mediaId))
    photoUrls.set(mediaId, url)
  }
  return url
}

// The codes activate_listing refuses with, or null for any other failure.
export function activationBlockers(error: unknown): ActivationBlocker[] | null {
  if (!(error instanceof ApiError)) return null
  const codes = error.fieldErrors.activation
  return codes?.length ? (codes as ActivationBlocker[]) : null
}

export const listerApi = {
  properties: () => request<PropertyRecord[]>('/properties/', { auth: true }),
  property: (id: string) => request<PropertyRecord>(`/properties/${encodeURIComponent(id)}/`, { auth: true }),
  createProperty: (input: PropertyInput) => request<PropertyRecord>('/properties/', { method: 'POST', body: input, auth: true }),
  updateProperty: (id: string, input: Partial<PropertyInput>) =>
    request<PropertyRecord>(`/properties/${encodeURIComponent(id)}/`, { method: 'PATCH', body: input, auth: true }),

  listings: () => request<Listing[]>('/listings/', { auth: true }),
  listing: (id: string) => request<Listing>(`/listings/${encodeURIComponent(id)}/`, { auth: true }),
  // New listings start as drafts (LST-02).
  createListing: (propertyId: string, kind: ListerKind, input: ListingInput) =>
    request<Listing>('/listings/', { method: 'POST', body: { property: propertyId, lister_kind: kind, ...input }, auth: true }),
  updateListing: (id: string, input: Partial<ListingInput>) =>
    request<Listing>(`/listings/${encodeURIComponent(id)}/`, { method: 'PATCH', body: input, auth: true }),
  activate: (id: string) => request<Listing>(`/listings/${encodeURIComponent(id)}/activate/`, { method: 'POST', body: {}, auth: true }),
  withdraw: (id: string) => request<Listing>(`/listings/${encodeURIComponent(id)}/withdraw/`, { method: 'POST', body: {}, auth: true }),

  photos: (id: string) => request<ListingPhoto[]>(`/listings/${encodeURIComponent(id)}/photos/`, { auth: true }),
  // Upload the image as the listing's media, then place it in the gallery.
  addPhoto: async (id: string, image: File) => {
    const form = new FormData()
    form.append('image', image)
    form.append('owner_type', 'listing')
    form.append('owner_id', id)
    const media = await request<{ media_id: string }>('/media/images/', {
      method: 'POST',
      body: form,
      auth: true,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
    return request<ListingPhoto>(`/listings/${encodeURIComponent(id)}/photos/`, {
      method: 'POST',
      body: { media_id: media.media_id },
      auth: true,
    })
  },
  removePhoto: (id: string, photoId: string) =>
    request<null>(`/listings/${encodeURIComponent(id)}/photos/${photoId}/`, { method: 'DELETE', auth: true }),
  reorderPhotos: (id: string, photoIds: string[]) =>
    request<ListingPhoto[]>(`/listings/${encodeURIComponent(id)}/photos/reorder/`, { method: 'POST', body: { photo_ids: photoIds }, auth: true }),

  // VER-02: the property's level and its location checks, newest first.
  checkStatus: (propertyId: string) =>
    request<PropertyCheckStatus>(`/verifications/properties/${encodeURIComponent(propertyId)}/`, { auth: true }),
  // A photo or a scanned PDF of the title document, kept as the property's own
  // private media; only the verifier on the check can open it.
  uploadTitleDocument: (propertyId: string, document: File) => {
    const form = new FormData()
    form.append('document', document)
    return request<{ media_id: string; mime_type: string; size_bytes: number; created_at: string }>(`/verifications/properties/${encodeURIComponent(propertyId)}/title-documents/`, {
      method: 'POST',
      body: form,
      auth: true,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },
  requestCheck: (propertyId: string, mediaId: string) =>
    request<PropertyCheck>(`/verifications/properties/${encodeURIComponent(propertyId)}/documents/`, {
      method: 'POST',
      body: { evidence: [{ evidence_type: 'TITLE_DOCUMENT', evidence_ref: mediaId }] },
      auth: true,
    }),

  // 404 until the lister starts; 403 for accounts without an Owner or Agent role.
  identity: () => request<ListerIdentity>('/lister-identity/me/', { auth: true }),
  startIdentity: (nationalIdNumber: string) =>
    request<ListerIdentity>('/lister-identity/', { method: 'POST', body: { national_id_number: nationalIdNumber }, auth: true }),
  updateIdentity: (nationalIdNumber: string) =>
    request<ListerIdentity>('/lister-identity/me/', { method: 'PATCH', body: { national_id_number: nationalIdNumber }, auth: true }),
  uploadEvidence: (kind: EvidenceKind, image: File) => {
    const form = new FormData()
    form.append('kind', kind)
    form.append('image', image)
    return request<ListerIdentity>('/lister-identity/me/evidence/', {
      method: 'POST',
      body: form,
      auth: true,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },
  submitIdentity: () => request<ListerIdentity>('/lister-identity/me/submit/', { method: 'POST', body: {}, auth: true }),
  // ACC-T1: a fresh WhatsApp confirmation link; Oweru staff send it from the outbox.
  requestWhatsAppLink: () =>
    request<{ delivery_id: string; status: string }>('/payments/confirmation-requests/', { method: 'POST', body: { purpose: 'PHONE' }, auth: true }),

  leads: () => request<Lead[]>('/leads/', { auth: true }),
  metrics: () => request<LeadMetrics>('/leads/metrics/', { auth: true }),
  moveLead: (id: string, stage: LeadStage, reason = '', finalPrice?: string) =>
    request<Lead>(`/leads/${id}/transition/`, {
      method: 'POST',
      body: { stage, reason, ...(finalPrice ? { final_selling_price: finalPrice } : {}) },
      auth: true,
      headers: { 'Idempotency-Key': idempotencyKey() },
    }),
  followUp: (id: string, at: string | null) => request<Lead>(`/leads/${id}/follow-up/`, { method: 'POST', body: { follow_up_at: at }, auth: true }),
}
