import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { formatTsh } from '../../lib/format'
import { placeName, sizeText, sortedPhotos } from '../../lib/listingText'
import type { PublicListing } from '../../lib/marketApi'
import { DocumentIcon, ImageIcon, RulerIcon } from '../icons'
import { VerificationBadge } from './VerificationBadge'

// Grid card matching the Horizon Realty reference: photo with a dark chip,
// title and price on one row, a grey address, then a facts row. GSAP staggers
// the `data-card` wrapper while motion owns the hover lift.
export function ListingCard({ listing, priority = false }: { listing: PublicListing; priority?: boolean }) {
  const { t, i18n } = useTranslation()
  const cover = sortedPhotos(listing)[0]
  const size = sizeText(listing, i18n.language)
  const { location, category } = listing.property

  return (
    <div data-card className="h-full">
      <motion.article
        whileHover={{ y: -4 }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        className="group relative flex h-full flex-col overflow-hidden rounded-lg bg-white shadow-card transition-shadow duration-300 hover:shadow-lift"
      >
        <div className="relative aspect-[5/3] overflow-hidden bg-mist">
          {cover ? (
            <img
              src={cover.url}
              alt=""
              loading={priority ? 'eager' : 'lazy'}
              decoding="async"
              className="size-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
            />
          ) : (
            <div className="grid size-full place-items-center text-muted">
              <span className="flex flex-col items-center gap-2 text-xs">
                <ImageIcon className="size-7" />
                {t('market.noPhotos')}
              </span>
            </div>
          )}
          <div className="absolute top-3 left-3">
            <VerificationBadge level={listing.lister.verification.level} />
          </div>
          {listing.status === 'UNDER_OFFER' && (
            <span className="absolute top-3 right-3 rounded bg-white px-2 py-1 text-[11px] font-semibold text-navy shadow-sm">{t('market.underOffer')}</span>
          )}
          <span className="absolute bottom-3 left-3 rounded bg-navy/85 px-2 py-1 text-[11px] font-medium text-white">
            {t(`market.category.${category}`)}
          </span>
          {listing.photos.length > 1 && (
            <span className="absolute right-3 bottom-3 rounded bg-navy/85 px-2 py-1 text-[11px] font-medium text-white">
              {t('market.photoCount', { count: listing.photos.length })}
            </span>
          )}
        </div>

        <div className="flex flex-1 flex-col px-5 pt-4 pb-5">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="min-w-0 truncate text-[15px] font-semibold text-navy">
              {/* The ::after overlay makes the whole card one link target. */}
              <Link
                to={`/listings/${encodeURIComponent(listing.listing_id)}`}
                className="after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-gold"
              >
                <span className="sr-only">{t(`market.category.${category}`)}, </span>
                {location.locality || location.ward}
              </Link>
            </h3>
            <p className="shrink-0 text-[15px] font-semibold text-navy">{formatTsh(listing.selling_price, i18n.language)}</p>
          </div>
          <p className="mt-1.5 truncate text-[13px] text-muted">{[placeName(listing), location.region].filter(Boolean).join(', ')}</p>
          <div className="mt-auto flex flex-wrap items-center gap-x-5 gap-y-1.5 pt-4 text-[13px] text-muted">
            {size && (
              <span className="inline-flex items-center gap-1.5">
                <RulerIcon className="size-4 text-gold" />
                {size}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5">
              <DocumentIcon className="size-4 text-gold" />
              {t(`market.titleType.${listing.property.title_type}`)}
            </span>
          </div>
        </div>
      </motion.article>
    </div>
  )
}

export function ListingCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg bg-white shadow-card" aria-hidden="true">
      <div className="aspect-[5/3] animate-pulse bg-mist" />
      <div className="space-y-3 px-5 pt-4 pb-5">
        <div className="flex justify-between gap-4">
          <div className="h-4 w-24 animate-pulse rounded bg-mist" />
          <div className="h-4 w-28 animate-pulse rounded bg-mist" />
        </div>
        <div className="h-3 w-44 animate-pulse rounded bg-mist" />
        <div className="h-3 w-36 animate-pulse rounded bg-mist" />
      </div>
    </div>
  )
}
