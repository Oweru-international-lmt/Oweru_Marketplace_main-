import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { DocumentIcon, LockIcon, SearchIcon, ShieldIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useNoReferrer } from '../../hooks/useNoReferrer'
import { ApiError } from '../../lib/api'
import { whatsappLink } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatDate } from '../../lib/format'
import { servicesApi, type ComplaintStatus, type ComplaintSummary } from '../../lib/servicesApi'
import { Field, PhotoBox } from './services/fields'
import { TrackingCard, Timeline, type Stage } from './services/tracking'

type Loaded = { key: string; complaint?: ComplaintSummary; failed?: 'invalid' | 'network' }

// CMP-05: the complainant follows progress through their private link.
export function ComplaintStatusPage() {
  const { complaintId = '' } = useParams()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const key = `${complaintId}:${token}`
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [attempt, setAttempt] = useState(0)
  useNoReferrer()

  useEffect(() => {
    let cancelled = false
    servicesApi
      .complaint(complaintId, token)
      .then((complaint) => !cancelled && setLoaded({ key, complaint }))
      .catch((error: unknown) => {
        if (cancelled) return
        const invalid = error instanceof ApiError && (error.status === 403 || error.status === 404)
        setLoaded({ key, failed: invalid ? 'invalid' : 'network' })
      })
    return () => {
      cancelled = true
    }
  }, [complaintId, token, key, attempt])

  const current = loaded?.key === key ? loaded : null
  if (!current) return <FullPageLoader inline />
  if (current.complaint) {
    return <StatusView complaint={current.complaint} token={token} onChange={(complaint) => setLoaded({ key, complaint })} />
  }
  return <InvalidLink network={current.failed === 'network'} onRetry={() => setAttempt((value) => value + 1)} />
}

// The six statuses on four milestones: waiting for information is part of the
// review, and a final review sits between the decision and closing.
const STAGE_OF: Record<ComplaintStatus, number> = { RECEIVED: 0, IN_REVIEW: 1, WAITING_INFORMATION: 1, RESOLVED: 2, UNDER_FINAL_REVIEW: 2, CLOSED: 3 }
const OPEN: ComplaintStatus[] = ['RECEIVED', 'IN_REVIEW', 'WAITING_INFORMATION', 'UNDER_FINAL_REVIEW']
const STAGES = [
  { name: 'received', icon: DocumentIcon },
  { name: 'review', icon: SearchIcon },
  { name: 'resolved', icon: ShieldIcon },
  { name: 'closed', icon: LockIcon },
] as const

function StatusView({ complaint, token, onChange }: { complaint: ComplaintSummary; token: string; onChange: (complaint: ComplaintSummary) => void }) {
  const { t, i18n } = useTranslation()
  useDocumentTitle(`${t('complaint.statusKicker')} ${complaint.reference}`)
  const current = STAGE_OF[complaint.status]
  // The current stage says what this exact status means; the others are generic.
  const stages: Stage[] = STAGES.map((stage, index) => ({
    label: index === current ? t(`complaint.statuses.${complaint.status}`) : t(`complaint.stages.${stage.name}`),
    body: index === current ? t(`complaint.statusBody.${complaint.status}`) : t(`complaint.stageBody.${stage.name}`),
    icon: stage.icon,
  }))
  const due = formatDate(complaint.resolution_due_at, i18n.language)
  const help = whatsappLink(`${t('site.supportMessage')} ${complaint.reference}`)
  const decided = complaint.status === 'RESOLVED' || complaint.status === 'CLOSED'

  return (
    <div className="mx-auto max-w-[860px] pb-16 lg:px-8 lg:pt-12">
      <div className="lg:hidden">
        <Timeline
          label={t('complaint.progress')}
          summary={[
            { label: t('complaint.statusLabel'), value: t(`complaint.stages.${STAGES[current].name}`) },
            { label: t('complaint.number'), value: <span className="font-mono text-base">{complaint.reference}</span> },
          ]}
          stages={stages}
          current={current}
        />
        <p className="border-t border-mist px-6 py-4 text-sm text-muted">{t('complaint.dueBy', { date: due })}</p>
      </div>
      <div className="hidden lg:block">
        <TrackingCard
          label={t('complaint.progress')}
          title={`${t('complaint.statusKicker')}  –  ${complaint.reference}`}
          facts={[
            { label: t('complaint.number'), value: <span className="font-mono">{complaint.reference}</span> },
            { label: t('complaint.statusLabel'), value: t(`complaint.statuses.${complaint.status}`) },
            { label: t('complaint.target'), value: due },
          ]}
          stages={stages}
          current={current}
          action={{ href: help, label: t('site.support'), icon: WhatsAppIcon }}
        />
        <p className="mt-10 text-[15px] leading-relaxed text-navy/80">{t(`complaint.statusBody.${complaint.status}`)}</p>
      </div>

      <div className="mt-2 space-y-5 px-4 lg:mt-8 lg:px-0">
        {(complaint.outcome || complaint.reasons) && (
          <section className="rounded-2xl bg-white p-6 shadow-card lg:rounded-md">
            {complaint.outcome && (
              <>
                <h2 className="text-[13px] font-medium tracking-[0.14em] text-navy/80 uppercase">{t('complaint.outcome')}</h2>
                <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-line text-navy">{complaint.outcome}</p>
              </>
            )}
            {complaint.reasons && (
              <>
                <h2 className="mt-5 border-t border-mist pt-5 text-[13px] font-medium tracking-[0.14em] text-navy/80 uppercase">{t('complaint.reasons')}</h2>
                <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-line text-navy">{complaint.reasons}</p>
              </>
            )}
          </section>
        )}

        {OPEN.includes(complaint.status) && <ReplyForm complaintId={complaint.id} token={token} highlight={complaint.status === 'WAITING_INFORMATION'} />}
        {decided && <FinalReviewForm complaint={complaint} token={token} onChange={onChange} />}

        <a
          href={help}
          target="_blank"
          rel="noopener noreferrer"
          className="flex h-12 items-center justify-center gap-2 rounded-full bg-white text-sm font-semibold text-navy ring-1 ring-mist transition-colors hover:ring-navy/30 lg:hidden"
        >
          <WhatsAppIcon className="size-4" />
          {t('site.support')}
        </a>
      </div>
    </div>
  )
}

function ReplyForm({ complaintId, token, highlight }: { complaintId: string; token: string; highlight: boolean }) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | undefined>()
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)

  async function send(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSent(false)
    if (!text.trim()) {
      setFieldError(t('validation.required'))
      return
    }
    const problem = firstFileProblem(files, EVIDENCE_TYPES)
    if (problem) {
      setError(t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name }))
      return
    }
    setFieldError(undefined)
    setSending(true)
    try {
      await servicesApi.replyToComplaint(complaintId, token, text.trim(), files)
      setText('')
      setFiles([])
      setSent(true)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setSending(false)
    }
  }

  return (
    <form noValidate onSubmit={(event) => void send(event)} className={`space-y-5 rounded-2xl bg-white p-6 shadow-card lg:rounded-md ${highlight ? 'ring-2 ring-gold/60' : ''}`}>
      <h2 className="text-lg font-bold text-navy">{t('complaint.replyTitle')}</h2>
      <Field label={t('complaint.replyLabel')} variant="filled" error={fieldError}>
        {(control) => (
          <textarea {...control} rows={4} maxLength={10000} className={`${control.className} resize-y py-3.5 leading-relaxed`} value={text} onChange={(event) => setText(event.target.value)} />
        )}
      </Field>
      <PhotoBox label={t('complaint.addEvidence')} files={files} onChange={setFiles} accept="image/jpeg,image/png,application/pdf" max={5} variant="filled" />
      <AnimatePresence>{sent && <Alert tone="success">{t('complaint.replySent')}</Alert>}</AnimatePresence>
      {error && <Alert tone="error">{error}</Alert>}
      <SendButton busy={sending} label={t('complaint.replySend')} busyLabel={t('listing.sending')} />
    </form>
  )
}

// CMP-07: one request, within the window the backend enforces.
function FinalReviewForm({ complaint, token, onChange }: { complaint: ComplaintSummary; token: string; onChange: (complaint: ComplaintSummary) => void }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [fieldError, setFieldError] = useState<string | undefined>()
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  async function send(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!reason.trim()) {
      setFieldError(t('validation.required'))
      return
    }
    setFieldError(undefined)
    setSending(true)
    try {
      onChange(await servicesApi.requestFinalReview(complaint.id, token, reason.trim()))
    } catch (failure) {
      const closed = failure instanceof ApiError && failure.status === 400 && /final review/i.test(failure.detail ?? '')
      setError(closed ? t('complaint.reviewClosed') : errorMessage(t, failure))
      setSending(false)
    }
  }

  return (
    <section className="rounded-2xl bg-white p-6 shadow-card lg:rounded-md">
      <h2 className="text-lg font-bold text-navy">{t('complaint.reviewTitle')}</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">{t('complaint.reviewBody')}</p>
      <AnimatePresence initial={false} mode="wait">
        {open ? (
          <motion.form
            key="form"
            noValidate
            onSubmit={(event) => void send(event)}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="space-y-5 pt-5">
              <Field label={t('complaint.reviewLabel')} variant="filled" error={fieldError}>
                {(control) => (
                  <textarea {...control} rows={4} maxLength={10000} className={`${control.className} resize-y py-3.5 leading-relaxed`} value={reason} onChange={(event) => setReason(event.target.value)} />
                )}
              </Field>
              {error && <Alert tone="error">{error}</Alert>}
              <SendButton busy={sending} label={t('complaint.reviewSend')} busyLabel={t('listing.sending')} />
            </div>
          </motion.form>
        ) : (
          <motion.button
            key="open"
            type="button"
            onClick={() => setOpen(true)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mt-4 inline-flex h-11 items-center rounded-full bg-paper px-5 text-sm font-semibold text-navy hover:bg-mist/70"
          >
            {t('complaint.reviewSend')}
          </motion.button>
        )}
      </AnimatePresence>
    </section>
  )
}

// S5's round Send button.
function SendButton({ busy, label, busyLabel }: { busy: boolean; label: string; busyLabel: string }) {
  return (
    <motion.button
      type="submit"
      whileTap={{ scale: 0.98 }}
      disabled={busy}
      aria-busy={busy || undefined}
      className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-full bg-gold text-[15px] font-semibold text-navy transition-colors hover:bg-gold-light disabled:opacity-70"
    >
      {busy && <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" />}
      {busy ? busyLabel : label}
    </motion.button>
  )
}

function InvalidLink({ network, onRetry }: { network: boolean; onRetry: () => void }) {
  const { t } = useTranslation()
  useDocumentTitle(t('complaint.invalidTitle'))
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-8">
      <h1 className="font-serif text-3xl font-semibold text-navy">{network ? t('search.errorTitle') : t('complaint.invalidTitle')}</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-muted">{network ? t('common.networkError') : t('complaint.invalidBody')}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {network && (
          <button type="button" onClick={onRetry} className="inline-flex h-12 items-center rounded-md bg-gold px-6 text-sm font-semibold text-navy hover:bg-gold-light">
            {t('common.retry')}
          </button>
        )}
        <Link to="/complaints/new" className="inline-flex h-12 items-center rounded-md bg-white px-6 text-sm font-semibold text-navy ring-1 ring-mist hover:ring-navy/30">
          {t('complaint.title')}
        </Link>
      </div>
    </div>
  )
}
