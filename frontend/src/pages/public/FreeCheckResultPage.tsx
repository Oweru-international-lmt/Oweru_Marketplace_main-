import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { DocumentIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useNoReferrer } from '../../hooks/useNoReferrer'
import { ApiError } from '../../lib/api'
import { whatsappLink, whatsappTo } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { formatDate, formatNumber } from '../../lib/format'
import { servicesApi, type FreeCheckCreated, type FreeCheckResult, type Verdict } from '../../lib/servicesApi'
import { ReceiptBrand, ReceiptCard, ReceiptFooter, ReceiptPage, ReceiptRow, ReceiptRows, ReceiptSeal, ReceiptSection } from './services/receipt'
import { CopyButton } from './services/ServiceUi'

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

// Good news in green, things to look into in red or amber, unknowns in grey.
function toneFor(status: Verdict['status']): string {
  if (status === 'LAND' || status === 'MATCH' || status === 'NONE') return 'text-success'
  if (status === 'MISMATCH' || status === 'OUTSIDE') return 'text-danger'
  if (status === 'FOUND') return 'text-[#8a5f12]'
  return 'text-muted'
}

// After S7: the report as one receipt card.
function Report({ result, token, whatsapp }: { result: FreeCheckResult; token: string; whatsapp?: string }) {
  const { t, i18n } = useTranslation()
  useDocumentTitle(`${t('freeCheck.reportKicker')} ${result.reference}`)
  const [opening, setOpening] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)

  // The API's own link points at JSON; people get this page instead.
  const pageLink = `${window.location.origin}/free-check/${result.id}?${new URLSearchParams({ token })}`
  const message = t('freeCheck.shareMessage', { reference: result.reference, link: pageLink })
  const ownWhatsApp = whatsapp ? whatsappTo(new URL(whatsapp).pathname.slice(1), message) : whatsappTo(null, message)
  const verdicts = VERDICT_ORDER.flatMap((name) => (result.verdicts[name] ? [{ name, verdict: result.verdicts[name] }] : []))
  const worry = verdicts.some(({ verdict }) => verdict.status === 'MISMATCH' || verdict.status === 'OUTSIDE')

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

  return (
    <ReceiptPage>
      <ReceiptBrand />
      <ReceiptCard
        mark={worry ? 'alert' : 'check'}
        title={worry ? t('freeCheck.receiptTitleWorry') : t('freeCheck.receiptTitle')}
        lead={
          <>
            {t('freeCheck.receiptLead')} <b className="font-semibold text-navy">{result.reference}</b>.
          </>
        }
      >
        <ReceiptSection title={t('freeCheck.details')}>
          <ReceiptRows>
            <ReceiptRow label={t('freeCheck.reference')} value={result.reference} />
            <ReceiptRow label={t('freeCheck.date')} value={formatDate(result.date, i18n.language)} />
            <ReceiptRow label={t('freeCheck.category')} value={t(`market.category.${result.category}`)} />
            <ReceiptRow label={t('freeCheck.size')} value={`${formatNumber(result.size, i18n.language)} ${t(`freeCheck.units.${result.size_unit as 'sqm'}`)}`} />
            <ReceiptRow label={t('freeCheck.descriptionShort')} value="" note={<span className="block text-[15px] whitespace-pre-line text-navy">{result.description}</span>} />
          </ReceiptRows>
        </ReceiptSection>

        <ReceiptSection title={t('freeCheck.verdicts')}>
          <ReceiptRows>
            {verdicts.map(({ name, verdict }) => (
              <ReceiptRow
                key={name}
                label={t(`freeCheck.verdictNames.${name}`)}
                value={<span className={toneFor(verdict.status)}>{t(`freeCheck.verdictShort.${verdict.status}`)}</span>}
                note={verdict.message}
              />
            ))}
          </ReceiptRows>
        </ReceiptSection>

        {/* FRC-04's statement, in the language the check was made in. */}
        <ReceiptSection>
          <p className="text-center text-[15px] leading-relaxed text-navy/75">
            <b className="font-semibold text-navy">{result.disclaimer}.</b> {result.full_check}{' '}
            <a
              href={whatsappLink(t('freeCheck.nextMessage', { reference: result.reference }))}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-gold underline-offset-4 hover:underline"
            >
              {t('freeCheck.nextCta')}
            </a>
          </p>
        </ReceiptSection>
      </ReceiptCard>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <button
          type="button"
          onClick={() => void openPdf()}
          disabled={opening}
          aria-busy={opening || undefined}
          className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-navy px-6 text-sm font-semibold text-white transition-colors hover:bg-navy-soft disabled:opacity-70"
        >
          <DocumentIcon className="size-5" />
          {opening ? t('freeCheck.downloading') : t('freeCheck.download')}
        </button>
        <a
          href={ownWhatsApp}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-[#1f7a4d] px-6 text-sm font-semibold text-white transition-colors hover:bg-[#186440]"
        >
          <WhatsAppIcon className="size-5" />
          {t('freeCheck.sendWhatsApp')}
        </a>
      </div>
      {pdfError && (
        <div className="mt-4">
          <Alert tone="error">{pdfError}</Alert>
        </div>
      )}

      <ReceiptFooter>
        <p>
          {t('freeCheck.reference')}: <b className="font-semibold text-navy/80">{result.reference}</b>
        </p>
        <div className="flex justify-center">
          <CopyButton value={pageLink} label={t('forms.copyLink')} />
        </div>
        <p>
          {t('freeCheck.helpLead')}{' '}
          <Link to="/free-check" className="text-gold underline-offset-4 hover:underline">
            {t('freeCheck.another')}
          </Link>
          .
        </p>
        <p className="text-[13px] text-muted/80">
          {t('freeCheck.validUntil', { date: formatDate(result.expires_at, i18n.language) })}. {t('forms.privateLink')}
        </p>
      </ReceiptFooter>
      <ReceiptSeal />
    </ReceiptPage>
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
