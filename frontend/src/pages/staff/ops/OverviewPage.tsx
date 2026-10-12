import { motion } from 'motion/react'
import { useEffect, useMemo, useState, type ComponentType, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { AlertIcon, ArrowRightIcon, BanknoteIcon, ChatIcon, DocumentIcon } from '../../../components/icons'
import { PageHeader } from '../../../components/PageHeader'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'
import type { FullCheck, FullCheckStatus } from '../../../lib/servicesApi'
import { staffApi, type ComplaintRoute, type DeskComplaint } from '../../../lib/staffApi'
import { Card, CardTitle, ComplaintChip } from './ui'

type Loaded = { complaints: DeskComplaint[]; checks: FullCheck[] } | { error: string }

const OPEN = (row: DeskComplaint) => row.status !== 'RESOLVED' && row.status !== 'CLOSED'

// Staff home, after W2 inside the W1 shell: four counts, the full checks
// ordered over two weeks, open complaints by team, checks by stage, and the
// latest complaints.
export function OverviewPage() {
  const { t } = useTranslation()
  const [loaded, setLoaded] = useState<Loaded | null>(null)

  useEffect(() => {
    let cancelled = false
    // A Verifier may see no full checks yet; an empty list is fine.
    Promise.all([staffApi.complaints(), staffApi.fullChecks().then((page) => page.results, () => [] as FullCheck[])])
      .then(([complaints, checks]) => !cancelled && setLoaded({ complaints, checks }))
      .catch((error: unknown) => !cancelled && setLoaded({ error: errorMessage(t, error) }))
    return () => {
      cancelled = true
    }
  }, [t])

  return (
    <>
      <PageHeader title={t('staff.overview.title')} />
      {!loaded ? <FullPageLoader inline /> : 'error' in loaded ? <Alert tone="error">{loaded.error}</Alert> : <Board complaints={loaded.complaints} checks={loaded.checks} />}
    </>
  )
}

function Board({ complaints, checks }: { complaints: DeskComplaint[]; checks: FullCheck[] }) {
  const { t } = useTranslation()
  const open = complaints.filter(OPEN)
  const counts: { label: string; value: number; icon: ComponentType<SVGProps<SVGSVGElement>>; to: string }[] = [
    { label: t('staff.overview.openComplaints'), value: open.length, icon: ChatIcon, to: '/staff/complaints' },
    { label: t('staff.overview.overdue'), value: complaints.filter((row) => row.overdue).length, icon: AlertIcon, to: '/staff/complaints?filter=overdue' },
    { label: t('staff.overview.toConfirm'), value: checks.filter((check) => check.status === 'AWAITING_PAYMENT').length, icon: BanknoteIcon, to: '/staff/full-checks?status=AWAITING_PAYMENT' },
    { label: t('staff.overview.toReview'), value: checks.filter((check) => check.status === 'UNDER_REVIEW').length, icon: DocumentIcon, to: '/staff/full-checks?status=UNDER_REVIEW' },
  ]

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {counts.map((count, index) => (
          <motion.div key={count.label} className="h-full" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05, duration: 0.35 }}>
            <Link to={count.to} className="flex h-full items-end justify-between gap-4 rounded-[10px] border border-mist bg-white px-6 pt-5 pb-4 transition-shadow hover:shadow-card">
              <span className="min-w-0">
                <span className="block truncate text-[15px] font-medium text-navy/80">{count.label}</span>
                <span className="mt-3 block text-[30px] leading-none font-semibold text-navy tabular-nums">{count.value.toLocaleString()}</span>
              </span>
              <count.icon className="size-10 shrink-0 text-mist" strokeWidth={1.4} />
            </Link>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)]">
        <OrdersChart checks={checks} />
        <TeamGauge complaints={open} />
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <StageBars checks={checks} />
        <RecentComplaints complaints={complaints} />
      </div>
    </div>
  )
}

const DAYS = 14

function OrdersChart({ checks }: { checks: FullCheck[] }) {
  const { t, i18n } = useTranslation()
  const [hover, setHover] = useState<number | null>(null)
  // Fixed when the page opens, so re-renders don't move the window.
  const [today] = useState(() => {
    const now = new Date()
    now.setHours(0, 0, 0, 0)
    return now
  })
  // One point per day for the last two weeks, oldest first.
  const days = useMemo(() => {
    return Array.from({ length: DAYS }, (_, index) => {
      const start = new Date(today)
      start.setDate(today.getDate() - (DAYS - 1 - index))
      const end = new Date(start)
      end.setDate(start.getDate() + 1)
      const count = checks.filter((check) => {
        const at = new Date(check.created_at)
        return at >= start && at < end
      }).length
      return { date: start, count }
    })
  }, [checks, today])
  const total = days.reduce((sum, day) => sum + day.count, 0)
  const max = Math.max(4, ...days.map((day) => day.count))
  const [width, height, pad] = [600, 190, 12]
  const x = (index: number) => pad + (index * (width - pad * 2)) / (DAYS - 1)
  const y = (count: number) => height - pad - (count / max) * (height - pad * 2 - 18)
  const line = days.map((day, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${y(day.count).toFixed(1)}`).join(' ')
  const area = `${line} L${x(DAYS - 1)},${height - pad} L${x(0)},${height - pad} Z`
  const point = hover === null ? null : days[hover]
  const label = (date: Date) => new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { day: 'numeric', month: 'short' }).format(date)

  return (
    <Card className="px-6 pt-6 pb-4">
      <CardTitle>{t('staff.overview.ordersTitle')}</CardTitle>
      <p className="mt-2 text-[30px] leading-none font-semibold text-navy tabular-nums">{total}</p>
      <p className="mt-1 text-xs text-muted">{t('staff.overview.ordersNote', { days: DAYS })}</p>
      <div className="relative mt-4">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-[190px] w-full overflow-visible"
          role="img"
          aria-label={t('staff.overview.ordersTitle')}
          onMouseLeave={() => setHover(null)}
          onMouseMove={(event) => {
            const box = event.currentTarget.getBoundingClientRect()
            const ratio = (event.clientX - box.left) / box.width
            setHover(Math.max(0, Math.min(DAYS - 1, Math.round(ratio * (DAYS - 1)))))
          }}
        >
          <defs>
            <linearGradient id="orders-fill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#c89128" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#c89128" stopOpacity="0" />
            </linearGradient>
          </defs>
          <line x1={pad} x2={width - pad} y1={height - pad} y2={height - pad} stroke="#dde1e8" strokeWidth="1" />
          <path d={area} fill="url(#orders-fill)" />
          <path d={line} fill="none" stroke="#c89128" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          {point && hover !== null && (
            <>
              <line x1={x(hover)} x2={x(hover)} y1={pad} y2={height - pad} stroke="#0f172a" strokeOpacity="0.15" strokeWidth="1" />
              <circle cx={x(hover)} cy={y(point.count)} r="6" fill="#c89128" stroke="#fff" strokeWidth="2" />
            </>
          )}
        </svg>
        {point && hover !== null && (
          <div
            className="pointer-events-none absolute -translate-x-1/2 -translate-y-full rounded-[6px] bg-navy px-3 py-2 text-white shadow-lift"
            style={{ left: `${(x(hover) / width) * 100}%`, top: `${(y(point.count) / height) * 100}%`, marginTop: -12 }}
          >
            <p className="text-[10px] whitespace-nowrap text-white/65">{label(point.date)}</p>
            <p className="text-[13px] font-semibold whitespace-nowrap">{t('staff.overview.ordersPoint', { count: point.count })}</p>
          </div>
        )}
        <div className="mt-1 flex justify-between px-1 text-[11px] text-muted">
          <span>{label(days[0].date)}</span>
          <span>{label(days[Math.floor(DAYS / 2)].date)}</span>
          <span>{label(days[DAYS - 1].date)}</span>
        </div>
      </div>
    </Card>
  )
}

// Validated categorical order (dataviz validator, light surface): fixed per team.
const ROUTE_COLOUR: Record<ComplaintRoute, string> = { HEAD_OPERATIONS: '#4a6bd1', MANAGEMENT: '#c89128', VERIFIER: '#2f9e7a', DIRECTOR: '#9a5cc6' }
const ROUTES: ComplaintRoute[] = ['HEAD_OPERATIONS', 'MANAGEMENT', 'VERIFIER', 'DIRECTOR']

function TeamGauge({ complaints }: { complaints: DeskComplaint[] }) {
  const { t } = useTranslation()
  const total = complaints.length
  const parts = ROUTES.map((route) => ({ route, count: complaints.filter((row) => row.route === route).length }))
  // A half ring split by team, with small gaps between the pieces.
  const [cx, cy, r] = [120, 118, 92]
  const gap = 0.05
  const point = (angle: number) => `${(cx + r * Math.cos(angle)).toFixed(1)},${(cy + r * Math.sin(angle)).toFixed(1)}`
  const shown = parts.filter((part) => part.count > 0)
  const arcs = shown.map((part, index) => {
    // Each piece starts where the ones before it end.
    const before = shown.slice(0, index).reduce((sum, previous) => sum + previous.count, 0)
    const start = Math.PI + (before / Math.max(total, 1)) * Math.PI
    const sweep = (part.count / Math.max(total, 1)) * Math.PI
    const inset = shown.length > 1 ? gap / 2 : 0
    const from = start + inset
    const to = Math.max(from, start + sweep - inset)
    return { route: part.route, d: `M${point(from)} A${r},${r} 0 0 1 ${point(to)}` }
  })

  return (
    <Card className="px-6 pt-6 pb-6">
      <CardTitle>{t('staff.overview.teamsTitle')}</CardTitle>
      <div className="relative mx-auto mt-5 w-full max-w-[260px]">
        <svg viewBox="0 0 240 130" className="w-full" role="img" aria-label={t('staff.overview.teamsTitle')}>
          <path d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}`} fill="none" stroke="#eef1f5" strokeWidth="14" strokeLinecap="round" />
          {arcs.map((arc) => (
            <path key={arc.route} d={arc.d} fill="none" stroke={ROUTE_COLOUR[arc.route]} strokeWidth="14" strokeLinecap="round" />
          ))}
        </svg>
        <div className="absolute inset-x-0 bottom-1 text-center">
          <p className="text-xs text-muted">{t('staff.overview.openComplaints')}</p>
          <p className="text-[26px] leading-tight font-semibold text-navy tabular-nums">{total}</p>
        </div>
      </div>
      <ul className="mt-5 grid grid-cols-2 gap-x-6 gap-y-2.5">
        {parts.map((part) => (
          <li key={part.route} className="flex items-center gap-2 text-[13px] text-navy/80">
            <span className="size-3 shrink-0 rounded-[3px]" style={{ backgroundColor: ROUTE_COLOUR[part.route] }} />
            <span className="min-w-0 flex-1 truncate">{t(`staff.routes.${part.route}`)}</span>
            <span className="font-semibold text-navy tabular-nums">{part.count}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

const STAGES: FullCheckStatus[] = ['AWAITING_PAYMENT', 'AWAITING_CONSENT', 'IN_PROGRESS', 'UNDER_REVIEW', 'PASSED', 'PROBLEM_FOUND', 'NOT_COMPLETED']

function StageBars({ checks }: { checks: FullCheck[] }) {
  const { t } = useTranslation()
  const [hover, setHover] = useState<FullCheckStatus | null>(null)
  const counts = STAGES.map((status) => ({ status, count: checks.filter((check) => check.status === status).length }))
  const running = counts.slice(0, 4).reduce((sum, part) => sum + part.count, 0)
  const finished = counts.slice(4).reduce((sum, part) => sum + part.count, 0)
  const max = Math.max(4, ...counts.map((part) => part.count))
  const ticks = [0, Math.round(max / 2), max]

  return (
    <Card className="px-6 pt-6 pb-5">
      <CardTitle
        action={
          <Link to="/staff/full-checks" className="inline-flex h-9 items-center gap-1.5 rounded-[6px] border border-mist px-3 text-[13px] text-navy hover:border-navy/30">
            {t('staff.overview.fullView')}
            <ArrowRightIcon className="size-3.5 -rotate-45" />
          </Link>
        }
      >
        {t('staff.overview.stagesTitle')}
      </CardTitle>
      <div className="mt-4 flex gap-10">
        <Stat label={t('staff.overview.running')} value={running} tone="bg-gold" />
        <Stat label={t('staff.overview.finished')} value={finished} tone="bg-gold/30" />
      </div>
      <div className="mt-5 grid grid-cols-[auto_minmax(0,1fr)] gap-3">
        <div className="flex h-[180px] flex-col justify-between text-right text-[11px] text-muted tabular-nums">
          {[...ticks].reverse().map((tick) => (
            <span key={tick}>{tick}</span>
          ))}
        </div>
        <div className="relative h-[180px]">
          {ticks.map((tick) => (
            <span key={tick} aria-hidden="true" className="absolute inset-x-0 border-t border-mist/70" style={{ bottom: `${(tick / max) * 100}%` }} />
          ))}
          <ul className="absolute inset-0 flex items-end justify-around gap-2">
            {counts.map((part, index) => (
              <li
                key={part.status}
                className="relative flex h-full w-full max-w-11 items-end"
                onMouseEnter={() => setHover(part.status)}
                onMouseLeave={() => setHover(null)}
              >
                <motion.span
                  className={`block w-full rounded-t-[4px] ${index < 4 ? 'bg-gold' : 'bg-gold/30'}`}
                  initial={{ height: 0 }}
                  animate={{ height: `${(part.count / max) * 100}%` }}
                  transition={{ duration: 0.5, delay: index * 0.05 }}
                  style={{ minHeight: part.count ? 4 : 0 }}
                />
                {hover === part.status && (
                  <span className="absolute bottom-full left-1/2 mb-2 -translate-x-1/2 rounded-[6px] bg-navy px-2.5 py-1.5 text-[11px] whitespace-nowrap text-white">
                    {t(`fullCheck.statuses.${part.status}`)}: <b>{part.count}</b>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
        <span />
        <div className="flex justify-around gap-1 text-center text-[10px] leading-tight break-words text-muted sm:text-[11px]">
          {counts.map((part) => (
            <span key={part.status} className="w-full max-w-16 min-w-0 [overflow-wrap:anywhere]">
              {t(`staff.stageShort.${part.status}`)}
            </span>
          ))}
        </div>
      </div>
    </Card>
  )
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <p className="flex items-center gap-2 text-[13px] text-navy/75">
        <span className={`size-3 rounded-[3px] ${tone}`} />
        {label}
      </p>
      <p className="mt-1 pl-5 text-[24px] leading-tight font-semibold text-navy tabular-nums">{value}</p>
    </div>
  )
}

// W2's recent list: a coloured bar, the date, two lines of text and a chip.
const BAR: Record<string, string> = {
  RECEIVED: 'bg-[#4a6bd1]',
  IN_REVIEW: 'bg-gold',
  WAITING_INFORMATION: 'bg-[#9a5cc6]',
  RESOLVED: 'bg-success',
  UNDER_FINAL_REVIEW: 'bg-navy',
  CLOSED: 'bg-mist',
}

function RecentComplaints({ complaints }: { complaints: DeskComplaint[] }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const recent = [...complaints].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 6)

  return (
    <Card className="px-6 pt-6 pb-4">
      <CardTitle
        action={
          <Link to="/staff/complaints" className="inline-flex h-9 items-center gap-1.5 rounded-[6px] border border-mist px-3 text-[13px] text-navy hover:border-navy/30">
            {t('staff.overview.viewAll')}
            <ArrowRightIcon className="size-3.5 -rotate-45" />
          </Link>
        }
      >
        {t('staff.overview.recentTitle')}
      </CardTitle>
      {recent.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted">{t('staff.complaints.empty')}</p>
      ) : (
        <ul className="mt-4 space-y-1">
          {recent.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => navigate(`/staff/complaints/${row.id}`)}
                className="group flex w-full items-center gap-4 rounded-[8px] px-2 py-2.5 text-left transition-shadow hover:bg-white hover:shadow-[0_4px_18px_-6px_rgba(15,23,42,0.22)]"
              >
                <span className={`h-11 w-[3px] shrink-0 rounded-full ${BAR[row.status]}`} />
                <span className="w-24 shrink-0 text-[13px] font-medium text-navy">{formatShortDate(row.created_at, i18n.language)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-navy">
                    {row.name} · {t(`complaint.types.${row.category}`)}
                  </span>
                  <span className="block truncate text-xs text-muted">
                    {row.reference} · {t(`staff.routes.${row.route}`)}
                  </span>
                </span>
                {row.overdue ? (
                  <span className="rounded-full bg-danger-soft px-2.5 py-0.5 text-[11px] font-medium text-danger">{t('staff.complaints.overdue')}</span>
                ) : (
                  <ComplaintChip status={row.status} />
                )}
                <ArrowRightIcon className="size-4 shrink-0 -rotate-45 text-transparent transition-colors group-hover:text-navy" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
