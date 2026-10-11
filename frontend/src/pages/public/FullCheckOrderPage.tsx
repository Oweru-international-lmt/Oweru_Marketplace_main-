import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { FullPageLoader } from '../../components/FullPageLoader'
import { ArrowLeftIcon, MapPinIcon, ShieldIcon, WhatsAppIcon } from '../../components/icons'
import { VerificationBadge } from '../../components/market/VerificationBadge'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useReveal } from '../../hooks/useReveal'
import { ApiError, idempotencyKey } from '../../lib/api'
import { whatsappLink } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { formatTsh } from '../../lib/format'
import { placeName, sortedPhotos } from '../../lib/listingText'
import { marketApi, type PublicListing } from '../../lib/marketApi'
import { servicesApi, type FullCheckQuote } from '../../lib/servicesApi'
import { Panel, ServiceColumns, ServiceHeader, ServicePage } from './services/ServiceUi'

type Loaded = { id: string; listing?: PublicListing; quote?: FullCheckQuote | null; failed?: 'missing' | 'network' }

// FUL-01: the buyer sees the fee and scope before ordering; the order freezes
// both through the signed quote.
export function FullCheckOrderPage() {
  const { listingId = '' } = useParams()
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([marketApi.listing(listingId), servicesApi.fullCheckQuote()]).then(([listing, quote]) => {
      if (cancelled) return
      if (listing.status === 'rejected') {
        const missing = listing.reason instanceof ApiError && listing.reason.status === 404
        setLoaded({ id: listingId, failed: missing ? 'missing' : 'network' })
        return
      }
      // A 400 means management hasn't set the fee yet; ordering waits for it.
      setLoaded({ id: listingId, listing: listing.value, quote: quote.status === 'fulfilled' ? quote.value : null })
    })
    return () => {
      cancelled = true
    }
  }, [listingId, attempt])

  const current = loaded?.id === listingId ? loaded : null
  if (!current) return <FullPageLoader inline />
  if (current.listing) return <OrderView listing={current.listing} initialQuote={current.quote ?? null} />
  return <Problem network={current.failed === 'network'} onRetry={() => setAttempt((value) => value + 1)} />
}

type Refusal = { text: string; openChecks?: boolean; whatsapp?: boolean }

function OrderView({ listing, initialQuote }: { listing: PublicListing; initialQuote: FullCheckQuote | null }) {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('fullCheck.title'))
  const navigate = useNavigate()
  const root = useRef<HTMLDivElement>(null)
  useReveal(root)
  const [quote, setQuote] = useState(initialQuote)
  const [ordering, setOrdering] = useState(false)
  const [refusal, setRefusal] = useState<Refusal | null>(null)
  // One key per order attempt, so a retried request can't order twice.
  const [key, setKey] = useState(idempotencyKey)
  const photo = sortedPhotos(listing)[0]
  const verified = listing.lister.verification.level === 3

  async function order() {
    if (!quote) return
    setOrdering(true)
    setRefusal(null)
    try {
      const created = await servicesApi.orderFullCheck(listing.listing_id, quote.quote, key)
      navigate(`/full-checks/${created.job_id}`)
    } catch (error) {
      setOrdering(false)
      if (!(error instanceof ApiError)) {
        setRefusal({ text: errorMessage(t, error) })
        return
      }
      if (error.status === 403) setRefusal({ text: t('fullCheck.notBuyer'), whatsapp: true })
      else if (error.status === 404) setRefusal({ text: t('fullCheck.unavailable') })
      else if (error.status === 409 && /unfinished/i.test(error.detail ?? '')) setRefusal({ text: t('fullCheck.alreadyOpen'), openChecks: true })
      else if (error.status === 409 && /fee or scope/i.test(error.detail ?? '')) {
        // Show the new terms; the buyer orders again knowingly, with a new key.
        setKey(idempotencyKey())
        setRefusal({ text: t('fullCheck.feeChanged') })
        servicesApi.fullCheckQuote().then(setQuote, () => setQuote(null))
      } else setRefusal({ text: errorMessage(t, error) })
    }
  }

  const steps = t('fullCheck.steps', { returnObjects: true }) as string[]

  return (
    <ServicePage>
      <div ref={root}>
        <Link
          to={`/listings/${listing.listing_id}`}
          className="mb-2 hidden h-11 items-center gap-2 text-sm font-medium text-muted hover:text-navy sm:inline-flex"
        >
          <ArrowLeftIcon className="size-4" />
          {t('listing.back')}
        </Link>
        <ServiceHeader kicker={t('fullCheck.kicker')} lead={t('fullCheck.titleLead')} accent={t('fullCheck.titleAccent')} body={t('fullCheck.subtitle')} />

        <ServiceColumns
          aside={
            <Panel title={t('fullCheck.stepsTitle')}>
              <ol className="space-y-4">
                {steps.map((step, index) => (
                  <li key={step} className="flex gap-3">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-navy font-serif text-xs font-semibold text-gold-light">{index + 1}</span>
                    <span className="pt-0.5 text-sm leading-relaxed text-navy">{step}</span>
                  </li>
                ))}
              </ol>
              <p className="mt-5 border-t border-mist pt-4 text-xs leading-relaxed text-muted">{t('fullCheck.resultNote')}</p>
            </Panel>
          }
        >
          <section data-reveal aria-label={t('fullCheck.property')} className="flex gap-4 rounded-2xl bg-white p-4 shadow-card sm:rounded-md sm:p-5">
            <div className="aspect-[4/3] w-28 shrink-0 overflow-hidden rounded-xl bg-mist sm:w-40">
              {photo && <img src={photo.url} alt="" className="size-full object-cover" />}
            </div>
            <div className="min-w-0 py-0.5">
              <p className="text-xs text-muted">{t(`market.category.${listing.property.category}`)}</p>
              <p className="mt-0.5 truncate font-serif text-lg font-semibold text-navy sm:text-xl">{placeName(listing)}</p>
              <p className="mt-1 flex items-center gap-1 text-xs text-muted">
                <MapPinIcon className="size-3.5 shrink-0" />
                {listing.property.property_id}
              </p>
              <div className="mt-2.5">
                <VerificationBadge level={listing.lister.verification.level} />
              </div>
            </div>
          </section>

          {verified ? (
            <Alert tone="success">{t('fullCheck.alreadyVerified')}</Alert>
          ) : quote ? (
            <section data-reveal className="rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
              <p className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('fullCheck.fee')}</p>
              <p className="mt-2 font-serif text-[34px] leading-none font-semibold text-navy sm:text-[42px]">{formatTsh(quote.fee, i18n.language)}</p>
              <p className="mt-2 text-sm text-muted">{t('fullCheck.feeNote')}</p>

              <div className="mt-6 rounded-xl bg-paper p-4">
                <p className="flex items-center gap-2 text-sm font-semibold text-navy">
                  <ShieldIcon className="size-4 text-gold" />
                  {t('fullCheck.scope')}
                </p>
                {/* The scope exactly as approved and frozen by the order. */}
                <p className="mt-2 text-sm leading-relaxed text-navy/80">{quote.scope}</p>
              </div>

              {refusal && (
                <div className="mt-5 space-y-3">
                  <Alert tone="error">{refusal.text}</Alert>
                  {refusal.openChecks && (
                    <Link to="/full-checks" className="text-link inline-block text-sm">
                      {t('fullCheck.openChecks')}
                    </Link>
                  )}
                  {refusal.whatsapp && <SupportLink reference={listing.property.property_id} />}
                </div>
              )}

              <div className="mt-6 sm:max-w-sm">
                <Button type="button" onClick={() => void order()} loading={ordering} loadingLabel={t('fullCheck.ordering')}>
                  {t('fullCheck.order', { fee: formatTsh(quote.fee, i18n.language) })}
                </Button>
              </div>
            </section>
          ) : (
            <section className="space-y-4 rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
              <p className="text-[15px] leading-relaxed text-navy">{t('fullCheck.noFee')}</p>
              <SupportLink reference={listing.property.property_id} />
            </section>
          )}
        </ServiceColumns>
      </div>
    </ServicePage>
  )
}

function SupportLink({ reference }: { reference: string }) {
  const { t } = useTranslation()
  return (
    <a
      href={whatsappLink(`${t('site.supportMessage')} ${t('listing.fullCheckCta')}: ${reference}`)}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex h-11 items-center gap-2 rounded-md bg-[#1f7a4d] px-4 text-sm font-semibold text-white hover:bg-[#186440]"
    >
      <WhatsAppIcon className="size-4" />
      {t('site.support')}
    </a>
  )
}

function Problem({ network, onRetry }: { network: boolean; onRetry: () => void }) {
  const { t } = useTranslation()
  useDocumentTitle(network ? t('search.errorTitle') : t('listing.notFoundTitle'))
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-8">
      <h1 className="font-serif text-3xl font-semibold text-navy">{network ? t('search.errorTitle') : t('listing.notFoundTitle')}</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-muted">{network ? t('common.networkError') : t('listing.notFoundBody')}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {network && (
          <button type="button" onClick={onRetry} className="inline-flex h-12 items-center rounded-md bg-gold px-6 text-sm font-semibold text-navy hover:bg-gold-light">
            {t('common.retry')}
          </button>
        )}
        <Link to="/listings" className="inline-flex h-12 items-center rounded-md bg-white px-6 text-sm font-semibold text-navy ring-1 ring-mist hover:ring-navy/30">
          {t('site.browse')}
        </Link>
      </div>
    </div>
  )
}
