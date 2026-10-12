import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { can } from '../../../auth/access'
import { useAuth } from '../../../auth/useAuth'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import {
  AlertIcon,
  ArrowRightIcon,
  CalendarIcon,
  CheckIcon,
  ChevronDownIcon,
  CloseIcon,
  DocumentIcon,
  ImageIcon,
  LockIcon,
  SearchIcon,
  ShieldIcon,
  UsersIcon,
  WhatsAppIcon,
} from '../../../components/icons'
import { PageHeader } from '../../../components/PageHeader'
import { ApiError } from '../../../lib/api'
import { whatsappTo } from '../../../lib/config'
import { errorMessage } from '../../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../../lib/files'
import { formatDate, formatShortDate } from '../../../lib/format'
import { initials } from '../../../lib/initials'
import { managementApi } from '../../../lib/managementApi'
import { openSigned } from '../../../lib/openSigned'
import { formatPhone } from '../../../lib/phone'
import type { ComplaintStatus } from '../../../lib/servicesApi'
import { NEXT_STATUSES, staffApi, type DeskComplaintDetail } from '../../../lib/staffApi'
import { ComplaintChip } from './ui'

type Loaded = { id: string; complaint?: DeskComplaintDetail; error?: string }

export function ComplaintDetailPage() {
  const { t } = useTranslation()
  const { complaintId = '' } = useParams()
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((value) => value + 1), [])

  useEffect(() => {
    let cancelled = false
    staffApi
      .complaint(complaintId)
      .then((complaint) => !cancelled && setLoaded({ id: complaintId, complaint }))
      .catch((error: unknown) => !cancelled && setLoaded({ id: complaintId, error: errorMessage(t, error) }))
    return () => {
      cancelled = true
    }
  }, [complaintId, version, t])

  const current = loaded?.id === complaintId ? loaded : null
  return (
    <>
      <PageHeader
        title={current?.complaint?.reference ?? t('staff.complaints.title')}
        crumbs={[{ label: t('staff.complaints.title'), to: '/staff/complaints' }, { label: current?.complaint?.reference ?? '…' }]}
      />
      {!current ? <FullPageLoader inline /> : current.complaint ? <Desk complaint={current.complaint} onChanged={reload} /> : <Alert tone="error">{current.error}</Alert>}
    </>
  )
}

// After W7: the complaint and replies in the middle on a light grey, the
// reply box under them, the complainant and the W8 history on the right, and
// a bar at the bottom that moves the complaint on.
function Desk({ complaint, onChanged }: { complaint: DeskComplaintDetail; onChanged: () => void }) {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  const thread = useRef<HTMLDivElement>(null)
  const open = complaint.status !== 'RESOLVED' && complaint.status !== 'CLOSED'
  const received = complaint.history[0]?.created_at

  useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight })
  }, [complaint.responses.length])

  return (
    <div className="overflow-hidden rounded-[10px] border border-mist/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-h-[620px] flex-col bg-[#f6f7f9]">
          <div ref={thread} className="max-h-[68vh] flex-1 space-y-7 overflow-y-auto px-5 py-6 sm:px-7">
            {received && (
              <div className="flex justify-center">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#eaecef] px-3.5 py-1.5 text-[13px] text-navy">
                  {formatDate(received, i18n.language)}
                  <ChevronDownIcon className="size-3.5 text-muted" />
                </span>
              </div>
            )}
            <Message side="left" name={complaint.name} when={received} text={complaint.description} />
            {complaint.responses.map((response, index) => (
              <Message
                key={`${response.date}-${index}`}
                side={response.from_complainant ? 'left' : 'right'}
                name={response.from_complainant ? complaint.name : t('staff.complaint.oweru')}
                when={response.date}
                text={response.text}
              />
            ))}
          </div>
          {open ? <Composer complaintId={complaint.id} onSent={onChanged} /> : <p className="border-t border-mist/70 px-7 py-5 text-sm text-muted">{t('staff.complaint.noReplies')}</p>}
        </div>

        <aside className="border-t border-mist/80 lg:border-t-0 lg:border-l">
          <Person complaint={complaint} />
          <History complaint={complaint} />
          {can(user, 'authorization.view') && open && <Assign complaint={complaint} onAssigned={onChanged} />}
        </aside>
      </div>
      <StatusBar complaint={complaint} onChanged={onChanged} />
    </div>
  )
}

function Message({ side, name, when, text }: { side: 'left' | 'right'; name: string; when?: string; text: string }) {
  const { i18n } = useTranslation()
  const right = side === 'right'
  const time = when ? new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(when)) : ''
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex flex-col ${right ? 'items-end' : 'items-start'}`}>
      <p
        className={`max-w-[560px] rounded-[10px] px-4 py-3 text-[15px] leading-relaxed whitespace-pre-line text-navy ${
          right ? 'bg-[#dfe8f5]' : 'border border-mist bg-white'
        }`}
      >
        {text}
      </p>
      {/* W7: avatar, name, time on the left; name, time, avatar on the right. */}
      <p className="mt-3 flex items-center gap-2.5">
        {!right && <span className={`grid size-8 place-items-center rounded-full text-[11px] font-semibold ${right ? 'bg-navy text-gold-light' : 'bg-gold/15 text-[#7a5410]'}`}>
          {initials(name)}
        </span>}
        <span className="text-[15px] font-medium text-navy">{name}</span>
        <span className="text-[13px] text-muted">{time}</span>
        {right && <span className={`grid size-8 place-items-center rounded-full text-[11px] font-semibold ${right ? 'bg-navy text-gold-light' : 'bg-gold/15 text-[#7a5410]'}`}>
          {initials(name)}
        </span>}
      </p>
    </motion.div>
  )
}

// W7's reply area: the text, attached files, and a square send button.
function Composer({ complaintId, onSent }: { complaintId: string; onSent: () => void }) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!text.trim()) return
    const problem = firstFileProblem(files, EVIDENCE_TYPES)
    if (problem) {
      setError(t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name }))
      return
    }
    setSending(true)
    try {
      await staffApi.respond(complaintId, text.trim(), files)
      setText('')
      setFiles([])
      onSent()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setSending(false)
    }
  }

  return (
    <form onSubmit={(event) => void send(event)} className="border-t border-mist/70 bg-gradient-to-b from-[#eef2f8] to-[#f6f7f9] px-5 pt-4 pb-5 sm:px-7">
      <label htmlFor="staff-reply" className="sr-only">
        {t('staff.complaint.reply')}
      </label>
      <textarea
        id="staff-reply"
        rows={3}
        maxLength={10000}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={t('staff.complaint.replyPlaceholder')}
        className="block w-full resize-none bg-transparent text-[15px] leading-relaxed text-navy outline-none placeholder:text-muted/70"
      />
      {files.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`} className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs text-navy ring-1 ring-mist">
              {file.name}
              <button type="button" onClick={() => setFiles(files.filter((_, position) => position !== index))} aria-label={t('forms.removeFile', { name: file.name })}>
                <CloseIcon className="size-3.5 text-muted" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <div className="mt-3 flex items-center justify-between">
        <label className="grid size-9 cursor-pointer place-items-center rounded-full text-muted hover:bg-white hover:text-navy" title={t('staff.complaint.attach')}>
          <span className="sr-only">{t('staff.complaint.attach')}</span>
          <ImageIcon className="size-[18px]" />
          <input
            type="file"
            multiple
            accept="image/jpeg,image/png,application/pdf"
            className="sr-only"
            onChange={(event) => {
              setFiles([...files, ...Array.from(event.target.files ?? [])].slice(0, 5))
              event.target.value = ''
            }}
          />
        </label>
        <motion.button
          type="submit"
          whileTap={{ scale: 0.95 }}
          disabled={sending || !text.trim()}
          aria-label={t('staff.complaint.send')}
          aria-busy={sending || undefined}
          className="grid size-12 place-items-center rounded-[10px] bg-gold text-navy shadow-[0_8px_18px_-8px_rgba(200,145,40,0.9)] transition-colors hover:bg-gold-light disabled:opacity-50"
        >
          {sending ? <span className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" /> : <ArrowRightIcon className="size-5" />}
        </motion.button>
      </div>
    </form>
  )
}

function Section({ title, children, defaultOpen = true }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="border-b border-mist/80 px-5 py-5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">{title}</div>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="grid size-8 shrink-0 place-items-center rounded-[6px] border border-mist text-navy/70 hover:text-navy"
        >
          <ChevronDownIcon className={`size-4 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="pt-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

function Person({ complaint }: { complaint: DeskComplaintDetail }) {
  const { t, i18n } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const rows = [
    { icon: WhatsAppIcon, value: <a href={whatsappTo(complaint.phone, '')} target="_blank" rel="noopener noreferrer" className="hover:text-gold">{formatPhone(complaint.phone)}</a> },
    { icon: DocumentIcon, value: t(`complaint.types.${complaint.category}`) },
    { icon: CalendarIcon, value: t('staff.complaint.dueOn', { date: formatShortDate(complaint.resolution_due_at, i18n.language) }) },
  ]

  return (
    <Section
      title={
        <span className="flex items-center gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-gold/15 text-xs font-semibold text-[#7a5410]">{initials(complaint.name)}</span>
          <span className="truncate text-[15px] font-semibold text-navy">{complaint.name}</span>
        </span>
      }
    >
      <ul className="space-y-3.5">
        {rows.map((row, index) => (
          <li key={index} className="flex items-center gap-3 text-[13px] text-navy">
            <row.icon className="size-4 shrink-0 text-muted" />
            {row.value}
          </li>
        ))}
        <li className="flex items-center gap-3">
          <UsersIcon className="size-4 shrink-0 text-muted" />
          <ComplaintChip status={complaint.status} />
        </li>
      </ul>
      {complaint.evidence.length > 0 && (
        <div className="mt-5">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">{t('staff.complaint.evidence')}</p>
          <ul className="mt-2 space-y-1.5">
            {complaint.evidence.map((evidenceId, index) => (
              <li key={evidenceId}>
                <button
                  type="button"
                  onClick={() => {
                    setError(null)
                    openSigned(() => staffApi.evidence(complaint.id, evidenceId)).catch((failure: unknown) => setError(errorMessage(t, failure)))
                  }}
                  className="flex w-full items-center gap-2.5 rounded-[6px] bg-paper px-3 py-2 text-left text-[13px] text-navy hover:bg-mist/60"
                >
                  <ImageIcon className="size-4 text-muted" />
                  {t('staff.complaint.evidenceItem', { index: index + 1 })}
                </button>
              </li>
            ))}
          </ul>
          {error && <p className="mt-2 text-xs text-danger">{error}</p>}
        </div>
      )}
    </Section>
  )
}

const HISTORY_ICON: Record<ComplaintStatus, { icon: typeof CheckIcon; tone: string; bar: string }> = {
  RECEIVED: { icon: DocumentIcon, tone: 'bg-[#4a6bd1] text-white', bar: 'border-[#4a6bd1]' },
  IN_REVIEW: { icon: SearchIcon, tone: 'bg-gold text-navy', bar: 'border-gold' },
  WAITING_INFORMATION: { icon: AlertIcon, tone: 'bg-[#9a5cc6] text-white', bar: 'border-[#9a5cc6]' },
  RESOLVED: { icon: CheckIcon, tone: 'bg-success text-white', bar: 'border-success' },
  UNDER_FINAL_REVIEW: { icon: ShieldIcon, tone: 'bg-navy text-gold-light', bar: 'border-navy' },
  CLOSED: { icon: LockIcon, tone: 'bg-mist text-navy', bar: 'border-mist' },
}

// After W8: date and time on the left, an icon on a vertical line, and the
// status with its recorded reason in a grey box.
function History({ complaint }: { complaint: DeskComplaintDetail }) {
  const { t, i18n } = useTranslation()
  const entries = [...complaint.history].sort((a, b) => b.version - a.version)
  const stamp = (value: string) =>
    new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))

  return (
    <Section title={<h2 className="text-[15px] font-medium text-navy">{t('staff.complaint.history')}</h2>}>
      <ol className="relative">
        <span aria-hidden="true" className="absolute top-2 bottom-2 left-[78px] w-px bg-mist" />
        {entries.map((entry) => {
          const look = HISTORY_ICON[entry.status]
          return (
            <li key={entry.version} className="relative grid grid-cols-[66px_24px_minmax(0,1fr)] gap-x-3 pb-5 last:pb-0">
              <span className="pt-1 text-[10px] leading-tight text-muted">{stamp(entry.created_at)}</span>
              <span className={`relative z-10 grid size-6 place-items-center rounded-full ${look.tone}`}>
                <look.icon className="size-3.5" />
              </span>
              <div className="min-w-0">
                <p className="pt-0.5 text-[13px] font-semibold text-navy">{t(`staff.statuses.${entry.status}`)}</p>
                <p className={`mt-1.5 border-l-[3px] bg-[#f1f2f4] px-2.5 py-2 text-xs leading-relaxed text-navy/85 ${look.bar}`}>{entry.reason}</p>
              </div>
            </li>
          )
        })}
      </ol>
    </Section>
  )
}

// Management hands a complaint to a handler by email (CMP-04).
function Assign({ complaint, onAssigned }: { complaint: DeskComplaintDetail; onAssigned: () => void }) {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function assign(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!email.trim()) return
    setBusy(true)
    try {
      const [account] = await managementApi.findAccount(email.trim())
      if (!account) {
        setError(t('staff.complaint.noAccount'))
        return
      }
      await staffApi.assign(complaint.id, account.id, complaint.version)
      setEmail('')
      onAssigned()
    } catch (failure) {
      setError(failure instanceof ApiError && failure.status === 409 ? t('staff.complaint.changed') : errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title={<h2 className="text-[15px] font-medium text-navy">{t('staff.complaint.assignTitle')}</h2>} defaultOpen={false}>
      <form onSubmit={(event) => void assign(event)} className="space-y-3">
        <label className="block text-xs text-muted" htmlFor="assign-email">
          {t('staff.complaint.assignLabel')}
        </label>
        <input
          id="assign-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="jina@oweru.com"
          className="h-10 w-full rounded-[6px] border border-mist px-3 text-[13px] text-navy outline-none focus:border-gold"
        />
        {error && <p className="text-xs text-danger">{error}</p>}
        <button type="submit" disabled={busy} className="h-10 w-full rounded-[6px] bg-navy text-[13px] font-semibold text-white hover:bg-navy-soft disabled:opacity-60">
          {busy ? t('listing.sending') : t('staff.complaint.assign')}
        </button>
      </form>
    </Section>
  )
}

// W7's bottom bar: the current state on the left of an outlined menu button
// that moves the complaint to its next status.
function StatusBar({ complaint, onChanged }: { complaint: DeskComplaintDetail; onChanged: () => void }) {
  const { t } = useTranslation()
  const [menu, setMenu] = useState(false)
  const [target, setTarget] = useState<ComplaintStatus | null>(null)
  const next = NEXT_STATUSES[complaint.status]

  return (
    <div className="flex flex-wrap items-center justify-end gap-4 border-t border-mist/80 bg-white px-5 py-4 sm:px-7">
      <span className="text-[15px] text-muted">{t('staff.complaint.isNow', { status: t(`staff.statuses.${complaint.status}`).toLowerCase() })}</span>
      {next.length > 0 && (
        <div className="relative">
          <button
            type="button"
            onClick={() => setMenu(!menu)}
            aria-expanded={menu}
            className="inline-flex h-11 items-center gap-2 rounded-[8px] border border-gold px-4 text-[15px] font-medium text-[#8a5f12] hover:bg-gold/10"
          >
            {t('staff.complaint.moveTo', { status: t(`staff.statuses.${next[0]}`) })}
            <ChevronDownIcon className="size-4" />
          </button>
          <AnimatePresence>
            {menu && (
              <motion.ul
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                className="absolute right-0 bottom-full z-20 mb-2 w-64 overflow-hidden rounded-[8px] border border-mist bg-white py-1 shadow-lift"
              >
                {next.map((status) => (
                  <li key={status}>
                    <button
                      type="button"
                      onClick={() => {
                        setMenu(false)
                        setTarget(status)
                      }}
                      className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm text-navy hover:bg-paper"
                    >
                      {t(`staff.statuses.${status}`)}
                      <ComplaintChip status={status} />
                    </button>
                  </li>
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>
      )}
      <AnimatePresence>{target && <MoveDialog complaint={complaint} target={target} onClose={() => setTarget(null)} onMoved={onChanged} />}</AnimatePresence>
    </div>
  )
}

// CMP-07: every move needs a reason; resolving (and closing a final review)
// also needs the outcome the complainant will read.
function MoveDialog({ complaint, target, onClose, onMoved }: { complaint: DeskComplaintDetail; target: ComplaintStatus; onClose: () => void; onMoved: () => void }) {
  const { t } = useTranslation()
  const needsOutcome = target === 'RESOLVED' || complaint.status === 'UNDER_FINAL_REVIEW'
  const [reason, setReason] = useState('')
  const [outcome, setOutcome] = useState(complaint.outcome)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function move(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!reason.trim() || (needsOutcome && !outcome.trim())) {
      setError(t('validation.required'))
      return
    }
    setBusy(true)
    try {
      await staffApi.transition(complaint.id, { status: target, version: complaint.version, reason: reason.trim(), outcome: needsOutcome ? outcome.trim() : '' })
      onClose()
      onMoved()
    } catch (failure) {
      setBusy(false)
      setError(failure instanceof ApiError && failure.status === 409 ? t('staff.complaint.changed') : errorMessage(t, failure))
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4" role="dialog" aria-modal="true" aria-labelledby="move-title">
      <motion.div className="absolute inset-0 bg-navy/50 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.form
        onSubmit={(event) => void move(event)}
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 16, scale: 0.98 }}
        className="relative w-full max-w-lg rounded-[12px] bg-white p-6 shadow-lift"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="move-title" className="text-lg font-semibold text-navy">
              {t('staff.complaint.moveTitle', { status: t(`staff.statuses.${target}`) })}
            </h2>
            <p className="mt-1 text-sm text-muted">{t('staff.complaint.moveBody')}</p>
          </div>
          <button type="button" onClick={onClose} aria-label={t('complaint.close')} className="grid size-9 place-items-center rounded-[8px] border border-mist text-muted hover:text-navy">
            <CloseIcon className="size-4" />
          </button>
        </div>
        <div className="mt-5 space-y-4">
          {needsOutcome && (
            <div>
              <label htmlFor="move-outcome" className="mb-1.5 block text-sm font-medium text-navy">
                {t('complaint.outcome')}
              </label>
              <textarea
                id="move-outcome"
                rows={3}
                value={outcome}
                onChange={(event) => setOutcome(event.target.value)}
                className="block w-full rounded-[8px] border border-mist px-3 py-2.5 text-sm text-navy outline-none focus:border-gold"
              />
            </div>
          )}
          <div>
            <label htmlFor="move-reason" className="mb-1.5 block text-sm font-medium text-navy">
              {needsOutcome ? t('complaint.reasons') : t('staff.complaint.reason')}
            </label>
            <textarea
              id="move-reason"
              rows={3}
              autoFocus
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className="block w-full rounded-[8px] border border-mist px-3 py-2.5 text-sm text-navy outline-none focus:border-gold"
            />
          </div>
          {error && <Alert tone="error">{error}</Alert>}
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="h-11 rounded-[8px] border border-mist px-5 text-sm font-medium text-navy hover:border-navy/30">
            {t('staff.cancel')}
          </button>
          <button type="submit" disabled={busy} className="h-11 rounded-[8px] bg-gold px-5 text-sm font-semibold text-navy hover:bg-gold-light disabled:opacity-60">
            {busy ? t('listing.sending') : t('staff.complaint.confirmMove')}
          </button>
        </div>
      </motion.form>
    </div>
  )
}
