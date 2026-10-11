import { AnimatePresence } from 'motion/react'
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { FilesField } from '../../components/FormFields'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, BanknoteIcon, CheckIcon, DocumentIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useReveal } from '../../hooks/useReveal'
import { ApiError } from '../../lib/api'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatDate, formatTsh } from '../../lib/format'
import { servicesApi, type FullCheck, type FullCheckStatus, type PaymentInstructions, type PaymentProofs } from '../../lib/servicesApi'
import { CopyButton, Panel, ServiceColumns, ServiceHeader, ServicePage, Stages } from './services/ServiceUi'

type Loaded = { id: string; job?: FullCheck; failed?: 'missing' | 'network' }

export function FullCheckPage() {
  const { jobId = '' } = useParams()
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    servicesApi
      .fullCheck(jobId)
      .then((job) => !cancelled && setLoaded({ id: jobId, job }))
      .catch((error: unknown) => {
        if (cancelled) return
        const missing = error instanceof ApiError && (error.status === 404 || error.status === 400)
        setLoaded({ id: jobId, failed: missing ? 'missing' : 'network' })
      })
    return () => {
      cancelled = true
    }
  }, [jobId, attempt])

  const current = loaded?.id === jobId ? loaded : null
  if (!current) return <FullPageLoader inline />
  if (current.job) return <JobView job={current.job} />
  return <Missing network={current.failed === 'network'} onRetry={() => setAttempt((value) => value + 1)} />
}

const STAGE_OF: Record<FullCheckStatus, number> = {
  AWAITING_PAYMENT: 0,
  AWAITING_CONSENT: 1,
  IN_PROGRESS: 2,
  UNDER_REVIEW: 3,
  PASSED: 4,
  PROBLEM_FOUND: 4,
  NOT_COMPLETED: 4,
}

// Signed document links open in a new tab. The tab opens on the click itself,
// before the request, so phone browsers don't block it as a popup.
async function openSigned(load: () => Promise<{ url: string }>): Promise<void> {
  const tab = window.open('', '_blank')
  if (tab) tab.opener = null
  try {
    const { url } = await load()
    if (tab) tab.location.href = url
    else window.location.assign(url)
  } catch (error) {
    tab?.close()
    throw error
  }
}

function JobView({ job }: { job: FullCheck }) {
  const { t, i18n } = useTranslation()
  useDocumentTitle(`${t('fullCheck.title')} ${job.property_id}`)
  const root = useRef<HTMLDivElement>(null)
  useReveal(root, [job.status])
  const stages = (['payment', 'consent', 'checks', 'review', 'result'] as const).map((stage) => t(`fullCheck.stages.${stage}`))
  const finished = STAGE_OF[job.status] === 4

  return (
    <ServicePage>
      <div ref={root}>
        <ServiceHeader kicker={t('fullCheck.kicker')} lead={t(`fullCheck.statuses.${job.status}`)}>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-white/75 sm:text-muted">
            <span>
              {t('listing.propertyId')}: <span className="font-semibold text-white sm:text-navy">{job.property_id}</span>
            </span>
            <span>{formatTsh(job.fee, i18n.language)}</span>
            <span>{t('fullCheck.ordered', { date: formatDate(job.created_at, i18n.language) })}</span>
          </div>
        </ServiceHeader>

        <ServiceColumns
          aside={
            <Panel title={t('fullCheck.scope')}>
              <p className="text-sm leading-relaxed text-navy/80">{job.scope_snapshot.scope}</p>
              <Link to="/full-checks" className="text-link mt-5 inline-block text-sm">
                {t('fullCheck.openChecks')}
              </Link>
            </Panel>
          }
        >
          <section data-reveal className="rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
            <Stages label={t('fullCheck.progress')} stages={stages} current={STAGE_OF[job.status]} stopped={job.status === 'PROBLEM_FOUND' || job.status === 'NOT_COMPLETED'} />
          </section>

          {job.status === 'AWAITING_PAYMENT' && <Payment jobId={job.id} />}
          {job.status === 'AWAITING_CONSENT' && (
            <StatusNote>
              {t('fullCheck.consentBody')} {job.consent_due_at && t('fullCheck.consentDue', { date: formatDate(job.consent_due_at, i18n.language) })}
            </StatusNote>
          )}
          {job.status === 'IN_PROGRESS' && <StatusNote>{t('fullCheck.progressBody')}</StatusNote>}
          {job.status === 'UNDER_REVIEW' && <StatusNote>{t('fullCheck.reviewBody')}</StatusNote>}
          {finished && <Result job={job} />}
        </ServiceColumns>
      </div>
    </ServicePage>
  )
}

function StatusNote({ children }: { children: ReactNode }) {
  return (
    <p data-reveal className="rounded-2xl bg-white p-5 text-[15px] leading-relaxed text-navy shadow-card sm:rounded-md sm:p-6">
      {children}
    </p>
  )
}

type PaymentState = { instructions?: PaymentInstructions; error?: string }

// PAY-13 for the full check: Oweru's bank details with the frozen amount and
// reference, then the buyer's slip, which management confirms.
function Payment({ jobId }: { jobId: string }) {
  const { t, i18n } = useTranslation()
  const [state, setState] = useState<PaymentState | null>(null)
  const [proofs, setProofs] = useState<PaymentProofs | null>(null)
  const [reload, setReload] = useState(0)
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [viewError, setViewError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    servicesApi
      .paymentInstructions(jobId)
      .then((instructions) => !cancelled && setState({ instructions }))
      .catch((error: unknown) => !cancelled && setState({ error: errorMessage(t, error) }))
    return () => {
      cancelled = true
    }
  }, [jobId, t])

  // Only the slip list changes after an upload. A failed refresh keeps the
  // list already shown rather than hiding the bank details.
  useEffect(() => {
    let cancelled = false
    servicesApi.paymentProofs(jobId).then(
      (list) => !cancelled && setProofs(list),
      () => undefined,
    )
    return () => {
      cancelled = true
    }
  }, [jobId, reload])

  async function upload(event: FormEvent) {
    event.preventDefault()
    setUploadError(null)
    setSent(false)
    const file = files[0]
    if (!file) {
      setUploadError(t('validation.required'))
      return
    }
    const problem = firstFileProblem([file], EVIDENCE_TYPES)
    if (problem) {
      setUploadError(t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name }))
      return
    }
    setUploading(true)
    try {
      await servicesApi.uploadPaymentProof(jobId, file)
      setFiles([])
      setSent(true)
      setReload((value) => value + 1)
    } catch (error) {
      setUploadError(errorMessage(t, error))
    } finally {
      setUploading(false)
    }
  }

  if (!state) return <FullPageLoader inline />
  if (state.error || !state.instructions) return <Alert tone="error">{state.error ?? t('common.unexpectedError')}</Alert>
  const { instructions } = state
  const rows = [
    { label: t('fullCheck.bankName'), value: instructions.bank.bank_name },
    { label: t('fullCheck.accountName'), value: instructions.bank.account_name },
    { label: t('fullCheck.accountNumber'), value: instructions.bank.account_number, copy: true },
    { label: t('fullCheck.branch'), value: instructions.bank.branch },
  ]

  return (
    <>
      <section data-reveal aria-labelledby="pay-title" className="rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
        <div className="flex items-start gap-4">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-gold/15 text-gold">
            <BanknoteIcon className="size-5" />
          </span>
          <div>
            <h2 id="pay-title" className="text-lg font-semibold text-navy sm:font-serif sm:text-xl">
              {t('fullCheck.payTitle')}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-muted">{t('fullCheck.payBody')}</p>
          </div>
        </div>

        <div className="mt-6 rounded-xl bg-navy p-5 text-white">
          <p className="text-xs text-white/60">{t('fullCheck.amount')}</p>
          <p className="mt-1 font-serif text-3xl font-semibold">{formatTsh(instructions.amount, i18n.language)}</p>
          <p className="mt-4 text-xs text-white/60">{t('fullCheck.paymentReference')}</p>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <span className="font-mono text-sm break-all text-gold-light">{instructions.reference}</span>
            <CopyButton value={instructions.reference} />
          </div>
        </div>

        <dl className="mt-5 divide-y divide-mist">
          {rows.map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-4 py-3">
              <dt className="text-sm text-muted">{row.label}</dt>
              <dd className="flex min-w-0 items-center gap-3 text-right text-sm font-semibold text-navy">
                <span className={row.copy ? 'font-mono whitespace-nowrap' : 'break-words'}>{row.value}</span>
                {row.copy && <CopyButton value={row.value} />}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <form data-reveal noValidate onSubmit={(event) => void upload(event)} className="space-y-5 rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
        <div>
          <h2 className="text-lg font-semibold text-navy sm:font-serif sm:text-xl">{t('fullCheck.slipTitle')}</h2>
          <p className="mt-1 text-sm leading-relaxed text-muted">{t('fullCheck.slipBody')}</p>
        </div>
        <FilesField label={t('fullCheck.slipTitle')} files={files} onChange={setFiles} accept="image/jpeg,image/png,application/pdf" max={1} error={uploadError ?? undefined} />
        <AnimatePresence>{sent && <Alert tone="success">{t('fullCheck.slipSent')}</Alert>}</AnimatePresence>
        <div className="sm:max-w-xs">
          <Button type="submit" loading={uploading} loadingLabel={t('fullCheck.slipUploading')}>
            {t('fullCheck.slipUpload')}
          </Button>
        </div>

        {proofs && proofs.proofs.length > 0 && (
          <div className="border-t border-mist pt-5">
            <h3 className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('fullCheck.slips')}</h3>
            <ul className="mt-3 space-y-2">
              {proofs.proofs.map((proof) => (
                <li key={proof.id} className="flex items-center gap-3 rounded-xl bg-paper px-3 py-2.5">
                  <DocumentIcon className="size-4 shrink-0 text-navy" />
                  <span className="flex-1 text-sm text-navy">{t('fullCheck.slipOn', { date: formatDate(proof.created_at, i18n.language) })}</span>
                  <button
                    type="button"
                    onClick={() => {
                      setViewError(null)
                      openSigned(() => servicesApi.paymentDocument(jobId, proof.document_id)).catch((error: unknown) => setViewError(errorMessage(t, error)))
                    }}
                    className="h-9 rounded-full bg-white px-3 text-xs font-semibold text-navy ring-1 ring-mist hover:ring-navy/30"
                  >
                    {t('fullCheck.view')}
                  </button>
                </li>
              ))}
            </ul>
            {viewError && (
              <div className="mt-3">
                <Alert tone="error">{viewError}</Alert>
              </div>
            )}
          </div>
        )}
      </form>
    </>
  )
}

// FUL-07: the verifier's result and versioned reports, for the paying buyer only.
function Result({ job }: { job: FullCheck }) {
  const { t, i18n } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const passed = job.status === 'PASSED'
  const Icon = passed ? CheckIcon : AlertIcon

  return (
    <>
      <section data-reveal className="rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
        <p className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('fullCheck.resultTitle')}</p>
        <div className="mt-3 flex items-center gap-3">
          <span className={`grid size-11 place-items-center rounded-full ${passed ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'}`}>
            <Icon className="size-6" />
          </span>
          <p className="font-serif text-2xl font-semibold text-navy">{t(`fullCheck.statuses.${job.status}`)}</p>
        </div>
        {job.invalidated_at && <p className="mt-4 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">{t('fullCheck.invalidated')}</p>}
        {passed && job.expires_at && !job.invalidated_at && (
          <p className="mt-3 text-sm text-muted">{t('fullCheck.validUntil', { date: formatDate(job.expires_at, i18n.language) })}</p>
        )}
        {job.result?.risk_assessment && (
          <div className="mt-6">
            <h2 className="text-sm font-semibold text-navy">{t('fullCheck.risk')}</h2>
            <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-line text-navy/85">{job.result.risk_assessment}</p>
          </div>
        )}
        {job.result && job.result.not_checked.length > 0 && (
          <div className="mt-6">
            <h2 className="text-sm font-semibold text-navy">{t('fullCheck.notChecked')}</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-navy/80">
              {job.result.not_checked.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {job.reports && job.reports.length > 0 && (
        <section data-reveal className="rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
          <h2 className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('fullCheck.reports')}</h2>
          <ul className="mt-3 space-y-2">
            {job.reports.map((report) => (
              <li key={report.id}>
                <button
                  type="button"
                  onClick={() => {
                    setError(null)
                    openSigned(() => servicesApi.fullCheckReport(job.id, report.id)).catch((failure: unknown) => setError(errorMessage(t, failure)))
                  }}
                  className="flex w-full items-center gap-3 rounded-xl bg-paper px-4 py-3 text-left text-sm font-semibold text-navy transition-colors hover:bg-mist/60"
                >
                  <DocumentIcon className="size-5 text-gold" />
                  {t('fullCheck.reportVersion', { version: report.version })}
                  <span className="ml-auto text-xs font-medium text-muted uppercase">{report.language}</span>
                </button>
              </li>
            ))}
          </ul>
          {error && (
            <div className="mt-3">
              <Alert tone="error">{error}</Alert>
            </div>
          )}
        </section>
      )}
    </>
  )
}

function Missing({ network, onRetry }: { network: boolean; onRetry: () => void }) {
  const { t } = useTranslation()
  useDocumentTitle(t('fullCheck.missingTitle'))
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-8">
      <h1 className="font-serif text-3xl font-semibold text-navy">{network ? t('search.errorTitle') : t('fullCheck.missingTitle')}</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-muted">{network ? t('common.networkError') : t('fullCheck.missingBody')}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {network && (
          <button type="button" onClick={onRetry} className="inline-flex h-12 items-center rounded-md bg-gold px-6 text-sm font-semibold text-navy hover:bg-gold-light">
            {t('common.retry')}
          </button>
        )}
        <Link to="/full-checks" className="inline-flex h-12 items-center rounded-md bg-white px-6 text-sm font-semibold text-navy ring-1 ring-mist hover:ring-navy/30">
          {t('fullCheck.openChecks')}
        </Link>
      </div>
    </div>
  )
}
