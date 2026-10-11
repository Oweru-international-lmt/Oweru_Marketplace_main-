import { formatNumber } from './format'
import type { PublicListing } from './marketApi'

// "Mbezi A, Kinondoni": street or village (else ward), then district.
export function placeName(listing: PublicListing): string {
  const { locality, ward, district } = listing.property.location
  return [locality || ward, district].filter(Boolean).join(', ')
}

export function sizeText(listing: PublicListing, language: string): string | null {
  const { stated_size: size, size_unit: unit } = listing.property
  return size ? `${formatNumber(size, language)} ${unit}` : null
}

export function sortedPhotos(listing: PublicListing) {
  return [...listing.photos].sort((a, b) => a.position - b.position)
}
