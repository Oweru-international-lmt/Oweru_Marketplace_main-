import { motion } from 'motion/react'
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { can, hasRole } from '../../../auth/access'
import { useAuth } from '../../../auth/useAuth'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { CheckIcon, ClockIcon, DocumentIcon, SearchIcon, ShieldIcon } from '../../../components/icons'
import { PageHeader } from '../../../components/PageHeader'
import { ApiError } from '../../../lib/api'
import { errorMessage } from '../../../lib/errors'
import { firstFileProblem, EVIDENCE_TYPES } from '../../../lib/files'
import { formatDate, formatNumber, formatTsh } from '../../../lib/format'
import { managementApi } from '../../../lib/managementApi'
import { openSigned } from '../../../lib/openSigned'
import { servicesApi, type FullCheck, type PaymentProofs } from '../../../lib/servicesApi'
import { staffApi } from '../../../lib/staffApi'
import { JobTasks } from './JobTasks'
import { Card, CheckChip } from './ui'

type Loaded = { id: string; job?: FullCheck; error?: string }

export function FullCheckDeskPage() {
  const { t } = useTranslation()
  const { jobId = '' } = useParams()
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((value) => value + 1), [])

  useEffect(() => {
    let cancelled = false
    servicesApi
      .fullCheck(jobId)
      .then((job) => !cancelled && setLoaded({ id: jobId, job }))
      .catch((error: unknown) => !cancelled && setLoaded({ id: jobId, error: errorMessage(t, error) }))
    return () => {
      cancelled = true
    }
  }, [jobId, version, t])

  const current = loaded?.id === jobId ? loaded : null
  if (!current) return <FullPageLoader inline />
  if (!current.job) return <Alert tone="error">{current.error}</Alert>
  return <Desk job={current.job} onChanged={reload} />
}

const FORM_ID = 'confirm-payment'

// After W9: the title with its date and the decision button top right; the
// bank slip shown large with the order's amount under it and the details
// below; status, the receipt form, attachments and the verifier on the right;
// a timeline at the bottom.
function Desk({ job, onChanged }: { job: FullCheck; onChanged: () => void }) {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  const [proofs, setProofs] = useState<PaymentProofs | null>(null)
  const [slip, setSlip] = useState<string | null>(null)
  const canConfirm = can(user, 'payment.confirm') && job.status === 'AWAITING_PAYMENT'
  const finished = job.status === 'PASSED' || job.status === 'PROBLEM_FOUND' || job.status === 'NOT_COMPLETED'

  // Only Management may read the buyer's slips; others simply don't see them.
  useEffect(() => {
    let cancelled = false
    if (!can(user, 'payment.confirm')) return
    servicesApi.paymentProofs(job.id).then(async (list) => {
      if (cancelled) return
      setProofs(list)
      const latest = list.proofs.at(-1)
      if (!latest) return
      const { url } = await servicesApi.paymentDocument(job.id, latest.document_id)
      if (!cancelled) setSlip(url)
    }, () => undefined)
    return () => {
      cancelled = true
    }
  }, [job.id, user])

  return (
    <>
      <PageHeader
        title={t('staff.check.title', { property: job.property_id })}
        crumbs={[{ label: t('staff.checks.title'), to: '/staff/full-checks' }, { label: job.property_id }]}
        actions={
          <div className="flex items-center gap-3">
            <span className="text-[13px] text-muted">{formatDate(job.created_at, i18n.language)}</span>
            {canConfirm && (
              <button
                type="submit"
                form={FORM_ID}
                className="inline-flex h-10 items-center gap-2 rounded-[6px] bg-gold px-4 text-[13px] font-semibold text-navy hover:bg-gold-light"
              >
                <CheckIcon className="size-4" />
                {t('staff.check.confirm')}
              </button>
            )}
            {/* FUL-07: only the responsible Verifier records the result. */}
            {job.status === 'UNDER_REVIEW' && hasRole(user, 'verifier') && (
              <Link
                to={`/staff/full-checks/${job.id}/result`}
                className="inline-flex h-10 items-center gap-2 rounded-[6px] bg-gold px-4 text-[13px] font-semibold text-navy hover:bg-gold-light"
              >
                <DocumentIcon className="size-4" />
                {t('staff.check.recordResult')}
              </Link>
            )}
          </div>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-5">
          <Card className="px-6 pt-5 pb-6">
            <h2 className="text-[15px] font-semibold text-navy">{t('staff.check.details')}</h2>
            <div className="mt-5 flex flex-col items-center">
              {slip ? (
                <button
                  type="button"
                  onClick={() => window.open(slip, '_blank', 'noopener')}
                  className="group relative block overflow-hidden rounded-[6px] border border-mist bg-paper shadow-card"
                  aria-label={t('staff.check.openSlip')}
                >
                  <img src={slip} alt={t('staff.check.slipAlt')} className="max-h-72 w-auto max-w-full object-contain" />
                  <span className="absolute inset-0 grid place-items-center bg-navy/0 transition-colors group-hover:bg-navy/20">
                    <span className="grid size-10 place-items-center rounded-full bg-white/90 text-navy opacity-80 shadow group-hover:opacity-100">
                      <SearchIcon className="size-5" />
                    </span>
                  </span>
                </button>
              ) : (
                <div className="grid h-40 w-full max-w-sm place-items-center rounded-[6px] border border-dashed border-mist text-center text-[13px] text-muted">
                  {can(user, 'payment.confirm') ? t('staff.check.noSlip') : t('staff.check.slipHidden')}
                </div>
              )}
              <p className="mt-6 text-[34px] leading-none font-semibold text-navy tabular-nums">{formatTsh(job.fee, i18n.language)}</p>
              <p className="mt-1.5 text-[13px] text-muted">{t('staff.check.amount')}</p>
            </div>
            <dl className="mt-7 space-y-3.5 text-[13px]">
              <Row label={t('listing.propertyId')} value={<span className="font-mono">{job.property_id}</span>} />
              <Row label={t('staff.checks.kind')} value={t(`staff.checks.kinds.${job.kind}`)} />
              <Row label={t('fullCheck.paymentReference')} value={<span className="font-mono text-xs break-all">{job.payment_reference}</span>} />
              <Row label={t('fullCheck.orderedOn')} value={formatDate(job.created_at, i18n.language)} />
              <Row label={t('staff.checks.status')} value={<CheckChip status={job.status} />} />
              {job.consent_due_at && <Row label={t('staff.check.consentDue')} value={formatDate(job.consent_due_at, i18n.language)} />}
            </dl>
          </Card>

          {(job.status === 'IN_PROGRESS' || job.status === 'UNDER_REVIEW' || finished) && <JobTasks job={job} canAct={hasRole(user, 'verifier') && !finished} />}

          <Timeline job={job} proofs={proofs} />
        </div>

        <div className="space-y-5">
          <Card className="px-5 py-5">
            <h2 className="text-[15px] font-semibold text-navy">{t('staff.check.statusTitle')}</h2>
            <div className="mt-4 flex flex-col items-center gap-3 text-center">
              <span className={`grid size-11 place-items-center rounded-full ${finished ? 'bg-success-soft text-success' : 'bg-gold/15 text-[#7a5410]'}`}>
                {finished ? <CheckIcon className="size-5" /> : <ClockIcon className="size-5" />}
              </span>
              <p className="text-[13px] leading-relaxed text-navy/80">{t(`staff.check.statusBody.${job.status}`)}</p>
            </div>
          </Card>

          {canConfirm && <ConfirmPayment job={job} onConfirmed={onChanged} />}

          {job.status === 'PASSED' && !job.invalidated_at && job.refresh_limit_at && hasRole(user, 'verifier') && <RefreshCheck job={job} onRefreshed={onChanged} />}

          {proofs && proofs.proofs.length > 0 && (
            <Card className="px-5 py-5">
              <h2 className="text-[15px] font-semibold text-navy">{t('staff.check.attachments')}</h2>
              <ul className="mt-3 space-y-2">
                {proofs.proofs.map((proof, index) => (
                  <li key={proof.id}>
                    <button
                      type="button"
                      onClick={() => void openSigned(() => servicesApi.paymentDocument(job.id, proof.document_id)).catch(() => undefined)}
                      className="flex w-full items-center gap-3 text-left text-[13px]"
                    >
                      <DocumentIcon className="size-5 shrink-0 text-muted" />
                      <span className="min-w-0 flex-1 truncate font-medium text-[#8a5f12] underline underline-offset-2">{t('staff.check.slipName', { index: index + 1 })}</span>
                      <span className="text-[11px] text-muted">{formatDate(proof.created_at, i18n.language)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {can(user, 'authorization.view') && !finished && <AssignVerifier job={job} onAssigned={onChanged} />}
        </div>
      </div>
    </>
  )
}

// FUL-09: within the six-month ceiling the verifier may extend reliance with a
// fresh assessment; a new report version is generated.
function RefreshCheck({ job, onRefreshed }: { job: FullCheck; onRefreshed: () => void }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [now] = useState(Date.now)
  if (!job.refresh_limit_at || new Date(job.refresh_limit_at).getTime() <= now) return null
  async function send() {
    setBusy(true)
    setError(null)
    try {
      await servicesApi.refreshFullCheck(job.id, text.trim())
      onRefreshed()
    } catch (failure) {
      setBusy(false)
      setError(errorMessage(t, failure))
    }
  }
  return (
    <Card className="px-5 py-5">
      <h2 className="text-[15px] font-semibold text-navy">{t('staff.check.refreshTitle')}</h2>
      <p className="mt-1 text-xs leading-relaxed text-muted">
        {t('staff.check.refreshBody', { expires: job.expires_at ? formatDate(job.expires_at, i18n.language) : '', limit: formatDate(job.refresh_limit_at as string, i18n.language) })}
      </p>
      {open ? (
        <div className="mt-3 space-y-3">
          <textarea rows={5} value={text} onChange={(event) => setText(event.target.value)} placeholder={t('staff.check.refreshPlaceholder')} className="w-full rounded-[6px] border border-mist px-3 py-2 text-[13px] text-navy outline-none focus:border-gold" />
          {error && <Alert tone="error">{error}</Alert>}
          <button type="button" disabled={busy || !text.trim()} onClick={() => void send()} className="h-10 w-full rounded-[6px] bg-gold text-[13px] font-semibold text-navy hover:bg-gold-light disabled:opacity-60">
            {busy ? t('listing.sending') : t('staff.check.refreshSend')}
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setOpen(true)} className="mt-3 h-10 w-full rounded-[6px] border border-mist text-[13px] font-medium text-navy hover:border-navy-soft/40">
          {t('staff.check.refresh')}
        </button>
      )}
    </Card>
  )
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6">
      <dt className="shrink-0 text-muted">{label}</dt>
      <dd className="min-w-0 text-right text-navy">{value}</dd>
    </div>
  )
}

// PAY-13: Management records Oweru's bank receipt. D3: the tax receipt is optional.
function ConfirmPayment({ job, onConfirmed }: { job: FullCheck; onConfirmed: () => void }) {
  const { t, i18n } = useTranslation()
  const [bankReference, setBankReference] = useState('')
  const [taxNumber, setTaxNumber] = useState('')
  const [taxReceipt, setTaxReceipt] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!bankReference.trim() || (taxReceipt && !taxNumber.trim())) {
      setError(t('staff.check.receiptRequired'))
      return
    }
    const problem = taxReceipt ? firstFileProblem([taxReceipt], EVIDENCE_TYPES) : null
    if (problem) {
      setError(t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name }))
      return
    }
    setBusy(true)
    try {
      await staffApi.confirmPayment(job.id, {
        amount: job.fee,
        reference: job.payment_reference,
        bank_reference: bankReference.trim(),
        tax_receipt_number: taxNumber.trim(),
        tax_receipt: taxReceipt,
      })
      onConfirmed()
    } catch (failure) {
      setBusy(false)
      setError(errorMessage(t, failure))
    }
  }

  const input = 'h-10 w-full rounded-[6px] border border-mist px-3 text-[13px] text-navy outline-none focus:border-gold'
  return (
    <Card className="px-5 py-5">
      <form id={FORM_ID} noValidate onSubmit={(event) => void confirm(event)}>
        <h2 className="text-[15px] font-semibold text-navy">{t('staff.check.receiptTitle')}</h2>
        <p className="mt-1 text-xs leading-relaxed text-muted">{t('staff.check.receiptBody', { amount: formatNumber(job.fee, i18n.language) })}</p>
        <div className="mt-4 space-y-3">
          <div>
            <label htmlFor="bank-reference" className="mb-1 block text-xs font-medium text-navy">
              {t('staff.check.bankReference')}
            </label>
            <input id="bank-reference" className={input} value={bankReference} onChange={(event) => setBankReference(event.target.value)} />
          </div>
          <div>
            <label htmlFor="tax-number" className="mb-1 block text-xs font-medium text-navy">
              {t('staff.check.taxNumber')} <span className="font-normal text-muted">{t('staff.check.optional')}</span>
            </label>
            <input id="tax-number" className={input} value={taxNumber} onChange={(event) => setTaxNumber(event.target.value)} />
          </div>
          <div>
            <span className="mb-1 block text-xs font-medium text-navy">{t('staff.check.taxReceipt')} <span className="font-normal text-muted">{t('staff.check.optional')}</span></span>
            <label className="flex h-10 cursor-pointer items-center gap-2 rounded-[6px] border border-dashed border-mist px-3 text-[13px] text-muted hover:border-gold">
              <DocumentIcon className="size-4 shrink-0" />
              <span className="truncate">{taxReceipt ? taxReceipt.name : t('staff.check.chooseFile')}</span>
              <input type="file" accept="image/jpeg,image/png,application/pdf" className="sr-only" onChange={(event) => setTaxReceipt(event.target.files?.[0] ?? null)} />
            </label>
          </div>
          {error && <Alert tone="error">{error}</Alert>}
          <button type="submit" disabled={busy} className="h-10 w-full rounded-[6px] bg-gold text-[13px] font-semibold text-navy hover:bg-gold-light disabled:opacity-60">
            {busy ? t('listing.sending') : t('staff.check.confirm')}
          </button>
        </div>
      </form>
    </Card>
  )
}

// Management names the responsible Verifier by email (FUL-04 handover).
function AssignVerifier({ job, onAssigned }: { job: FullCheck; onAssigned: () => void }) {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<{ tone: 'error' | 'success'; text: string } | null>(null)

  async function assign(event: FormEvent) {
    event.preventDefault()
    setNote(null)
    if (!email.trim()) return
    setBusy(true)
    try {
      const [account] = await managementApi.findAccount(email.trim())
      if (!account) {
        setNote({ tone: 'error', text: t('staff.complaint.noAccount') })
        return
      }
      await staffApi.assignVerifier(job.id, account.id)
      setNote({ tone: 'success', text: t('staff.check.verifierAssigned', { name: account.full_name }) })
      setEmail('')
      onAssigned()
    } catch (failure) {
      setNote({ tone: 'error', text: failure instanceof ApiError && failure.status === 403 ? t('staff.check.notVerifier') : errorMessage(t, failure) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="px-5 py-5">
      <form onSubmit={(event) => void assign(event)}>
        <h2 className="flex items-center gap-2 text-[15px] font-semibold text-navy">
          <ShieldIcon className="size-4 text-muted" />
          {t('staff.check.verifierTitle')}
        </h2>
        <label htmlFor="verifier-email" className="mt-3 mb-1 block text-xs text-muted">
          {t('staff.check.verifierLabel')}
        </label>
        <input
          id="verifier-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="jina@oweru.com"
          className="h-10 w-full rounded-[6px] border border-mist px-3 text-[13px] text-navy outline-none focus:border-gold"
        />
        {note && <p className={`mt-2 text-xs ${note.tone === 'error' ? 'text-danger' : 'text-success'}`}>{note.text}</p>}
        <button type="submit" disabled={busy} className="mt-3 h-10 w-full rounded-[6px] border border-mist text-[13px] font-semibold text-navy hover:border-navy/30 disabled:opacity-60">
          {busy ? t('listing.sending') : t('staff.check.assignVerifier')}
        </button>
      </form>
    </Card>
  )
}

// W9's timeline: what has happened to the order so far.
function Timeline({ job, proofs }: { job: FullCheck; proofs: PaymentProofs | null }) {
  const { t, i18n } = useTranslation()
  const events = [
    { at: job.created_at, text: t('staff.check.events.ordered') },
    ...(proofs?.proofs ?? []).map((proof) => ({ at: proof.created_at, text: t('staff.check.events.slip') })),
    ...(job.completed_at ? [{ at: job.completed_at, text: t('staff.check.events.completed', { status: t(`fullCheck.statuses.${job.status}`) }) }] : []),
  ].sort((a, b) => a.at.localeCompare(b.at))

  return (
    <Card className="px-6 pt-5 pb-6">
      <h2 className="text-[15px] font-semibold text-navy">{t('staff.check.timeline')}</h2>
      <ol className="mt-4 space-y-4">
        {events.map((event, index) => (
          <motion.li key={`${event.at}-${index}`} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.05 }} className="flex items-start gap-3">
            <span className="mt-1.5 size-2 shrink-0 rounded-full bg-gold" />
            <div>
              <p className="text-[13px] text-navy">{event.text}</p>
              <p className="text-[11px] text-muted">{formatDate(event.at, i18n.language)}</p>
            </div>
          </motion.li>
        ))}
      </ol>
    </Card>
  )
}
