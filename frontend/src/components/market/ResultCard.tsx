import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { formatDate, formatTsh } from '../../lib/format'
import { initials } from '../../lib/initials'
import { placeName, sizeText, sortedPhotos } from '../../lib/listingText'
import type { PublicListing } from '../../lib/marketApi'
import { CalendarIcon, DocumentIcon, ImageIcon, MapPinIcon, RulerIcon, UserIcon } from '../icons'
import { VerificationBadge } from './VerificationBadge'

// Search result row matching the Zoopla reference: an inset photo on the
// left; title, address and a two-column facts list; price and lister along
// the bottom. Horizon's card surface (small radius, soft shadow) keeps it in
// the same family as the home page cards.
export function ResultCard({ listing, priority = false }: { listing: PublicListing; priority?: boolean }) {
  const { t, i18n } = useTranslation()
  const cover = sortedPhotos(listing)[0]
  const size = sizeText(listing, i18n.language)
  const { location, category } = listing.property
  const { display_name: name, lister_kind: kind } = listing.lister

  const facts = [
    size && { icon: RulerIcon, text: size },
    { icon: DocumentIcon, text: t(`market.titleType.${listing.property.title_type}`) },
    { icon: UserIcon, text: kind === 'AGENT' ? t('listing.agent') : t('listing.owner') },
    { icon: CalendarIcon, text: t('market.listedOn', { date: formatDate(listing.created_at, i18n.language) }) },
  ].filter(Boolean) as { icon: typeof RulerIcon; text: string }[]

  return (
    <div data-card>
      <motion.article
        whileHover={{ y: -3 }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        className="group relative grid gap-5 rounded-lg bg-white p-4 shadow-card transition-shadow duration-300 hover:shadow-lift sm:grid-cols-[minmax(0,250px)_minmax(0,1fr)]"
      >
        <div className="relative aspect-[4/3] overflow-hidden rounded-md bg-mist">
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
          <div className="absolute top-2.5 left-2.5">
            <VerificationBadge level={listing.lister.verification.level} />
          </div>
          {listing.photos.length > 1 && (
            <span className="absolute right-2.5 bottom-2.5 rounded bg-navy/85 px-2 py-0.5 text-[11px] font-medium text-white">
              {t('market.photoCount', { count: listing.photos.length })}
            </span>
          )}
        </div>

        <div className="flex min-w-0 flex-col py-1 pr-1">
          <div className="flex items-start justify-between gap-3">
            <h3 className="min-w-0 text-base font-semibold text-navy">
              {/* The ::after overlay makes the whole row one link target. */}
              <Link
                to={`/listings/${encodeURIComponent(listing.listing_id)}`}
                className="after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-gold"
              >
                {t('listing.inLocation', { category: t(`market.category.${category}`), place: location.locality || location.ward })}
              </Link>
            </h3>
            {listing.status === 'UNDER_OFFER' && (
              <span className="shrink-0 rounded bg-navy px-2 py-1 text-[11px] font-semibold text-white">{t('market.underOffer')}</span>
            )}
          </div>
          <p className="mt-1 flex items-center gap-1.5 text-[13px] text-muted">
            <MapPinIcon className="size-3.5 shrink-0" />
            <span className="truncate">{[placeName(listing), location.region].filter(Boolean).join(', ')}</span>
          </p>

          <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px] text-navy/80">
            {facts.map((fact) => (
              <li key={fact.text} className="flex min-w-0 items-center gap-2">
                <fact.icon className="size-4 shrink-0 text-gold" />
                <span className="truncate">{fact.text}</span>
              </li>
            ))}
          </ul>

          <div className="mt-auto flex flex-wrap items-end justify-between gap-3 pt-5">
            <p className="text-xl font-bold text-navy">{formatTsh(listing.selling_price, i18n.language)}</p>
            <span className="inline-flex h-9 items-center gap-2 rounded-md pr-3 pl-1 text-[13px] font-semibold text-navy ring-1 ring-mist">
              <span className="grid size-7 place-items-center rounded-full bg-navy text-[10px] font-semibold text-gold-light">{initials(name)}</span>
              <span className="max-w-32 truncate">{name}</span>
            </span>
          </div>
        </div>
      </motion.article>
    </div>
  )
}

export function ResultCardSkeleton() {
  return (
    <div className="grid gap-5 rounded-lg bg-white p-4 shadow-card sm:grid-cols-[250px_1fr]" aria-hidden="true">
      <div className="aspect-[4/3] animate-pulse rounded-md bg-mist" />
      <div className="space-y-3 py-1">
        <div className="h-4 w-48 animate-pulse rounded bg-mist" />
        <div className="h-3 w-56 animate-pulse rounded bg-mist" />
        <div className="grid grid-cols-2 gap-3 pt-2">
          <div className="h-3 animate-pulse rounded bg-mist" />
          <div className="h-3 animate-pulse rounded bg-mist" />
          <div className="h-3 animate-pulse rounded bg-mist" />
          <div className="h-3 animate-pulse rounded bg-mist" />
        </div>
        <div className="h-6 w-40 animate-pulse rounded bg-mist" />
      </div>
    </div>
  )
}
