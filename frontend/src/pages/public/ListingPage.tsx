import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeftIcon, CalendarIcon, DocumentIcon, MapPinIcon, RulerIcon, TickIcon } from '../../components/icons'
import { FullPageLoader } from '../../components/FullPageLoader'
import { VerificationBadge } from '../../components/market/VerificationBadge'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ApiError } from '../../lib/api'
import { formatDate, formatTsh } from '../../lib/format'
import { gsap, MOTION_OK, useGSAP } from '../../lib/gsap'
import { placeName, sizeText, sortedPhotos } from '../../lib/listingText'
import { marketApi, type PublicListing } from '../../lib/marketApi'
import { Gallery } from './listing/Gallery'
import { ContactActions, FullCheckCard, ListerCard } from './listing/ListingSidebar'
import { VerificationPanel } from './listing/VerificationPanel'

type Loaded = { id: string; listing?: PublicListing; missing?: boolean; failed?: boolean }

export function ListingPage() {
  const { listingId = '' } = useParams()
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    marketApi
      .listing(listingId)
      .then((listing) => !cancelled && setLoaded({ id: listingId, listing }))
      .catch((error: unknown) => {
        if (cancelled) return
        const missing = error instanceof ApiError && error.status === 404
        setLoaded({ id: listingId, missing, failed: !missing })
      })
    return () => {
      cancelled = true
    }
  }, [listingId, attempt])

  const current = loaded?.id === listingId ? loaded : null
  if (!current) return <FullPageLoader inline />
  if (current.listing) return <ListingView listing={current.listing} />
  return <Unavailable failed={Boolean(current.failed)} onRetry={() => setAttempt((value) => value + 1)} />
}

function ListingView({ listing }: { listing: PublicListing }) {
  const { t, i18n } = useTranslation()
  const root = useRef<HTMLDivElement>(null)
  const category = t(`market.category.${listing.property.category}`)
  const place = placeName(listing)
  useDocumentTitle(`${category}, ${place}`)

  useGSAP(
    () => {
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap.from('[data-intro]', { opacity: 0, y: 18, duration: 0.6, stagger: 0.08, ease: 'power3.out' })
        gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach((element) => {
          gsap.from(element, {
            opacity: 0,
            y: 24,
            duration: 0.6,
            ease: 'power3.out',
            scrollTrigger: { trigger: element, start: 'top 88%', once: true },
          })
        })
      })
    },
    { scope: root, dependencies: [listing.listing_id], revertOnUpdate: true },
  )

  const size = sizeText(listing, i18n.language)
  const facts = [
    size && { icon: RulerIcon, label: t('listing.size'), value: size },
    { icon: DocumentIcon, label: t('listing.titleType'), value: t(`market.titleType.${listing.property.title_type}`) },
    { icon: MapPinIcon, label: t('listing.propertyId'), value: listing.property.property_id },
    { icon: CalendarIcon, label: t('listing.listed'), value: formatDate(listing.created_at, i18n.language) },
  ].filter(Boolean) as { icon: typeof RulerIcon; label: string; value: string }[]

  return (
    <div ref={root} className="mx-auto max-w-7xl px-4 pt-6 pb-28 sm:px-8 sm:pt-8 lg:pb-16">
      <Link to="/listings" className="inline-flex h-11 items-center gap-2 text-sm font-medium text-muted hover:text-navy">
        <ArrowLeftIcon className="size-4" />
        {t('listing.back')}
      </Link>

      <div className="mt-2 grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-10">
        <div className="min-w-0 space-y-8">
          <div data-intro>
            <Gallery photos={sortedPhotos(listing)} />
          </div>

          <header className="space-y-3">
            <div data-intro className="flex flex-wrap items-center gap-2">
              <VerificationBadge level={listing.lister.verification.level} size="md" />
              {listing.status === 'UNDER_OFFER' && (
                <span className="rounded-full bg-navy px-3 py-1.5 text-sm font-semibold text-white">{t('market.underOffer')}</span>
              )}
            </div>
            <h1 data-intro className="font-serif text-[34px] leading-tight font-semibold text-navy sm:text-[42px]">
              {t('listing.inLocation', { category, place })}
            </h1>
            <p data-intro className="flex items-center gap-1.5 text-[15px] text-muted">
              <MapPinIcon className="size-4 shrink-0" />
              {[listing.property.location.ward, listing.property.location.district, listing.property.location.region].filter(Boolean).join(', ')}
            </p>
            <p data-intro className="text-3xl font-bold text-navy lg:hidden">
              {formatTsh(listing.selling_price, i18n.language)}
            </p>
          </header>

          <dl data-reveal className="grid gap-3 sm:grid-cols-2">
            {facts.map((fact) => (
              <div key={fact.label} className="flex items-start gap-3 rounded-lg bg-white p-4 shadow-card">
                <span className="grid size-10 shrink-0 place-items-center rounded-md bg-paper text-navy">
                  <fact.icon className="size-5" />
                </span>
                <div className="min-w-0">
                  <dt className="text-xs text-muted">{fact.label}</dt>
                  <dd className="mt-0.5 font-medium break-words text-navy">{fact.value}</dd>
                </div>
              </div>
            ))}
          </dl>

          <section data-reveal aria-labelledby="about-title">
            <h2 id="about-title" className="font-serif text-2xl font-semibold text-navy">
              {t('listing.about')}
            </h2>
            <p className="mt-3 text-[15px] leading-relaxed whitespace-pre-line text-navy/85">
              {listing.description.trim() || <span className="text-muted">{t('listing.noDescription')}</span>}
            </p>
            <Features features={listing.features} />
          </section>

          <div data-reveal>
            <VerificationPanel listing={listing} />
          </div>
        </div>

        <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
          <ContactActions listing={listing} />
          <ListerCard listing={listing} />
          <FullCheckCard listing={listing} />
        </aside>
      </div>
    </div>
  )
}

// The API stores features as free JSON: a list of labels, or named values.
function Features({ features }: { features: unknown }) {
  const { t } = useTranslation()
  let items: string[] = []
  if (Array.isArray(features)) items = features.filter((item): item is string => typeof item === 'string' && item.trim() !== '')
  else if (features && typeof features === 'object') {
    items = Object.entries(features as Record<string, unknown>)
      .filter(([, value]) => value !== false && value !== null && value !== '')
      .map(([name, value]) => {
        const label = name.replace(/_/g, ' ')
        return value === true ? label : `${label}: ${String(value)}`
      })
  }
  if (items.length === 0) return null

  return (
    <div className="mt-6">
      <h3 className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('listing.features')}</h3>
      <ul className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => (
          <li key={item} className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm text-navy ring-1 ring-mist">
            <TickIcon className="size-4 text-success" />
            <span className="first-letter:uppercase">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Unavailable({ failed, onRetry }: { failed: boolean; onRetry: () => void }) {
  const { t } = useTranslation()
  useDocumentTitle(failed ? t('search.errorTitle') : t('listing.notFoundTitle'))
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-8">
      <h1 className="text-3xl font-bold text-navy">{failed ? t('search.errorTitle') : t('listing.notFoundTitle')}</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-muted">{failed ? t('common.networkError') : t('listing.notFoundBody')}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {failed && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex h-12 items-center rounded-md bg-gold px-6 text-sm font-semibold text-navy hover:bg-gold-light"
          >
            {t('search.retry')}
          </button>
        )}
        <Link
          to="/listings"
          className="inline-flex h-12 items-center rounded-md bg-white px-6 text-sm font-semibold text-navy ring-1 ring-mist hover:ring-navy/30"
        >
          {t('site.browse')}
        </Link>
      </div>
    </div>
  )
}
