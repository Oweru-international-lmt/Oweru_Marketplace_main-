import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { ChevronRightIcon, ClockIcon, DocumentIcon, MapPinIcon, ShieldIcon, UsersIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatShortDate } from '../../lib/format'
import { satelliteLayer } from '../../lib/maps'
import { tasksApi, type Task } from '../../lib/tasksApi'
import { SidePanel } from '../deals/ui'

// LOC-03, PRO-03: one task list for local officials, professionals and
// listers doing site capture. After R9 (the jobs as a list beside a map) with
// R8's new-request cards on top: who asks, what and where, Decline and Accept.

type Tab = 'open' | 'done'

export function TasksPage() {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[] | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('open')
  const [version, setVersion] = useState(0)
  const [declining, setDeclining] = useState<Task | null>(null)
  const [hovered, setHovered] = useState<string | null>(null)
  useDocumentTitle(t('field.tasks.title'))

  useEffect(() => {
    let live = true
    tasksApi
      .list()
      .then((page) => live && setTasks(page.results))
      .catch((failure) => {
        if (!live) return
        setError(errorMessage(t, failure))
        setTasks([])
      })
    return () => {
      live = false
    }
  }, [t, version])

  const requests = useMemo(() => (tasks ?? []).filter((row) => row.kind === 'PROFESSIONAL' && row.status === 'ASSIGNED'), [tasks])
  const rows = useMemo(() => (tasks ?? []).filter((row) => !requests.includes(row)).filter((row) => (tab === 'done' ? row.status === 'SUBMITTED' || row.status === 'TIMED_OUT' : row.status !== 'SUBMITTED' && row.status !== 'TIMED_OUT')), [tasks, requests, tab])

  async function accept(task: Task) {
    try {
      await tasksApi.decide(task.id, 'ACCEPT')
      navigate(`/tasks/${task.id}`)
    } catch (failure) {
      setError(errorMessage(t, failure))
    }
  }

  if (!tasks) return <FullPageLoader inline />
  return (
    <div className="pb-10">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[26px] font-bold tracking-wide text-navy uppercase">{t('field.tasks.title')}</h1>
          <p className="mt-1 text-[13px] text-muted">{t('field.tasks.subtitle')}</p>
        </div>
        <div role="tablist" className="flex rounded-xl border border-mist bg-white p-1">
          {(['open', 'done'] as Tab[]).map((value) => (
            <button key={value} type="button" role="tab" aria-selected={tab === value} onClick={() => setTab(value)} className={`relative rounded-lg px-4 py-1.5 text-[13px] ${tab === value ? 'font-semibold text-navy' : 'text-muted'}`}>
              {tab === value && <motion.span layoutId="tasks-tab" className="absolute inset-0 rounded-lg bg-gold/20" />}
              <span className="relative">{t(`field.tasks.tabs.${value}`)}</span>
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {/* R8: new job requests. */}
      <AnimatePresence>
        {requests.length > 0 && (
          <motion.section initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mb-6 rounded-3xl bg-navy p-4 text-white sm:p-5">
            <h2 className="text-[15px] font-bold tracking-[0.06em] uppercase">{t('field.tasks.newRequests', { count: requests.length })}</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {requests.map((task, index) => (
                <motion.article key={task.id} initial={reduce ? false : { opacity: 0, y: 14, rotate: -1 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ delay: index * 0.08 }} className="rounded-2xl bg-white p-4 text-navy">
                  <div className="flex items-start gap-3">
                    <span className="grid size-12 shrink-0 place-items-center rounded-full bg-gold/15 text-[#9a6c12]">
                      <ShieldIcon className="size-6" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[16px] font-semibold">{t(`field.types.${task.professional_type}`)}</p>
                      <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-muted">
                        <MapPinIcon className="size-3.5 shrink-0" />
                        <span className="truncate">{task.area}</span>
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">{t('field.tasks.due')}</p>
                      <p className="text-[13px] font-semibold">{task.due_at ? formatShortDate(task.due_at, i18n.language) : '-'}</p>
                    </div>
                  </div>
                  <p className="mt-3 text-[12px] text-muted">{t('field.tasks.property', { id: task.property_id })}</p>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <button type="button" onClick={() => setDeclining(task)} className="h-11 rounded-full border border-mist text-[14px] font-semibold text-navy-soft hover:bg-paper">
                      {t('field.tasks.decline')}
                    </button>
                    <motion.button type="button" whileTap={{ scale: 0.96 }} onClick={() => void accept(task)} className="h-11 rounded-full bg-gold text-[14px] font-bold text-navy shadow-[0_8px_20px_-10px_rgba(200,145,40,0.9)]">
                      {t('field.tasks.accept')}
                    </motion.button>
                  </div>
                </motion.article>
              ))}
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* R9: the list beside the map. */}
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
        <ul className="space-y-3">
          {rows.length === 0 && <li className="rounded-2xl border border-dashed border-mist bg-white px-6 py-12 text-center text-[14px] text-muted">{t(`field.tasks.empty.${tab}`)}</li>}
          {rows.map((task, index) => (
            <motion.li key={task.id} initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }} onMouseEnter={() => setHovered(task.id)} onMouseLeave={() => setHovered(null)}>
              <Link to={`/tasks/${task.id}`} className={`flex items-center gap-4 rounded-2xl border bg-white p-3 pr-4 transition-shadow hover:shadow-card ${hovered === task.id ? 'border-gold' : 'border-mist'}`}>
                <span className={`grid size-16 shrink-0 place-items-center rounded-xl ${KIND_TONE[task.kind]}`}>
                  <KindIcon task={task} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-[15px] font-semibold text-navy">{task.kind === 'PROFESSIONAL' ? t(`field.types.${task.professional_type}`) : t(`field.kinds.${task.kind}`)}</span>
                  </span>
                  <span className="mt-0.5 block truncate text-[13px] text-muted">{task.area}</span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
                    <span>{task.property_id}</span>
                    {task.due_at && (
                      <span className="inline-flex items-center gap-1">
                        <ClockIcon className="size-3.5" />
                        {formatShortDate(task.due_at, i18n.language)}
                      </span>
                    )}
                  </span>
                </span>
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap ${STATUS_TONE[task.status]}`}>{t(`field.statuses.${task.status}`)}</span>
                <ChevronRightIcon className="size-4 text-muted" />
              </Link>
            </motion.li>
          ))}
        </ul>
        <div className="sticky top-4 hidden h-[520px] overflow-hidden rounded-3xl border border-mist lg:block">
          <TasksMap tasks={rows} hovered={hovered} onOpen={(id) => navigate(`/tasks/${id}`)} />
        </div>
      </div>

      <SidePanel open={declining !== null} title={t('field.tasks.declineTitle')} onClose={() => setDeclining(null)}>
        {declining && (
          <DeclineForm
            task={declining}
            onDone={() => {
              setDeclining(null)
              setVersion((value) => value + 1)
            }}
          />
        )}
      </SidePanel>
    </div>
  )
}

const KIND_TONE: Record<Task['kind'], string> = {
  SITE_CAPTURE: 'bg-[#e9f6ee] text-success',
  LOCAL_OFFICE: 'bg-[#fdf3e2] text-[#9a6c12]',
  PROFESSIONAL: 'bg-[#e8eefb] text-[#3552a8]',
  REGISTRY: 'bg-[#f1e9fa] text-[#6b3fa0]',
}

const STATUS_TONE: Record<Task['status'], string> = {
  UNASSIGNED: 'bg-mist/70 text-muted',
  NEEDS_OFFICIAL: 'bg-danger-soft text-danger',
  ASSIGNED: 'bg-[#fdf3d8] text-[#7a5410]',
  ACCEPTED: 'bg-[#e8eefb] text-[#3552a8]',
  SUBMITTED: 'bg-success-soft text-success',
  TIMED_OUT: 'bg-danger-soft text-danger',
}

function KindIcon({ task }: { task: Task }) {
  if (task.kind === 'SITE_CAPTURE') return <MapPinIcon className="size-7" />
  if (task.kind === 'LOCAL_OFFICE') return <UsersIcon className="size-7" />
  if (task.kind === 'REGISTRY') return <DocumentIcon className="size-7" />
  return <ShieldIcon className="size-7" />
}

function DeclineForm({ task, onDone }: { task: Task; onDone: () => void }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function decline() {
    setBusy(true)
    setError('')
    try {
      await tasksApi.decide(task.id, 'DECLINE', reason.trim())
      onDone()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      <p className="text-[14px] leading-relaxed text-navy-soft">{t('field.tasks.declineBody', { area: task.area })}</p>
      <label className="mt-4 block text-[13px] font-medium text-navy">
        {t('field.tasks.reason')}
        <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={4} className="mt-1.5 w-full rounded-xl border border-mist px-3 py-2.5 text-[14px] outline-none focus:border-gold focus:ring-2 focus:ring-gold/20" />
      </label>
      {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
      <button type="button" disabled={busy} onClick={() => void decline()} className="mt-4 h-12 w-full rounded-full bg-navy text-[14px] font-semibold text-white disabled:opacity-60">
        {t('field.tasks.declineConfirm')}
      </button>
    </div>
  )
}

const taskPin = (active: boolean) =>
  L.divIcon({
    className: '',
    iconSize: [28, 36],
    iconAnchor: [14, 34],
    html: `<svg viewBox="0 0 36 46" width="28" height="36" style="filter:drop-shadow(0 4px 6px rgba(15,23,42,.45));transform:scale(${active ? 1.25 : 1});transform-origin:bottom center;transition:transform .2s"><path d="M18 1C8.6 1 1 8.5 1 17.8 1 30 18 45 18 45s17-15 17-27.2C35 8.5 27.4 1 18 1Z" fill="${active ? '#c89128' : '#0f172a'}"/><circle cx="18" cy="17.5" r="6.5" fill="#fff"/></svg>`,
  })

function TasksMap({ tasks, hovered, onOpen }: { tasks: Task[]; hovered: string | null; onOpen: (id: string) => void }) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const group = useRef<L.LayerGroup | null>(null)
  const openRef = useRef(onOpen)
  useEffect(() => {
    openRef.current = onOpen
  }, [onOpen])

  useEffect(() => {
    if (!element.current) return
    const instance = L.map(element.current, { zoomControl: true }).setView([-6.37, 34.89], 5)
    satelliteLayer().addTo(instance)
    group.current = L.layerGroup().addTo(instance)
    map.current = instance
    return () => {
      instance.remove()
      map.current = null
    }
  }, [])

  useEffect(() => {
    const instance = map.current
    if (!instance || !group.current) return
    group.current.clearLayers()
    const located = tasks.filter((task) => task.approx_point)
    located.forEach((task) => {
      const [lng, lat] = task.approx_point!
      L.marker([lat, lng], { icon: taskPin(task.id === hovered), title: task.property_id }).on('click', () => openRef.current(task.id)).addTo(group.current!)
    })
    if (located.length && hovered === null) {
      instance.fitBounds(L.latLngBounds(located.map((task) => [task.approx_point![1], task.approx_point![0]] as L.LatLngTuple)), { padding: [40, 40], maxZoom: 14 })
    }
  }, [tasks, hovered])

  return <div ref={element} className="size-full" aria-label="Map of task areas" role="img" />
}
