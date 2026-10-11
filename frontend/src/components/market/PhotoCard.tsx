import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { formatTsh } from '../../lib/format'
import { sizeText, sortedPhotos } from '../../lib/listingText'
import type { PublicListing } from '../../lib/marketApi'
import { ImageIcon, MapPinIcon } from '../icons'
import { VerificationBadge } from './VerificationBadge'

// Phone card with everything over the photo. "wide" follows the M5 results
// reference (badge top-left; name, place and price along the bottom); "tall"
// follows the M3 home carousel (portrait, large radius).
export function PhotoCard({ listing, variant = 'wide', priority = false }: { listing: PublicListing; variant?: 'wide' | 'tall'; priority?: boolean }) {
  const { t, i18n } = useTranslation()
  const cover = sortedPhotos(listing)[0]
  const { location, category } = listing.property
  const tall = variant === 'tall'
  const size = sizeText(listing, i18n.language)

  return (
    <div data-card>
      <motion.article
        whileTap={{ scale: 0.98 }}
        className={`group relative overflow-hidden bg-navy shadow-card ${tall ? 'aspect-[4/5] rounded-[28px]' : 'aspect-[16/11] rounded-2xl'}`}
      >
        {cover ? (
          <img
            src={cover.url}
            alt=""
            loading={priority ? 'eager' : 'lazy'}
            decoding="async"
            className="absolute inset-0 size-full object-cover transition-transform duration-700 group-hover:scale-105"
          />
        ) : (
          <div className="absolute inset-0 grid place-items-center text-white/50">
            <span className="flex flex-col items-center gap-2 text-xs">
              <ImageIcon className="size-7" />
              {t('market.noPhotos')}
            </span>
          </div>
        )}
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-navy/90 via-navy/25 via-55% to-transparent" />

        <div className="absolute inset-x-3 top-3 flex items-start justify-between gap-2">
          <VerificationBadge level={listing.lister.verification.level} />
          {listing.status === 'UNDER_OFFER' && (
            <span className="rounded-full bg-white/95 px-2.5 py-1 text-[11px] font-semibold text-navy">{t('market.underOffer')}</span>
          )}
        </div>

        <div className={`absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 text-white ${tall ? 'p-5' : 'p-4'}`}>
          <div className="min-w-0">
            <h3 className={`truncate font-semibold ${tall ? 'text-lg' : 'text-base'}`}>
              {/* The ::after overlay makes the whole card one link target. */}
              <Link
                to={`/listings/${encodeURIComponent(listing.listing_id)}`}
                className="after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-offset-[-4px] focus-visible:after:outline-gold"
              >
                <span className="sr-only">{t(`market.category.${category}`)}, </span>
                {location.locality || location.ward}
              </Link>
            </h3>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-white/80">
              <MapPinIcon className="size-3.5 shrink-0" />
              <span className="truncate">
                {[location.district, location.region].filter(Boolean).join(', ')}
                {size && !tall ? ` · ${size}` : ''}
              </span>
            </p>
            {tall && <p className="mt-2 text-base font-bold">{formatTsh(listing.selling_price, i18n.language)}</p>}
          </div>
          {!tall && <p className="shrink-0 text-base font-bold">{formatTsh(listing.selling_price, i18n.language)}</p>}
        </div>
      </motion.article>
    </div>
  )
}

export function PhotoCardSkeleton({ variant = 'wide' }: { variant?: 'wide' | 'tall' }) {
  return <div aria-hidden="true" className={`animate-pulse bg-mist ${variant === 'tall' ? 'aspect-[4/5] rounded-[28px]' : 'aspect-[16/11] rounded-2xl'}`} />
}
