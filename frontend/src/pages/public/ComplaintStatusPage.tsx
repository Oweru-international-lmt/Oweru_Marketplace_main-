import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { FilesField, TextAreaField } from '../../components/FormFields'
import { FullPageLoader } from '../../components/FullPageLoader'
import { CalendarIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useNoReferrer } from '../../hooks/useNoReferrer'
import { useReveal } from '../../hooks/useReveal'
import { ApiError } from '../../lib/api'
import { whatsappLink } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatDate } from '../../lib/format'
import { servicesApi, type ComplaintStatus, type ComplaintSummary } from '../../lib/servicesApi'
import { Panel, ServiceColumns, ServiceHeader, ServicePage, Stages } from './services/ServiceUi'

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

function StatusView({ complaint, token, onChange }: { complaint: ComplaintSummary; token: string; onChange: (complaint: ComplaintSummary) => void }) {
  const { t, i18n } = useTranslation()
  useDocumentTitle(`${t('complaint.statusKicker')} ${complaint.reference}`)
  const root = useRef<HTMLDivElement>(null)
  useReveal(root, [complaint.status])
  const stages = [t('complaint.stages.received'), t('complaint.stages.review'), t('complaint.stages.resolved'), t('complaint.stages.closed')]
  const waiting = complaint.status === 'WAITING_INFORMATION'
  const decided = complaint.status === 'RESOLVED' || complaint.status === 'CLOSED'

  return (
    <ServicePage>
      <div ref={root}>
        <ServiceHeader kicker={t('complaint.statusKicker')} lead={complaint.reference}>
          <p className="mt-3 text-sm text-white/75 sm:text-muted">
            <CalendarIcon className="mr-1.5 inline size-4 align-[-3px]" />
            {t('complaint.dueBy', { date: formatDate(complaint.resolution_due_at, i18n.language) })}
          </p>
        </ServiceHeader>

        <ServiceColumns
          aside={
            <Panel tone="navy">
              <p className="text-sm leading-relaxed text-white/80">{t('complaint.helpBody')}</p>
              <a
                href={whatsappLink(`${t('site.supportMessage')} ${complaint.reference}`)}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 inline-flex h-11 items-center rounded-md bg-gold px-4 text-sm font-semibold text-navy hover:bg-gold-light"
              >
                {t('site.support')}
              </a>
            </Panel>
          }
        >
          <section data-reveal className="rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
            <Stages label={t('complaint.progress')} stages={stages} current={STAGE_OF[complaint.status]} />
            <div className={`mt-6 rounded-xl px-4 py-3 ${waiting ? 'bg-gold/15' : 'bg-paper'}`}>
              <p className="font-semibold text-navy">{t(`complaint.statuses.${complaint.status}`)}</p>
              <p className="mt-1 text-sm leading-relaxed text-navy/75">{t(`complaint.statusBody.${complaint.status}`)}</p>
            </div>
          </section>

          {(complaint.outcome || complaint.reasons) && (
            <section data-reveal className="space-y-4 rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
              {complaint.outcome && (
                <div>
                  <h2 className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('complaint.outcome')}</h2>
                  <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-line text-navy">{complaint.outcome}</p>
                </div>
              )}
              {complaint.reasons && (
                <div>
                  <h2 className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('complaint.reasons')}</h2>
                  <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-line text-navy">{complaint.reasons}</p>
                </div>
              )}
            </section>
          )}

          {OPEN.includes(complaint.status) && <ReplyForm complaintId={complaint.id} token={token} highlight={waiting} />}
          {decided && <FinalReviewForm complaint={complaint} token={token} onChange={onChange} />}
        </ServiceColumns>
      </div>
    </ServicePage>
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
    <form
      data-reveal
      noValidate
      onSubmit={(event) => void send(event)}
      className={`space-y-5 rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7 ${highlight ? 'ring-2 ring-gold/60' : ''}`}
    >
      <h2 className="text-lg font-semibold text-navy sm:font-serif sm:text-xl">{t('complaint.replyTitle')}</h2>
      <TextAreaField label={t('complaint.replyLabel')} rows={4} maxLength={10000} value={text} onChange={(event) => setText(event.target.value)} error={fieldError} />
      <FilesField label={`${t('complaint.stepEvidence')} ${t('forms.optional')}`} hint={t('complaint.evidenceHint')} files={files} onChange={setFiles} accept="image/jpeg,image/png,application/pdf" max={5} />
      <AnimatePresence>{sent && <Alert tone="success">{t('complaint.replySent')}</Alert>}</AnimatePresence>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="sm:max-w-xs">
        <Button type="submit" loading={sending} loadingLabel={t('listing.sending')}>
          {t('complaint.replySend')}
        </Button>
      </div>
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
    <section data-reveal className="rounded-2xl bg-white p-5 shadow-card sm:rounded-md sm:p-7">
      <h2 className="text-lg font-semibold text-navy sm:font-serif sm:text-xl">{t('complaint.reviewTitle')}</h2>
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
              <TextAreaField label={t('complaint.reviewLabel')} rows={4} maxLength={10000} value={reason} onChange={(event) => setReason(event.target.value)} error={fieldError} />
              {error && <Alert tone="error">{error}</Alert>}
              <div className="sm:max-w-xs">
                <Button type="submit" loading={sending} loadingLabel={t('listing.sending')}>
                  {t('complaint.reviewSend')}
                </Button>
              </div>
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
            className="mt-4 inline-flex h-11 items-center rounded-md bg-white px-4 text-sm font-semibold text-navy ring-1 ring-mist hover:ring-navy/30"
          >
            {t('complaint.reviewSend')}
          </motion.button>
        )}
      </AnimatePresence>
    </section>
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
