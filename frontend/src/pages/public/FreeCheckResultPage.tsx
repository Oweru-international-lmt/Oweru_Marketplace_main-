import { motion } from 'motion/react'
import { useEffect, useRef, useState, type ComponentType, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, CheckIcon, DocumentIcon, SearchIcon, ShieldIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useNoReferrer } from '../../hooks/useNoReferrer'
import { useReveal } from '../../hooks/useReveal'
import { ApiError } from '../../lib/api'
import { whatsappLink, whatsappTo } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { formatDate, formatNumber } from '../../lib/format'
import { servicesApi, type FreeCheckCreated, type FreeCheckResult, type Verdict } from '../../lib/servicesApi'
import { CopyButton, Panel, ServiceColumns, ServiceHeader, ServicePage } from './services/ServiceUi'

type Loaded = { key: string; result?: FreeCheckResult; failed?: 'invalid' | 'network' }

// FRC-03: the verdict on screen, a PDF, and a link the person sends to their
// own WhatsApp. Opened straight after the check, or later from that link.
export function FreeCheckResultPage() {
  const { checkId = '' } = useParams()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const { state } = useLocation() as { state: { created?: FreeCheckCreated } | null }
  const created = state?.created?.id === checkId ? state.created : undefined
  const key = `${checkId}:${token}`
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [attempt, setAttempt] = useState(0)
  useNoReferrer()

  useEffect(() => {
    if (created) return
    let cancelled = false
    servicesApi
      .freeCheck(checkId, token)
      .then((result) => !cancelled && setLoaded({ key, result }))
      .catch((error: unknown) => {
        if (cancelled) return
        const invalid = error instanceof ApiError && (error.status === 403 || error.status === 404)
        setLoaded({ key, failed: invalid ? 'invalid' : 'network' })
      })
    return () => {
      cancelled = true
    }
  }, [checkId, token, key, created, attempt])

  if (created) return <Report result={created} token={token} whatsapp={created.whatsapp_link} />
  const current = loaded?.key === key ? loaded : null
  if (!current) return <FullPageLoader inline />
  if (current.result) return <Report result={current.result} token={token} />
  return <InvalidLink network={current.failed === 'network'} onRetry={() => setAttempt((value) => value + 1)} />
}

const VERDICT_ORDER = ['land', 'duplicates', 'photos', 'description_match'] as const

type Tone = { icon: ComponentType<SVGProps<SVGSVGElement>>; badge: string; ring: string }

// Good news in green, things to look into in amber or red, unknowns in grey.
function toneFor(status: Verdict['status']): Tone {
  if (status === 'LAND' || status === 'MATCH' || status === 'NONE') return { icon: CheckIcon, badge: 'bg-success-soft text-success', ring: 'ring-success/20' }
  if (status === 'MISMATCH' || status === 'OUTSIDE') return { icon: AlertIcon, badge: 'bg-danger-soft text-danger', ring: 'ring-danger/25' }
  if (status === 'FOUND') return { icon: AlertIcon, badge: 'bg-gold/15 text-[#8a5f12]', ring: 'ring-gold/30' }
  return { icon: SearchIcon, badge: 'bg-paper text-muted', ring: 'ring-mist' }
}

function Report({ result, token, whatsapp }: { result: FreeCheckResult; token: string; whatsapp?: string }) {
  const { t, i18n } = useTranslation()
  useDocumentTitle(`${t('freeCheck.reportKicker')} ${result.reference}`)
  const root = useRef<HTMLDivElement>(null)
  useReveal(root)
  const [opening, setOpening] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)

  // The API's own link points at JSON; people get this page instead.
  const pageLink = `${window.location.origin}/free-check/${result.id}?${new URLSearchParams({ token })}`
  const message = t('freeCheck.shareMessage', { reference: result.reference, link: pageLink })
  const ownWhatsApp = whatsapp ? whatsappTo(new URL(whatsapp).pathname.slice(1), message) : whatsappTo(null, message)

  async function openPdf() {
    setOpening(true)
    setPdfError(null)
    try {
      const { url } = await servicesApi.freeCheckPdf(result.id, token)
      window.location.assign(url)
    } catch (error) {
      setPdfError(errorMessage(t, error))
    } finally {
      setOpening(false)
    }
  }

  const verdicts = VERDICT_ORDER.flatMap((name) => (result.verdicts[name] ? [{ name, verdict: result.verdicts[name] }] : []))

  return (
    <ServicePage>
      <div ref={root}>
        <ServiceHeader kicker={t('freeCheck.reportKicker')} lead={t('freeCheck.reportTitle')}>
          <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-white/75 sm:text-muted">
            <span>
              {t('freeCheck.reference')}: <span className="font-semibold text-white sm:text-navy">{result.reference}</span>
            </span>
            <span>{t('freeCheck.checkedOn', { date: formatDate(result.date, i18n.language) })}</span>
          </div>
        </ServiceHeader>

        <ServiceColumns aside={<NextSteps reference={result.reference} />}>
          {/* FRC-04's statement, in the language the check was made in. */}
          <div data-reveal className="flex items-start gap-3 rounded-2xl bg-navy px-5 py-4 text-white sm:rounded-md">
            <ShieldIcon className="mt-0.5 size-5 shrink-0 text-gold-light" />
            <p className="font-serif text-lg leading-snug font-semibold">{result.disclaimer}</p>
          </div>

          <section data-reveal aria-labelledby="verdicts-title">
            <h2 id="verdicts-title" className="text-base font-bold text-navy sm:font-serif sm:text-2xl sm:font-semibold">
              {t('freeCheck.verdicts')}
            </h2>
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {verdicts.map(({ name, verdict }, index) => {
                const tone = toneFor(verdict.status)
                return (
                  <motion.li
                    key={name}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 + index * 0.08, duration: 0.4 }}
                    className={`flex gap-3 rounded-2xl bg-white p-4 shadow-card ring-1 sm:rounded-md sm:p-5 ${tone.ring}`}
                  >
                    <span className={`grid size-10 shrink-0 place-items-center rounded-full ${tone.badge}`}>
                      <tone.icon className="size-5" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-navy">{t(`freeCheck.verdictNames.${name}`)}</h3>
                      <p className="mt-1 text-sm leading-relaxed text-navy/80">{verdict.message}</p>
                    </div>
                  </motion.li>
                )
              })}
            </ul>
          </section>

          <section data-reveal className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <button
              type="button"
              onClick={() => void openPdf()}
              disabled={opening}
              aria-busy={opening || undefined}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-navy px-6 text-sm font-semibold text-white transition-colors hover:bg-navy-soft disabled:opacity-70"
            >
              <DocumentIcon className="size-5" />
              {opening ? t('freeCheck.downloading') : t('freeCheck.download')}
            </button>
            <a
              href={ownWhatsApp}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#1f7a4d] px-6 text-sm font-semibold text-white transition-colors hover:bg-[#186440]"
            >
              <WhatsAppIcon className="size-5" />
              {t('freeCheck.sendWhatsApp')}
            </a>
            <div className="flex items-center justify-center sm:ml-auto">
              <CopyButton value={pageLink} label={t('forms.copyLink')} />
            </div>
          </section>
          {pdfError && <Alert tone="error">{pdfError}</Alert>}

          <section data-reveal aria-labelledby="details-title" className="rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-6">
            <h2 id="details-title" className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">
              {t('freeCheck.details')}
            </h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <Detail label={t('freeCheck.category')} value={t(`market.category.${result.category}`)} />
              <Detail label={t('freeCheck.size')} value={`${formatNumber(result.size, i18n.language)} ${t(`freeCheck.units.${result.size_unit as 'sqm'}`)}`} />
              <div className="sm:col-span-2">
                <Detail label={t('freeCheck.description')} value={result.description} />
              </div>
            </dl>
            <p className="mt-5 border-t border-mist pt-4 text-xs leading-relaxed text-muted">
              {t('freeCheck.validUntil', { date: formatDate(result.expires_at, i18n.language) })}. {t('forms.privateLink')}
            </p>
          </section>
        </ServiceColumns>
      </div>
    </ServicePage>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-[15px] leading-relaxed break-words whitespace-pre-line text-navy">{value}</dd>
    </div>
  )
}

function NextSteps({ reference }: { reference: string }) {
  const { t } = useTranslation()
  return (
    <>
      <Panel tone="navy">
        <h2 className="font-serif text-xl font-semibold">{t('freeCheck.nextTitle')}</h2>
        <p className="mt-2 text-sm leading-relaxed text-white/75">{t('freeCheck.limitNote')}</p>
        <a
          href={whatsappLink(t('freeCheck.nextMessage', { reference }))}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-5 inline-flex h-11 items-center gap-2 rounded-md bg-gold px-4 text-sm font-semibold text-navy hover:bg-gold-light"
        >
          <WhatsAppIcon className="size-4" />
          {t('freeCheck.nextCta')}
        </a>
      </Panel>
      <Link
        to="/free-check"
        className="flex h-12 items-center justify-center rounded-xl bg-white text-sm font-semibold text-navy ring-1 ring-mist transition-colors hover:ring-navy/30"
      >
        {t('freeCheck.another')}
      </Link>
    </>
  )
}

function InvalidLink({ network, onRetry }: { network: boolean; onRetry: () => void }) {
  const { t } = useTranslation()
  useDocumentTitle(t('freeCheck.invalidTitle'))
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-8">
      <h1 className="font-serif text-3xl font-semibold text-navy">{network ? t('search.errorTitle') : t('freeCheck.invalidTitle')}</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-muted">{network ? t('common.networkError') : t('freeCheck.invalidBody')}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {network && (
          <button type="button" onClick={onRetry} className="inline-flex h-12 items-center rounded-md bg-gold px-6 text-sm font-semibold text-navy hover:bg-gold-light">
            {t('common.retry')}
          </button>
        )}
        <Link to="/free-check" className="inline-flex h-12 items-center rounded-md bg-white px-6 text-sm font-semibold text-navy ring-1 ring-mist hover:ring-navy/30">
          {t('freeCheck.another')}
        </Link>
      </div>
    </div>
  )
}
