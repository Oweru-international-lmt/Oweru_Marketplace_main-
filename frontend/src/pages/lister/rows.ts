import type { TFunction } from 'i18next'
import { listerApi, photoUrl, propertyPlace, type Listing, type ListingPhoto, type ListingStatus, type PropertyRecord } from '../../lib/listerApi'

// One listing with what its row shows: the property record, the place names
// and the cover photo (the first by position).
export type ListingRow = {
  listing: Listing
  property: PropertyRecord | null
  place: { region: string; district: string; ward: string } | null
  cover: string | null
  photoCount: number
}

export async function loadListingRows(): Promise<ListingRow[]> {
  const [listings, properties] = await Promise.all([listerApi.listings(), listerApi.properties()])
  const byId = new Map(properties.map((record) => [record.property_id, record]))
  const rows = await Promise.all(
    listings.map(async (listing): Promise<ListingRow> => {
      const property = byId.get(listing.property_id) ?? null
      const [place, photos] = await Promise.all([
        property ? propertyPlace(property).catch(() => null) : null,
        listerApi.photos(listing.listing_id).catch(() => []),
      ])
      const first = [...photos].sort((a, b) => a.position - b.position)[0]
      const cover = first ? await photoUrl(first.media_id).catch(() => null) : null
      return { listing, property, place, cover, photoCount: photos.length }
    }),
  )
  return rows.sort((a, b) => b.listing.updated_at.localeCompare(a.listing.updated_at))
}

// The L11 submenu: what each ?status= shows.
export const STATUS_FILTERS = {
  draft: ['DRAFT'],
  published: ['ACTIVE', 'UNDER_OFFER'],
  unavailable: ['WITHDRAWN', 'SUSPENDED'],
  sold: ['SOLD'],
} satisfies Record<string, ListingStatus[]>

export type StatusFilter = keyof typeof STATUS_FILTERS

export function isStatusFilter(value: string | null): value is StatusFilter {
  return value !== null && value in STATUS_FILTERS
}

// Listings have no name of their own: "Nyumba, Mtaa wa Kwanza".
export function rowTitle(t: TFunction, row: Pick<ListingRow, 'property' | 'place'>): string {
  if (!row.property) return t('lister.untitled')
  const where = row.property.locality?.name ?? row.place?.ward
  const kind = t(`market.category.${row.property.category}`)
  return where ? `${kind}, ${where}` : kind
}

// "Mtaa wa Kwanza, Usa River, Arumeru, Arusha".
export function rowAddress(row: Pick<ListingRow, 'property' | 'place'>): string {
  if (!row.place) return ''
  return [row.property?.locality?.name, row.place.ward, row.place.district, row.place.region].filter(Boolean).join(', ')
}

// Labels in the features list match either language, so a listing written
// in English still ticks its boxes after switching to Swahili.
export const FEATURES = [
  'water',
  'electricity',
  'solar',
  'borehole',
  'fence',
  'gate',
  'security',
  'cctv',
  'parking',
  'garden',
  'balcony',
  'airConditioning',
  'furnished',
  'tiles',
  'internet',
  'roadAccess',
  'schoolNearby',
  'marketNearby',
] as const
export type Feature = (typeof FEATURES)[number]

// A gallery photo with its display link, in gallery order.
export type Photo = ListingPhoto & { url: string | null }

export async function withUrls(photos: ListingPhoto[]): Promise<Photo[]> {
  const sorted = [...photos].sort((a, b) => a.position - b.position)
  return Promise.all(sorted.map(async (photo) => ({ ...photo, url: await photoUrl(photo.media_id).catch(() => null) })))
}
