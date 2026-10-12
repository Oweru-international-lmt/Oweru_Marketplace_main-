import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, BanknoteIcon, CheckIcon, ClockIcon, DocumentIcon, SearchIcon, ShieldIcon, UserIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ApiError } from '../../lib/api'
import { whatsappLink } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatDate, formatNumber, formatTsh } from '../../lib/format'
import { openSigned } from '../../lib/openSigned'
import { servicesApi, type FullCheck, type FullCheckStatus, type PaymentInstructions, type PaymentProofs } from '../../lib/servicesApi'
import { PhotoBox } from './services/fields'
import { CopyButton } from './services/ServiceUi'
import { TrackingCard, Timeline, type Stage } from './services/tracking'

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
const STAGES = [
  { name: 'payment', icon: BanknoteIcon },
  { name: 'consent', icon: UserIcon },
  { name: 'checks', icon: SearchIcon },
  { name: 'review', icon: DocumentIcon },
  { name: 'result', icon: ShieldIcon },
] as const

function JobView({ job }: { job: FullCheck }) {
  const { t, i18n } = useTranslation()
  useDocumentTitle(`${t('fullCheck.title')} ${job.property_id}`)
  const current = STAGE_OF[job.status]
  const stopped = job.status === 'PROBLEM_FOUND' || job.status === 'NOT_COMPLETED'
  const stages: Stage[] = STAGES.map((stage, index) => ({
    label: index === current ? t(`fullCheck.statuses.${job.status}`) : t(`fullCheck.stages.${stage.name}`),
    body: index === current ? t(`fullCheck.statusBody.${job.status}`) : t(`fullCheck.stageBody.${stage.name}`),
    icon: stage.icon,
  }))
  const ordered = formatDate(job.created_at, i18n.language)

  return (
    <div className="mx-auto max-w-[1080px] pb-16 lg:px-8 lg:pt-12">
      <div className="lg:hidden">
        <Timeline
          label={t('fullCheck.progress')}
          summary={[
            { label: t('fullCheck.statusLabel'), value: t(`fullCheck.stages.${STAGES[current].name}`) },
            { label: t('listing.propertyId'), value: <span className="font-mono text-base">{job.property_id}</span> },
          ]}
          stages={stages}
          current={current}
          stopped={stopped}
        />
      </div>
      <div className="hidden lg:block">
        <TrackingCard
          label={t('fullCheck.progress')}
          title={`${t('fullCheck.title')}  –  ${job.property_id}`}
          facts={[
            { label: t('fullCheck.statusLabel'), value: t(`fullCheck.statuses.${job.status}`) },
            { label: t('fullCheck.fee'), value: formatTsh(job.fee, i18n.language) },
            { label: t('fullCheck.orderedOn'), value: ordered },
          ]}
          stages={stages}
          current={current}
          stopped={stopped}
          action={{ href: whatsappLink(`${t('site.supportMessage')} ${job.property_id}`), label: t('site.support'), icon: WhatsAppIcon }}
        />
      </div>

      <div className="mt-2 px-4 lg:mt-12 lg:grid lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-8 lg:px-0">
        <div className="space-y-5">
          {job.status === 'AWAITING_PAYMENT' && <Payment job={job} />}
          {job.status === 'AWAITING_CONSENT' && job.consent_due_at && (
            <Note>{t('fullCheck.consentDue', { date: formatDate(job.consent_due_at, i18n.language) })}</Note>
          )}
          {current === 4 && <Result job={job} />}
        </div>
        <aside className="mt-5 space-y-5 lg:mt-0">
          <section className="rounded-2xl bg-white p-6 shadow-card lg:rounded-md">
            <h2 className="text-[13px] font-medium tracking-[0.14em] text-navy/80 uppercase">{t('fullCheck.scope')}</h2>
            <p className="mt-3 text-sm leading-relaxed text-navy/80">{job.scope_snapshot.scope}</p>
          </section>
          <Link
            to="/full-checks"
            className="flex h-12 items-center justify-center rounded-full bg-white text-sm font-semibold text-navy ring-1 ring-mist transition-colors hover:ring-navy/30"
          >
            {t('fullCheck.openChecks')}
          </Link>
        </aside>
      </div>
    </div>
  )
}

function Note({ children }: { children: ReactNode }) {
  return <p className="rounded-2xl bg-white p-6 text-[15px] leading-relaxed text-navy shadow-card lg:rounded-md">{children}</p>
}

type PaymentState = { instructions?: PaymentInstructions; error?: string }

// PAY-13 for the full check, after S8: a title row over a navy rule, a
// "waiting for payment" banner, the amount in a box, the bank details as
// rows with a status pill, and a fee summary box. The slip upload follows.
function Payment({ job }: { job: FullCheck }) {
  const { t, i18n } = useTranslation()
  const [state, setState] = useState<PaymentState | null>(null)
  const [proofs, setProofs] = useState<PaymentProofs | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let cancelled = false
    servicesApi
      .paymentInstructions(job.id)
      .then((instructions) => !cancelled && setState({ instructions }))
      .catch((error: unknown) => !cancelled && setState({ error: errorMessage(t, error) }))
    return () => {
      cancelled = true
    }
  }, [job.id, t])

  // Only the slip list changes after an upload. A failed refresh keeps the
  // list already shown rather than hiding the bank details.
  useEffect(() => {
    let cancelled = false
    servicesApi.paymentProofs(job.id).then(
      (list) => !cancelled && setProofs(list),
      () => undefined,
    )
    return () => {
      cancelled = true
    }
  }, [job.id, reload])

  if (!state) return <FullPageLoader inline />
  if (state.error || !state.instructions) return <Alert tone="error">{state.error ?? t('common.unexpectedError')}</Alert>
  const { instructions } = state
  const [amount, currency] = [formatNumber(instructions.amount, i18n.language), instructions.currency === 'TZS' ? 'TSh' : instructions.currency]

  return (
    <>
      <section aria-labelledby="pay-title" className="overflow-hidden rounded-2xl bg-white shadow-card lg:rounded-md">
        <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-4">
          <h2 id="pay-title" className="text-xl font-bold text-navy">
            {t('fullCheck.payTitle')}
          </h2>
          <p className="text-right text-xs leading-tight text-muted">
            {t('fullCheck.orderedOn')}
            <br />
            <span className="text-sm">{formatDate(job.created_at, i18n.language)}</span>
          </p>
        </div>
        <div aria-hidden="true" className="h-1 bg-navy" />
        <div className="flex items-center gap-4 border-l-4 border-gold bg-gold/10 px-5 py-4">
          <span className="grid size-7 shrink-0 place-items-center rounded-full bg-gold text-navy">
            <ClockIcon className="size-4" />
          </span>
          <div>
            <p className="text-[17px] font-semibold text-[#7a5410]">{t('fullCheck.statuses.AWAITING_PAYMENT')}</p>
            <p className="text-sm text-[#7a5410]/90">{t('fullCheck.payBody')}</p>
          </div>
        </div>

        <div className="px-6 pt-6 pb-7">
          <div className="rounded-xl border border-mist px-4 py-5 text-center">
            <p className="text-sm text-muted">{t('fullCheck.amountToPay')}</p>
            <p className="mt-1 text-[34px] leading-tight font-bold text-navy sm:text-[40px]">
              {amount} <span className="text-xl font-semibold text-muted">{currency}</span>
            </p>
          </div>

          <h3 className="mt-8 border-b-2 border-mist pb-3 text-xl font-bold text-navy">{t('fullCheck.paymentDetails')}</h3>
          <dl className="divide-y divide-mist">
            <PayRow label={t('fullCheck.bankName')} value={instructions.bank.bank_name} />
            <PayRow label={t('fullCheck.accountName')} value={instructions.bank.account_name} />
            <PayRow label={t('fullCheck.accountNumber')} value={<span className="font-mono">{instructions.bank.account_number}</span>} copy={instructions.bank.account_number} />
            <PayRow label={t('fullCheck.branch')} value={instructions.bank.branch} />
            <PayRow
              label={t('fullCheck.paymentReference')}
              value={<span className="font-mono text-sm break-all">{instructions.reference}</span>}
              copy={instructions.reference}
            />
            <PayRow
              label={t('fullCheck.statusLabel')}
              value={
                <span className="inline-flex items-center gap-1.5 rounded-full bg-gold/20 px-3 py-1 text-sm font-medium text-[#7a5410]">
                  <ClockIcon className="size-4" />
                  {t('fullCheck.pending')}
                </span>
              }
            />
          </dl>

          <div className="mt-6 rounded-xl border border-gold/30 bg-gold/[0.07] px-5 py-5">
            <h3 className="text-[17px] font-bold text-navy">{t('fullCheck.breakdown')}</h3>
            <dl className="mt-3 space-y-2 text-[15px]">
              <div className="flex justify-between gap-4">
                <dt className="text-navy/75">{t('fullCheck.fee')}</dt>
                <dd className="font-semibold text-navy">{formatTsh(instructions.amount, i18n.language)}</dd>
              </div>
              <div className="flex justify-between gap-4 border-t border-gold/25 pt-2">
                <dt className="font-semibold text-navy">{t('fullCheck.total')}</dt>
                <dd className="font-bold text-navy">{formatTsh(instructions.amount, i18n.language)}</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      <SlipUpload jobId={job.id} proofs={proofs} onUploaded={() => setReload((value) => value + 1)} />
    </>
  )
}

function PayRow({ label, value, copy }: { label: string; value: ReactNode; copy?: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <dt className="shrink-0 text-[15px] text-muted">{label}</dt>
      <dd className="flex min-w-0 items-center justify-end gap-2.5 text-right text-[15px] font-semibold text-navy">
        <span className="min-w-0">{value}</span>
        {copy && <CopyButton value={copy} />}
      </dd>
    </div>
  )
}

function SlipUpload({ jobId, proofs, onUploaded }: { jobId: string; proofs: PaymentProofs | null; onUploaded: () => void }) {
  const { t, i18n } = useTranslation()
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [viewError, setViewError] = useState<string | null>(null)

  async function upload(event: FormEvent) {
    event.preventDefault()
    setUploadError(null)
    setSent(false)
    const file = files[0]
    if (!file) {
      setUploadError(t('fullCheck.slipRequired'))
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
      onUploaded()
    } catch (error) {
      setUploadError(errorMessage(t, error))
    } finally {
      setUploading(false)
    }
  }

  return (
    <form noValidate onSubmit={(event) => void upload(event)} className="space-y-5 rounded-2xl bg-white p-6 shadow-card lg:rounded-md">
      <div>
        <h2 className="text-lg font-bold text-navy">{t('fullCheck.slipTitle')}</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted">{t('fullCheck.slipBody')}</p>
      </div>
      <PhotoBox label={t('fullCheck.slipAdd')} files={files} onChange={setFiles} accept="image/jpeg,image/png,application/pdf" max={1} variant="filled" error={uploadError ?? undefined} />
      <AnimatePresence>{sent && <Alert tone="success">{t('fullCheck.slipSent')}</Alert>}</AnimatePresence>
      <motion.button
        type="submit"
        whileTap={{ scale: 0.98 }}
        disabled={uploading}
        aria-busy={uploading || undefined}
        className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-full bg-gold text-[15px] font-semibold text-navy transition-colors hover:bg-gold-light disabled:opacity-70"
      >
        {uploading && <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" />}
        {uploading ? t('fullCheck.slipUploading') : t('fullCheck.slipUpload')}
      </motion.button>

      {proofs && proofs.proofs.length > 0 && (
        <div className="border-t border-mist pt-5">
          <h3 className="text-[13px] font-medium tracking-[0.14em] text-navy/80 uppercase">{t('fullCheck.slips')}</h3>
          <ul className="mt-3 divide-y divide-mist">
            {proofs.proofs.map((proof) => (
              <li key={proof.id} className="flex items-center gap-3 py-3">
                <DocumentIcon className="size-5 shrink-0 text-navy/70" />
                <span className="flex-1 text-sm text-navy">{t('fullCheck.slipOn', { date: formatDate(proof.created_at, i18n.language) })}</span>
                <button
                  type="button"
                  onClick={() => {
                    setViewError(null)
                    openSigned(() => servicesApi.paymentDocument(jobId, proof.document_id)).catch((error: unknown) => setViewError(errorMessage(t, error)))
                  }}
                  className="h-9 rounded-full bg-paper px-4 text-xs font-semibold text-navy hover:bg-mist/70"
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
  )
}

// FUL-07: the verifier's result and versioned reports, for the paying buyer only.
function Result({ job }: { job: FullCheck }) {
  const { t, i18n } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const passed = job.status === 'PASSED'

  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-card lg:rounded-md">
      <div className={`flex items-center gap-4 border-l-4 px-5 py-4 ${passed ? 'border-success bg-success-soft' : 'border-danger bg-danger-soft'}`}>
        <span className={`grid size-7 shrink-0 place-items-center rounded-full text-white ${passed ? 'bg-success' : 'bg-danger'}`}>
          {passed ? <CheckIcon className="size-4" /> : <AlertIcon className="size-4" />}
        </span>
        <div>
          <p className={`text-[17px] font-semibold ${passed ? 'text-success' : 'text-danger'}`}>{t(`fullCheck.statuses.${job.status}`)}</p>
          {passed && job.expires_at && !job.invalidated_at && (
            <p className="text-sm text-success/90">{t('fullCheck.validUntil', { date: formatDate(job.expires_at, i18n.language) })}</p>
          )}
        </div>
      </div>
      <div className="px-6 pt-5 pb-7">
        {job.invalidated_at && <p className="mb-5 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">{t('fullCheck.invalidated')}</p>}
        {job.result?.risk_assessment && (
          <>
            <h2 className="border-b-2 border-mist pb-3 text-xl font-bold text-navy">{t('fullCheck.risk')}</h2>
            <p className="mt-4 text-[15px] leading-relaxed whitespace-pre-line text-navy/85">{job.result.risk_assessment}</p>
          </>
        )}
        {job.result && job.result.not_checked.length > 0 && (
          <div className="mt-6 rounded-xl border border-gold/30 bg-gold/[0.07] px-5 py-5">
            <h3 className="text-[17px] font-bold text-navy">{t('fullCheck.notChecked')}</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-navy/80">
              {job.result.not_checked.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}
        {job.reports && job.reports.length > 0 && (
          <div className="mt-6">
            <h3 className="text-[13px] font-medium tracking-[0.14em] text-navy/80 uppercase">{t('fullCheck.reports')}</h3>
            <ul className="mt-3 divide-y divide-mist">
              {job.reports.map((report) => (
                <li key={report.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setError(null)
                      openSigned(() => servicesApi.fullCheckReport(job.id, report.id)).catch((failure: unknown) => setError(errorMessage(t, failure)))
                    }}
                    className="flex w-full items-center gap-3 py-3 text-left text-sm font-semibold text-navy hover:text-gold"
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
          </div>
        )}
      </div>
    </section>
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
