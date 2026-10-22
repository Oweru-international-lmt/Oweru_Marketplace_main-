import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { CheckIcon, ClockIcon, DocumentIcon, UsersIcon } from '../../../components/icons'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'
import { openSigned } from '../../../lib/openSigned'
import type { FullCheck } from '../../../lib/servicesApi'
import { tasksApi, type Professional, type ProfessionalType, type Task } from '../../../lib/tasksApi'
import { SidePanel } from '../../deals/ui'
import { Card } from './ui'

// FUL-03 to FUL-06, PRO-02, VER-04: the responsible verifier starts the
// tasks, assigns professionals from those eligible, reads each submission and
// asks for a correction. Shown inside the full check desk (W9).

const TYPES: ProfessionalType[] = ['SURVEYOR', 'AFISA_MIPANGO_MIJI', 'PLANNER']

export function JobTasks({ job, canAct }: { job: FullCheck; canAct: boolean }) {
  const { t, i18n } = useTranslation()
  const [tasks, setTasks] = useState<Task[] | null>(null)
  const [version, setVersion] = useState(0)
  const [assigning, setAssigning] = useState<Task | null>(null)
  const [correcting, setCorrecting] = useState<Task | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let live = true
    tasksApi.list(job.id).then((page) => live && setTasks(page.results), () => live && setTasks([]))
    return () => {
      live = false
    }
  }, [job.id, version])

  const reload = () => setVersion((value) => value + 1)
  if (!tasks) return null

  return (
    <Card className="px-6 pt-5 pb-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-navy">{t('field.desk.title')}</h2>
        <span className="text-[12px] text-muted">{t('field.desk.count', { done: tasks.filter((row) => row.status === 'SUBMITTED').length, total: tasks.length })}</span>
      </div>
      {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
      {tasks.length === 0 ? (
        canAct && job.status === 'IN_PROGRESS' ? <StartForm job={job} onStarted={reload} onError={setError} /> : <p className="mt-4 text-[13px] text-muted">{t('field.desk.notStarted')}</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {tasks.map((task, index) => (
            <motion.li key={task.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }} className="flex flex-wrap items-center gap-3 rounded-lg border border-mist/70 px-3 py-2.5">
              <span className={`grid size-8 place-items-center rounded-full ${task.status === 'SUBMITTED' ? 'bg-success-soft text-success' : 'bg-paper text-muted'}`}>{task.status === 'SUBMITTED' ? <CheckIcon className="size-4" /> : <ClockIcon className="size-4" />}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-medium text-navy">{task.kind === 'PROFESSIONAL' ? t(`field.types.${task.professional_type}`) : t(`field.kinds.${task.kind}`)}</span>
                <span className="block text-[12px] text-muted">
                  {t(`field.statuses.${task.status}`)}
                  {task.assignee_name && ` · ${task.assignee_name}`}
                  {task.due_at && ` · ${formatShortDate(task.due_at, i18n.language)}`}
                </span>
              </span>
              {canAct && task.kind === 'PROFESSIONAL' && (task.status === 'UNASSIGNED' || task.status === 'TIMED_OUT') && (
                <button type="button" onClick={() => setAssigning(task)} className="rounded-md bg-gold px-3 py-1.5 text-[12px] font-semibold text-navy">
                  {t('field.desk.assign')}
                </button>
              )}
              {task.kind === 'REGISTRY' && task.status !== 'SUBMITTED' && canAct && (
                <Link to={`/tasks/${task.id}`} className="rounded-md bg-gold px-3 py-1.5 text-[12px] font-semibold text-navy">
                  {t('field.desk.recordSearch')}
                </Link>
              )}
              {task.status === 'SUBMITTED' && (
                <>
                  <ReportLink taskId={task.id} />
                  {canAct && (
                    <button type="button" onClick={() => setCorrecting(task)} className="rounded-md border border-mist px-3 py-1.5 text-[12px] font-medium text-navy">
                      {t('field.desk.correction')}
                    </button>
                  )}
                </>
              )}
            </motion.li>
          ))}
        </ul>
      )}

      <SidePanel open={assigning !== null} title={t('field.desk.assignTitle')} onClose={() => setAssigning(null)}>
        {assigning && (
          <AssignForm
            job={job}
            task={assigning}
            onDone={() => {
              setAssigning(null)
              reload()
            }}
          />
        )}
      </SidePanel>
      <SidePanel open={correcting !== null} title={t('field.desk.correctionTitle')} onClose={() => setCorrecting(null)}>
        {correcting && (
          <CorrectionForm
            task={correcting}
            onDone={() => {
              setCorrecting(null)
              reload()
            }}
          />
        )}
      </SidePanel>
    </Card>
  )
}

function ReportLink({ taskId }: { taskId: string }) {
  const { t } = useTranslation()
  async function open() {
    const detail = await tasksApi.get(taskId)
    const latest = detail.submissions.at(-1)
    if (latest) await openSigned(() => tasksApi.report(latest.id))
  }
  return (
    <button type="button" onClick={() => void open().catch(() => undefined)} className="inline-flex items-center gap-1 text-[12px] font-medium text-[#9a6c12]">
      <DocumentIcon className="size-3.5" />
      {t('field.desk.openReport')}
    </button>
  )
}

function StartForm({ job, onStarted, onError }: { job: FullCheck; onStarted: () => void; onError: (message: string) => void }) {
  const { t } = useTranslation()
  const [types, setTypes] = useState<ProfessionalType[]>([])
  const [surveyorCapture, setSurveyorCapture] = useState(false)
  const [busy, setBusy] = useState(false)
  async function start() {
    setBusy(true)
    onError('')
    try {
      await tasksApi.startTasks(job.id, types, surveyorCapture && types.includes('SURVEYOR'))
      onStarted()
    } catch (failure) {
      onError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="mt-4 space-y-3">
      <p className="text-[13px] text-muted">{t('field.desk.startNote')}</p>
      <div className="flex flex-wrap gap-2">
        {TYPES.map((type) => {
          const on = types.includes(type)
          return (
            <button key={type} type="button" aria-pressed={on} onClick={() => setTypes((current) => (on ? current.filter((row) => row !== type) : [...current, type]))} className={`rounded-full border px-3 py-1.5 text-[12px] font-medium ${on ? 'border-gold bg-gold/15 text-[#7a5410]' : 'border-mist text-navy-soft'}`}>
              {t(`field.types.${type}`)}
            </button>
          )
        })}
      </div>
      <AnimatePresence>
        {types.includes('SURVEYOR') && (
          <motion.label initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="flex items-center gap-2 overflow-hidden text-[13px] text-navy">
            <input type="checkbox" checked={surveyorCapture} onChange={(event) => setSurveyorCapture(event.target.checked)} className="size-4 accent-[#c89128]" />
            {t('field.desk.surveyorCapture')}
          </motion.label>
        )}
      </AnimatePresence>
      <button type="button" disabled={busy} onClick={() => void start()} className="h-10 w-full rounded-[6px] bg-gold text-[13px] font-semibold text-navy disabled:opacity-60">
        {t('field.desk.start')}
      </button>
    </div>
  )
}

function AssignForm({ job, task, onDone }: { job: FullCheck; task: Task; onDone: () => void }) {
  const { t } = useTranslation()
  const [people, setPeople] = useState<Professional[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    tasksApi.eligible(job.id, task.professional_type as ProfessionalType).then(setPeople, (failure) => {
      setError(errorMessage(t, failure))
      setPeople([])
    })
  }, [job.id, task.professional_type, t])
  async function assign(profile: Professional) {
    try {
      await tasksApi.assign(task.id, profile.id)
      onDone()
    } catch (failure) {
      setError(errorMessage(t, failure))
    }
  }
  if (!people) return <p className="text-[13px] text-muted">{t('deals.loading')}</p>
  return (
    <div>
      <p className="text-[14px] text-navy-soft">{t('field.desk.assignBody', { type: t(`field.types.${task.professional_type}`) })}</p>
      {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
      {people.length === 0 && <p className="mt-4 rounded-xl bg-paper px-4 py-6 text-center text-[13px] text-muted">{t('field.desk.noneEligible')}</p>}
      <ul className="mt-4 space-y-2">
        {people.map((person) => (
          <li key={person.id} className="flex items-center gap-3 rounded-xl border border-mist px-3 py-3">
            <span className="grid size-10 place-items-center rounded-full bg-gold/15 text-[#9a6c12]">
              <UsersIcon className="size-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[14px] font-medium text-navy">{person.name}</span>
              <span className="block text-[12px] text-muted">{person.registration_number}</span>
            </span>
            <button type="button" onClick={() => void assign(person)} className="rounded-full bg-gold px-4 py-2 text-[13px] font-semibold text-navy">
              {t('field.desk.assign')}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function CorrectionForm({ task, onDone }: { task: Task; onDone: () => void }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  async function send() {
    try {
      await tasksApi.correction(task.id, reason.trim())
      onDone()
    } catch (failure) {
      setError(errorMessage(t, failure))
    }
  }
  return (
    <div>
      <p className="text-[14px] text-navy-soft">{t('field.desk.correctionBody')}</p>
      <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={4} className="mt-4 w-full rounded-xl border border-mist px-3 py-2.5 text-[14px] outline-none focus:border-gold" />
      {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
      <button type="button" disabled={!reason.trim()} onClick={() => void send()} className="mt-4 h-11 w-full rounded-full bg-navy text-[14px] font-semibold text-white disabled:opacity-50">
        {t('field.desk.correctionSend')}
      </button>
    </div>
  )
}
