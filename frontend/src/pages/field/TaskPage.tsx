import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, ArrowLeftIcon, CheckIcon, CopyIcon, DocumentIcon, MapPinIcon, TickIcon, TrashIcon, UploadIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatShortDate } from '../../lib/format'
import { openSigned } from '../../lib/openSigned'
import { captureApi, FINDING_FIELDS, tasksApi, type Answer, type Capture, type TaskDetail } from '../../lib/tasksApi'
import { SidePanel } from '../deals/ui'

// LOC-03, LOC-04, PRO-03 to PRO-05, FUL-03, FUL-06: one task, one screen.
// After R6 (the task number large with its status, tabs, a progress bar and
// checklist rows), R7 (each question as Yes or No) and R10 (the document as a
// dashed drop area, then a file row with its size and remove).

type Tab = 'work' | 'property' | 'history'

export function TaskPage() {
  const { taskId = '' } = useParams()
  const { t } = useTranslation()
  const [task, setTask] = useState<TaskDetail | null>(null)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  useDocumentTitle(t('field.task.title'))

  useEffect(() => {
    let live = true
    tasksApi
      .get(taskId)
      .then((row) => live && setTask(row))
      .catch((failure) => live && setError(errorMessage(t, failure)))
    return () => {
      live = false
    }
  }, [taskId, version, t])

  if (error) return <Alert tone="error">{error}</Alert>
  if (!task || task.id !== taskId) return <FullPageLoader inline />
  return <Task task={task} onChange={() => setVersion((value) => value + 1)} />
}

function Task({ task, onChange }: { task: TaskDetail; onChange: () => void }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('work')
  const [relationship, setRelationship] = useState(false)
  const done = task.status === 'SUBMITTED'
  const code = task.id.slice(0, 6).toUpperCase()
  const title = task.kind === 'PROFESSIONAL' ? t(`field.types.${task.professional_type}`) : t(`field.kinds.${task.kind}`)

  return (
    <div className="mx-auto max-w-[680px] pb-12">
      <div className="flex items-center justify-between">
        <button type="button" onClick={() => navigate('/tasks')} aria-label={t('field.task.back')} className="grid size-10 place-items-center rounded-full border border-mist bg-white text-navy">
          <ArrowLeftIcon className="size-5" />
        </button>
        <p className="text-[15px] font-semibold text-navy">{title}</p>
        <span className="size-10" />
      </div>

      {/* R6: status, the number large, the property under it. */}
      <div className="mt-6">
        <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium ${done ? 'bg-success-soft text-success' : 'bg-[#fdf3d8] text-[#7a5410]'}`}>
          <span className="size-1.5 rounded-full bg-current" />
          {t(`field.statuses.${task.status}`)}
        </span>
        <div className="mt-3 flex items-center gap-3">
          <h1 className="font-display text-[44px] leading-none font-bold tracking-tight text-navy">T-{code}</h1>
          <button type="button" aria-label={t('field.task.copy')} onClick={() => void navigator.clipboard?.writeText(task.id)} className="text-muted hover:text-navy">
            <CopyIcon className="size-5" />
          </button>
        </div>
        <p className="mt-2 text-[14px] text-muted">
          {task.property_id} · {task.area}
          {task.due_at && ` · ${t('field.task.due', { date: formatShortDate(task.due_at, i18n.language) })}`}
        </p>
      </div>

      <div role="tablist" className="mt-6 flex gap-2">
        {(['work', 'property', 'history'] as Tab[]).map((value) => (
          <button key={value} type="button" role="tab" aria-selected={tab === value} onClick={() => setTab(value)} className={`relative rounded-full px-5 py-2.5 text-[14px] font-medium ${tab === value ? 'text-white' : 'text-navy-soft hover:bg-white'}`}>
            {tab === value && <motion.span layoutId="task-tab" className="absolute inset-0 rounded-full bg-navy" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
            <span className="relative">{t(`field.task.tabs.${value}`, { count: task.submissions.length })}</span>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.2 }} className="mt-5">
          {tab === 'work' && <Work task={task} onChange={onChange} />}
          {tab === 'property' && <PropertyTab task={task} />}
          {tab === 'history' && <History task={task} />}
        </motion.div>
      </AnimatePresence>

      {!done && task.kind !== 'REGISTRY' && (
        <button type="button" onClick={() => setRelationship(true)} className="mt-8 text-[13px] text-muted underline underline-offset-4 hover:text-navy">
          {t('field.task.relationship')}
        </button>
      )}
      <SidePanel open={relationship} title={t('field.task.relationshipTitle')} onClose={() => setRelationship(false)}>
        <Relationship
          task={task}
          onDone={() => {
            setRelationship(false)
            navigate('/tasks')
          }}
        />
      </SidePanel>
    </div>
  )
}

function Work({ task, onChange }: { task: TaskDetail; onChange: () => void }) {
  const { t } = useTranslation()
  if (task.status === 'SUBMITTED') return <Submitted task={task} />
  if (task.status === 'TIMED_OUT') return <Alert tone="error">{t('field.task.timedOut')}</Alert>
  if (task.kind === 'PROFESSIONAL' && task.status === 'ASSIGNED') return <AcceptCard task={task} onChange={onChange} />
  if (task.kind === 'LOCAL_OFFICE') return <LocalOffice task={task} onChange={onChange} />
  if (task.kind === 'SITE_CAPTURE') return <SiteCapture task={task} onChange={onChange} />
  return <Findings task={task} onChange={onChange} />
}

// R7: the five questions as large Yes / No choices with a note under each.
function LocalOffice({ task, onChange }: { task: TaskDetail; onChange: () => void }) {
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const questions = task.questions ?? []
  const [answers, setAnswers] = useState<Record<string, { answer: Answer | ''; comment: string }>>(() => Object.fromEntries(questions.map((_, index) => [String(index + 1), { answer: '', comment: '' }])))
  const [letter, setLetter] = useState<File | null>(null)
  const [stamped, setStamped] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const answered = Object.entries(answers).filter(([key, row]) => row.answer && (key === '1' || row.comment.trim())).length
  const ready = answered === questions.length && letter !== null && stamped

  async function submit() {
    setBusy(true)
    setError('')
    try {
      const findings = Object.fromEntries(Object.entries(answers).map(([key, row]) => [key, { answer: row.answer, comment: row.comment.trim() }]))
      await tasksApi.submit(task.id, { findings, report: letter, signed_and_stamped: true })
      onChange()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <Progress done={answered} total={questions.length} label={t('field.task.questionsTitle')} />
      <ol className="space-y-3">
        {questions.map((question, index) => {
          const key = String(index + 1)
          const row = answers[key]
          return (
            <motion.li key={key} initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }} className="rounded-2xl border border-mist bg-white p-4">
              <p className="flex gap-3 text-[15px] font-medium text-navy">
                <span className={`grid size-7 shrink-0 place-items-center rounded-full text-[13px] font-bold ${row.answer ? 'bg-gold text-navy' : 'bg-paper text-muted'}`}>{index + 1}</span>
                {t(`field.task.questions.${index}`, { owner: task.owner_name, defaultValue: question })}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2 pl-10">
                {(['YES', 'NO'] as Answer[]).map((value) => (
                  <motion.button
                    key={value}
                    type="button"
                    whileTap={{ scale: 0.96 }}
                    aria-pressed={row.answer === value}
                    onClick={() => setAnswers((current) => ({ ...current, [key]: { ...current[key], answer: value } }))}
                    className={`h-12 rounded-xl border-2 text-[15px] font-bold ${row.answer === value ? (value === 'YES' ? 'border-success bg-success-soft text-success' : 'border-danger bg-danger-soft text-danger') : 'border-mist text-navy-soft'}`}
                  >
                    {t(`field.task.${value === 'YES' ? 'yes' : 'no'}`)}
                  </motion.button>
                ))}
              </div>
              {index > 0 && (
                <textarea
                  value={row.comment}
                  onChange={(event) => setAnswers((current) => ({ ...current, [key]: { ...current[key], comment: event.target.value } }))}
                  rows={2}
                  placeholder={t('field.task.commentRequired')}
                  className="mt-2 ml-10 w-[calc(100%-2.5rem)] rounded-xl border border-mist px-3 py-2 text-[14px] outline-none focus:border-gold"
                />
              )}
            </motion.li>
          )
        })}
      </ol>
      <Upload label={t('field.task.letterTitle')} note={t('field.task.letterNote')} file={letter} onFile={setLetter} onError={setError} />
      <label className="flex items-start gap-3 rounded-2xl bg-paper p-4 text-[14px] text-navy">
        <input type="checkbox" checked={stamped} onChange={(event) => setStamped(event.target.checked)} className="mt-0.5 size-5 accent-[#c89128]" />
        {t('field.task.stampedConfirm')}
      </label>
      <SubmitBar ready={ready} busy={busy} error={error} onSubmit={() => void submit()} note={t('field.task.lockNote')} />
    </div>
  )
}

// Professionals and the Land Registry search: written findings and a report.
function Findings({ task, onChange }: { task: TaskDetail; onChange: () => void }) {
  const { t } = useTranslation()
  const fields = FINDING_FIELDS[task.kind === 'REGISTRY' ? 'REGISTRY' : (task.professional_type as keyof typeof FINDING_FIELDS)] ?? []
  const surveyor = task.professional_type === 'SURVEYOR'
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(fields.map((field) => [field, ''])))
  const [report, setReport] = useState<File | null>(null)
  const [capture, setCapture] = useState<Capture | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!surveyor) return
    captureApi.list(task.property_id).then((page) => setCapture(page.results.find((row) => row.verification_task_id === task.id && row.status === 'SUBMITTED') ?? null), () => undefined)
  }, [surveyor, task.property_id, task.id])

  const filled = fields.filter((field) => values[field]?.trim()).length
  const ready = filled === fields.length && report !== null && (!surveyor || capture !== null)

  async function submit() {
    setBusy(true)
    setError('')
    try {
      await tasksApi.submit(task.id, { findings: Object.fromEntries(fields.map((field) => [field, values[field].trim()])), report, capture_id: capture?.capture_id })
      onChange()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <Progress done={filled + (report ? 1 : 0)} total={fields.length + 1} label={t('field.task.findingsTitle')} />
      {surveyor && <CaptureCard task={task} capture={capture} />}
      {fields.map((field, index) => (
        <motion.label key={field} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }} className="block rounded-2xl border border-mist bg-white p-4">
          <span className="flex items-center gap-2 text-[14px] font-semibold text-navy">
            <span className={`grid size-6 place-items-center rounded-full ${values[field]?.trim() ? 'bg-success text-white' : 'bg-paper text-muted'}`}>{values[field]?.trim() ? <CheckIcon className="size-3.5" /> : <span className="size-1.5 rounded-full bg-current" />}</span>
            {t(`field.findings.${field}`)}
          </span>
          <textarea value={values[field]} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))} rows={3} className="mt-2 w-full rounded-xl border border-mist px-3 py-2 text-[14px] outline-none focus:border-gold" />
        </motion.label>
      ))}
      <Upload label={t('field.task.reportTitle')} note={t('field.task.reportNote')} file={report} onFile={setReport} onError={setError} />
      <SubmitBar ready={ready} busy={busy} error={error} onSubmit={() => void submit()} note={t('field.task.lockNote')} />
    </div>
  )
}

function SiteCapture({ task, onChange }: { task: TaskDetail; onChange: () => void }) {
  const { t } = useTranslation()
  const [capture, setCapture] = useState<Capture | null | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    captureApi.list(task.property_id).then(
      (page) => setCapture(page.results.find((row) => row.verification_task_id === task.id && row.status === 'SUBMITTED') ?? null),
      () => setCapture(null),
    )
  }, [task.property_id, task.id])

  async function submit() {
    if (!capture) return
    setBusy(true)
    setError('')
    try {
      await tasksApi.submit(task.id, { findings: {}, capture_id: capture.capture_id })
      onChange()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <CaptureCard task={task} capture={capture ?? null} />
      <SubmitBar ready={Boolean(capture)} busy={busy} error={error} onSubmit={() => void submit()} note={t('field.task.captureSubmitNote')} />
    </div>
  )
}

function CaptureCard({ task, capture }: { task: TaskDetail; capture: Capture | null }) {
  const { t } = useTranslation()
  return (
    <div className="overflow-hidden rounded-2xl bg-navy text-white">
      <div className="flex items-center gap-4 p-5">
        <span className={`grid size-12 place-items-center rounded-full ${capture ? 'bg-success text-white' : 'bg-gold text-navy'}`}>{capture ? <CheckIcon className="size-6" /> : <MapPinIcon className="size-6" />}</span>
        <div className="min-w-0 flex-1">
          <p className="text-[16px] font-semibold">{capture ? t('field.task.captureDone', { area: Math.round(Number(capture.measured_area_sqm ?? 0)) }) : t('field.task.captureTitle')}</p>
          <p className="text-[13px] text-white/70">{capture ? capture.capture_id : t('field.task.captureNote')}</p>
        </div>
      </div>
      {!capture && (
        <Link to={`/capture/${encodeURIComponent(task.property_id)}?task=${task.id}`} className="flex h-14 items-center justify-center gap-2 bg-gold text-[15px] font-bold text-navy">
          <MapPinIcon className="size-5" />
          {t('field.task.captureStart')}
        </Link>
      )}
    </div>
  )
}

// R8 on the task page: a new professional job waits for Accept or Decline.
function AcceptCard({ task, onChange }: { task: TaskDetail; onChange: () => void }) {
  const { t } = useTranslation()
  const [declining, setDeclining] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function decide(decision: 'ACCEPT' | 'DECLINE') {
    setBusy(true)
    setError('')
    try {
      await tasksApi.decide(task.id, decision, reason.trim())
      onChange()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="rounded-3xl bg-white p-5 shadow-card">
      <p className="text-[13px] font-semibold tracking-[0.08em] text-[#9a6c12] uppercase">{t('field.task.newJob')}</p>
      <p className="mt-2 text-[15px] leading-relaxed text-navy">{t('field.task.newJobBody', { type: t(`field.types.${task.professional_type}`), area: task.area })}</p>
      {declining && <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} placeholder={t('field.tasks.reason')} className="mt-4 w-full rounded-xl border border-mist px-3 py-2 text-[14px] outline-none focus:border-gold" />}
      {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button type="button" disabled={busy} onClick={() => (declining ? void decide('DECLINE') : setDeclining(true))} className="h-12 rounded-full border border-mist text-[14px] font-semibold text-navy-soft">
          {declining ? t('field.tasks.declineConfirm') : t('field.tasks.decline')}
        </button>
        <button type="button" disabled={busy} onClick={() => void decide('ACCEPT')} className="h-12 rounded-full bg-gold text-[14px] font-bold text-navy">
          {t('field.tasks.accept')}
        </button>
      </div>
    </div>
  )
}

function Submitted({ task }: { task: TaskDetail }) {
  const { t, i18n } = useTranslation()
  const latest = task.submissions.at(-1)
  return (
    <div className="rounded-3xl border border-success/30 bg-success-soft p-6 text-center">
      <motion.span initial={{ scale: 0, rotate: -30 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', stiffness: 300, damping: 16 }} className="mx-auto grid size-16 place-items-center rounded-full bg-success text-white">
        <TickIcon className="size-8" />
      </motion.span>
      <p className="mt-4 text-[18px] font-semibold text-success">{t('field.task.submittedTitle')}</p>
      <p className="mt-1 text-[14px] text-navy-soft">{latest ? t('field.task.submittedBody', { version: latest.version, date: formatShortDate(latest.created_at, i18n.language) }) : ''}</p>
      <p className="mt-3 text-[13px] text-muted">{t('field.task.lockedNote')}</p>
    </div>
  )
}

function PropertyTab({ task }: { task: TaskDetail }) {
  const { t } = useTranslation()
  const rows: [string, ReactNode][] = [
    [t('field.task.rows.property'), task.property_id],
    [t('field.task.rows.area'), task.area],
    [t('field.task.rows.locality'), task.locality],
    [t('field.task.rows.owner'), task.owner_name],
  ]
  return (
    <dl className="rounded-2xl border border-mist bg-white px-5">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-4 border-b border-mist/70 py-3.5 text-[14px] last:border-b-0">
          <dt className="text-muted">{label}</dt>
          <dd className="text-right font-medium text-navy">{value || '-'}</dd>
        </div>
      ))}
      <p className="border-t border-mist py-3 text-[12px] text-muted">{t('field.task.mapNote')}</p>
    </dl>
  )
}

function History({ task }: { task: TaskDetail }) {
  const { t, i18n } = useTranslation()
  if (!task.submissions.length) return <p className="rounded-2xl border border-dashed border-mist bg-white px-6 py-10 text-center text-[14px] text-muted">{t('field.task.noHistory')}</p>
  return (
    <ol className="space-y-3">
      {[...task.submissions].reverse().map((row) => (
        <li key={row.id} className="rounded-2xl border border-mist bg-white p-4">
          <div className="flex items-center justify-between">
            <p className="text-[14px] font-semibold text-navy">{t('field.task.version', { version: row.version })}</p>
            <p className="text-[12px] text-muted">{formatShortDate(row.created_at, i18n.language)}</p>
          </div>
          <p className="mt-1 text-[13px] text-muted">
            {row.author_name}
            {row.registration_number && ` · ${row.registration_number}`}
          </p>
          <button type="button" onClick={() => void openSigned(() => tasksApi.report(row.id)).catch(() => undefined)} className="mt-3 inline-flex items-center gap-2 text-[13px] font-medium text-[#9a6c12]">
            <DocumentIcon className="size-4" />
            {t('field.task.openReport')}
          </button>
        </li>
      ))}
    </ol>
  )
}

function Relationship({ task, onDone }: { task: TaskDetail; onDone: () => void }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function declare() {
    setBusy(true)
    try {
      await tasksApi.declareRelationship(task.id, reason.trim())
      onDone()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      <p className="text-[14px] leading-relaxed text-navy-soft">{t('field.task.relationshipBody')}</p>
      <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={4} className="mt-4 w-full rounded-xl border border-mist px-3 py-2.5 text-[14px] outline-none focus:border-gold" />
      {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
      <button type="button" disabled={busy || !reason.trim()} onClick={() => void declare()} className="mt-4 h-12 w-full rounded-full bg-navy text-[14px] font-semibold text-white disabled:opacity-50">
        {t('field.task.relationshipConfirm')}
      </button>
    </div>
  )
}

// R6's progress: "3 of 5" with a striped bar.
function Progress({ done, total, label }: { done: number; total: number; label: string }) {
  const { t } = useTranslation()
  const share = total ? Math.round((done / total) * 100) : 0
  return (
    <div className="rounded-2xl bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between">
        <p className="text-[18px] font-semibold text-navy">{label}</p>
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[12px] font-medium ${done === total ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'}`}>
          <span className="size-1.5 rounded-full bg-current" />
          {done === total ? t('field.task.complete') : t('field.task.left', { count: total - done })}
        </span>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <span className="text-[13px] text-muted tabular-nums">{t('field.task.of', { done, total })}</span>
        <div className="relative h-5 flex-1 overflow-hidden rounded-md bg-[repeating-linear-gradient(90deg,#e5e7eb_0_3px,transparent_3px_6px)]">
          <motion.div className="absolute inset-y-0 left-0 bg-[repeating-linear-gradient(90deg,#c89128_0_3px,transparent_3px_6px)]" initial={false} animate={{ width: `${share}%` }} transition={{ type: 'spring', stiffness: 120, damping: 20 }} />
        </div>
        <span className="text-[13px] text-muted tabular-nums">{share}%</span>
      </div>
    </div>
  )
}

// R10: a dashed drop area, then the chosen file as a row with its size and remove.
function Upload({ label, note, file, onFile, onError }: { label: string; note: string; file: File | null; onFile: (file: File | null) => void; onError: (message: string) => void }) {
  const { t } = useTranslation()
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const size = useMemo(() => (file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : ''), [file])
  function take(files: FileList | null) {
    const picked = files?.[0]
    if (!picked) return
    const problem = firstFileProblem([picked], EVIDENCE_TYPES)
    if (problem) {
      onError(t(problem.kind === 'size' ? 'deals.fileTooBig' : 'deals.fileType', { name: problem.name }))
      return
    }
    onError('')
    onFile(picked)
  }
  return (
    <div className="rounded-2xl border border-mist bg-white p-4">
      <p className="text-[16px] font-semibold text-navy">{label}</p>
      <p className="mt-0.5 text-[13px] text-muted">{note}</p>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setOver(false)
          take(event.dataTransfer.files)
        }}
        className={`mt-3 flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-7 transition-colors ${over ? 'border-gold bg-[#fdf7ec]' : 'border-mist bg-paper'}`}
      >
        <motion.span animate={over ? { y: -4 } : { y: 0 }} className="grid size-11 place-items-center rounded-full bg-white text-navy shadow-sm">
          <UploadIcon className="size-5" />
        </motion.span>
        <span className="text-[14px] font-medium text-navy">{t('field.task.dropOrPhoto')}</span>
        <span className="text-[12px] text-muted">{t('field.task.fileLimit')}</span>
      </button>
      <input ref={input} type="file" accept="application/pdf,image/jpeg,image/png" capture="environment" className="sr-only" tabIndex={-1} onChange={(event) => take(event.target.files)} />
      <AnimatePresence>
        {file && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }} className="mt-3 flex items-center gap-3 rounded-xl border border-mist px-3 py-2.5">
            <span className="grid size-10 place-items-center rounded-lg bg-danger-soft text-[10px] font-bold text-danger">{file.type === 'application/pdf' ? 'PDF' : 'IMG'}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[14px] font-medium text-navy">{file.name}</span>
              <span className="block text-[12px] text-muted">{size}</span>
            </span>
            <button type="button" onClick={() => onFile(null)} aria-label={t('field.task.remove')} className="grid size-9 place-items-center rounded-full text-muted hover:bg-paper hover:text-danger">
              <TrashIcon className="size-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function SubmitBar({ ready, busy, error, onSubmit, note }: { ready: boolean; busy: boolean; error: string; onSubmit: () => void; note: string }) {
  const { t } = useTranslation()
  return (
    <div className="sticky bottom-0 -mx-4 bg-paper/95 px-4 pt-3 pb-4 backdrop-blur sm:mx-0 sm:rounded-2xl sm:px-0">
      {error && (
        <p role="alert" className="mb-2 flex items-center gap-2 text-[13px] text-danger">
          <AlertIcon className="size-4" />
          {error}
        </p>
      )}
      <motion.button type="button" whileTap={{ scale: 0.98 }} disabled={!ready || busy} onClick={onSubmit} className="h-14 w-full rounded-2xl bg-gold text-[16px] font-bold text-navy shadow-[0_10px_24px_-12px_rgba(200,145,40,0.9)] disabled:bg-mist disabled:text-muted disabled:shadow-none">
        {busy ? t('field.task.submitting') : t('field.task.submit')}
      </motion.button>
      <p className="mt-2 text-center text-[12px] text-muted">{note}</p>
    </div>
  )
}
