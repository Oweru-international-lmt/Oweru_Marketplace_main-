import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import aerial from '../../../assets/photos/dar-aerial-720.webp'
import coast from '../../../assets/photos/dar-coast-720.webp'
import sunset from '../../../assets/photos/dar-sunset-720.webp'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import {
  AlertIcon,
  ArrowRightIcon,
  BarsIcon,
  BuildingIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClockIcon,
  FilterIcon,
  InfoIcon,
  MapPinIcon,
  RulerIcon,
  SearchIcon,
} from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { can } from '../../../auth/access'
import { useAuth } from '../../../auth/useAuth'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate, formatTshShort } from '../../../lib/format'
import { list, panelApi, type District, type Featured, type Panel, type PanelFilters, type PanelRow, type Region } from '../../../lib/panelApi'
import { AreaMap } from './AreaMap'
import { Donut, GhostBars, GOLD, GroupedBars, NAVY, SegmentBar, Sparkline, StepFunnel, TrendLine, TwoLines } from './charts'
import {
  BANDS,
  byKind,
  byRegion,
  CATEGORIES,
  counts,
  isoDay,
  monthKey,
  monthly,
  percentChange,
  priceStats,
  priceTrend,
  sourceKind,
  sources,
  STAGES,
  stockDays,
  stockOn,
  sum,
  tagDetail,
} from './data'

type View = 'overview' | 'areas' | 'sources'
const RANGES = [30, 90, 180, 365] as const
const PHOTOS = [aerial, coast, sunset]
const LEVEL_COLOURS = ['#cbd5e1', '#64748b', GOLD, NAVY]

// SRD 18, after M1 (frame, regions, demand, mix), M2 (tiles, price trend,
// verification donut, featured strip), M4 (the buyer funnel), M3 (areas on
// the map) and M6 (source tags). Counts by area only (MON-03).
export function MarketPanelPage() {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  useDocumentTitle(t('staff.market.title'))
  const [params, setParams] = useSearchParams()
  const view = (['overview', 'areas', 'sources'] as const).find((value) => value === params.get('view')) ?? 'overview'
  const [days, setDays] = useState<(typeof RANGES)[number]>(180)
  const [region, setRegion] = useState('')
  const [district, setDistrict] = useState('')
  const [category, setCategory] = useState('')
  const [panel, setPanel] = useState<Panel | null>(null)
  const [previous, setPrevious] = useState<Panel | null>(null)
  const [regions, setRegions] = useState<Region[]>([])
  const [districts, setDistricts] = useState<District[]>([])
  const [featured, setFeatured] = useState<Featured[]>([])
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [today] = useState(() => new Date())

  const filters = useMemo<PanelFilters>(() => {
    const end = today
    const start = new Date(end.getTime() - (days - 1) * 86_400_000)
    return { start: isoDay(start), end: isoDay(end), region: region || undefined, district: district || undefined, category: category || undefined }
  }, [days, region, district, category, today])

  useEffect(() => {
    let live = true
    const before = { ...filters, end: isoDay(new Date(new Date(filters.start).getTime() - 86_400_000)), start: isoDay(new Date(new Date(filters.start).getTime() - days * 86_400_000)) }
    panelApi.panel(filters).then(
      (loaded) => live && setPanel(loaded),
      (caught) => live && setError(errorMessage(t, caught)),
    )
    panelApi.panel(before).then(
      (loaded) => live && setPrevious(loaded),
      () => live && setPrevious(null),
    )
    return () => {
      live = false
    }
  }, [filters, days, t])

  useEffect(() => {
    panelApi.regions().then((rows) => setRegions(list(rows)), () => setRegions([]))
    if (can(user, 'marketing.manage')) panelApi.featured().then(setFeatured, () => setFeatured([]))
  }, [user])

  useEffect(() => {
    if (!region) return
    let live = true
    panelApi.districts(region).then((rows) => live && setDistricts(list(rows)), () => live && setDistricts([]))
    return () => {
      live = false
    }
  }, [region])

  async function exportExcel() {
    setExporting(true)
    try {
      const blob = await panelApi.exportPanel(filters)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `oweru-soko-${filters.start}-${filters.end}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
    } catch (caught) {
      setError(errorMessage(t, caught))
    } finally {
      setExporting(false)
    }
  }

  const setView = (next: View) => setParams(next === 'overview' ? {} : { view: next }, { replace: true })
  const month = useCallback((key: string) => new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { month: 'short' }).format(new Date(`${key}-01T00:00:00`)), [i18n.language])
  const money = useCallback((value: number) => formatTshShort(value, i18n.language), [i18n.language])

  return (
    <div className="space-y-5">
      {/* M1: pill navigation centred in the top band. */}
      <nav aria-label={t('staff.market.title')} className="flex justify-center">
        <div className="flex items-center gap-1 rounded-full bg-white p-1 shadow-[0_1px_3px_rgba(15,23,42,0.08)] ring-1 ring-mist/70">
          {(['overview', 'areas', 'sources'] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-current={view === value ? 'page' : undefined}
              onClick={() => setView(value)}
              className={`inline-flex h-10 items-center gap-1.5 rounded-full px-5 text-[14px] transition-colors ${view === value ? 'bg-navy font-medium text-white' : 'text-navy-soft hover:text-navy'}`}
            >
              {view === value && <ChevronLeftIcon className="size-3.5 text-gold-light" />}
              {t(`staff.market.views.${value}`)}
              {view === value && <ChevronRightIcon className="size-3.5 text-gold-light" />}
            </button>
          ))}
        </div>
      </nav>

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] leading-tight font-medium text-navy sm:text-[28px]">{t(`staff.market.headings.${view}`)}</h1>
          <p className="mt-1 text-[15px] text-muted">{t(`staff.market.subtitles.${view}`)}</p>
        </div>
        <div className="flex items-center gap-2">
          <FilterButton>
            <Filters
              days={days}
              onDays={setDays}
              regions={regions}
              region={region}
              onRegion={(value) => {
                setRegion(value)
                setDistrict('')
                if (!value) setDistricts([])
              }}
              districts={districts}
              district={district}
              onDistrict={setDistrict}
              category={category}
              onCategory={setCategory}
            />
          </FilterButton>
          <button
            type="button"
            onClick={exportExcel}
            disabled={exporting}
            className="inline-flex h-11 items-center gap-2 rounded-full bg-white px-5 text-[14px] text-navy shadow-[0_1px_3px_rgba(15,23,42,0.08)] ring-1 ring-mist/70 hover:ring-navy/30 disabled:opacity-60"
          >
            <UploadIcon className="size-4" />
            {exporting ? t('staff.market.exporting') : t('staff.market.export')}
          </button>
        </div>
      </header>

      {error && <Alert tone="error">{error}</Alert>}
      {panel?.stale && (
        <p className="flex items-center gap-2 rounded-xl border border-gold/30 bg-[#fdf7ec] px-4 py-3 text-[13.5px] text-[#7a5410]">
          <InfoIcon className="size-4 shrink-0" />
          {t('staff.market.stale')}
        </p>
      )}

      {!panel ? (
        <FullPageLoader inline />
      ) : view === 'overview' ? (
        <Overview panel={panel} previous={previous} featured={featured} month={month} money={money} onMap={() => setView('areas')} />
      ) : view === 'areas' ? (
        <Areas panel={panel} month={month} />
      ) : (
        <Sources panel={panel} previous={previous} month={month} />
      )}

      {panel && (
        <p className="text-[12px] text-muted">
          {t('staff.market.generated', { date: panel.generated_at ? formatShortDate(panel.generated_at, i18n.language) : '-' })} · {t('staff.market.privacy')}
        </p>
      )}
    </div>
  )
}

function UploadIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M12 15V4M8 8l4-4 4 4M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" />
    </svg>
  )
}

function FilterButton({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])
  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label={t('staff.market.filters.title')}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="grid size-11 place-items-center rounded-full bg-white text-navy shadow-[0_1px_3px_rgba(15,23,42,0.08)] ring-1 ring-mist/70 hover:ring-navy/30"
      >
        <FilterIcon className="size-[18px]" />
      </button>
      {open && <div className="absolute top-full right-0 z-30 mt-2 w-[300px] rounded-2xl border border-mist bg-white p-4 shadow-[0_18px_40px_-12px_rgba(15,23,42,0.3)]">{children}</div>}
    </div>
  )
}

function Filters(props: {
  days: number
  onDays: (value: (typeof RANGES)[number]) => void
  regions: Region[]
  region: string
  onRegion: (value: string) => void
  districts: District[]
  district: string
  onDistrict: (value: string) => void
  category: string
  onCategory: (value: string) => void
}) {
  const { t } = useTranslation()
  const select = 'mt-1 h-10 w-full rounded-lg border border-mist bg-white px-3 text-[13.5px] text-navy outline-none focus:border-gold'
  return (
    <div className="space-y-3">
      <p className="text-[14px] font-semibold text-navy">{t('staff.market.filters.title')}</p>
      <div role="radiogroup" aria-label={t('staff.market.filters.range')} className="grid grid-cols-4 gap-1 rounded-lg bg-paper p-1">
        {RANGES.map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={props.days === value}
            onClick={() => props.onDays(value)}
            className={`h-8 rounded-md text-[12.5px] ${props.days === value ? 'bg-white font-semibold text-navy shadow-sm' : 'text-navy-soft'}`}
          >
            {t('staff.market.filters.days', { count: value })}
          </button>
        ))}
      </div>
      <label className="block text-[12.5px] text-navy-soft">
        {t('staff.market.filters.region')}
        <select value={props.region} onChange={(event) => props.onRegion(event.target.value)} className={select}>
          <option value="">{t('staff.market.filters.all')}</option>
          {props.regions.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
      <label className="block text-[12.5px] text-navy-soft">
        {t('staff.market.filters.district')}
        <select value={props.district} onChange={(event) => props.onDistrict(event.target.value)} disabled={!props.region} className={`${select} disabled:opacity-50`}>
          <option value="">{t('staff.market.filters.all')}</option>
          {props.districts.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
      <label className="block text-[12.5px] text-navy-soft">
        {t('staff.market.filters.category')}
        <select value={props.category} onChange={(event) => props.onCategory(event.target.value)} className={select}>
          <option value="">{t('staff.market.filters.all')}</option>
          {CATEGORIES.map((value) => <option key={value} value={value}>{t(`market.category.${value}`)}</option>)}
        </select>
      </label>
    </div>
  )
}

function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-[20px] border border-mist/70 bg-white ${className}`}>{children}</section>
}

function Change({ value, invert = false }: { value: number | null; invert?: boolean }) {
  const { t } = useTranslation()
  if (value === null) return <span className="text-[12.5px] text-muted">{t('staff.market.noComparison')}</span>
  const good = invert ? value < 0 : value >= 0
  return (
    <span className={`inline-flex items-center gap-1 text-[12.5px] ${good ? 'text-success' : 'text-danger'}`}>
      <span aria-hidden="true">{value >= 0 ? '↗' : '↘'}</span>
      {t('staff.market.change', { value: Math.abs(value) > 999 ? (value > 0 ? '>+999%' : '<-999%') : `${value >= 0 ? '+' : ''}${value.toFixed(1)}%` })}
    </span>
  )
}

// ---------------------------------------------------------------- overview

function Overview({ panel, previous, featured, month, money, onMap }: {
  panel: Panel
  previous: Panel | null
  featured: Featured[]
  month: (key: string) => string
  money: (value: number) => string
  onMap: () => void
}) {
  const { t } = useTranslation()
  const rows = panel.rows
  const { first, last } = stockDays(rows)
  const stock = stockOn(rows, last)
  const firstStock = stockOn(rows, first)
  const before = previous ? byKind(previous.rows, 'ACTIVITY') : []
  const active = sum(stock, 'active_listings')
  const price = priceStats(stock, 'selling_price')
  const sqm = priceStats(stock, 'price_per_sqm')

  const tiles = [
    { key: 'active', icon: BuildingIcon, value: active.toLocaleString(), change: percentChange(active, sum(firstStock, 'active_listings')) },
    { key: 'median', icon: BarsIcon, value: price.median !== null ? money(price.median) : '-', change: percentChange(price.median ?? 0, priceStats(firstStock, 'selling_price').median ?? 0) },
    { key: 'sqm', icon: RulerIcon, value: sqm.median !== null ? money(sqm.median) : '-', change: percentChange(sqm.median ?? 0, priceStats(firstStock, 'price_per_sqm').median ?? 0) },
  ]

  const trend = priceTrend(rows)
  const [span, setSpan] = useState<12 | 6 | 3>(12)
  const shown = trend.slice(-span)

  const levels = counts(stock, 'verification_mix')
  const levelTotal = Object.values(levels).reduce((total, value) => total + value, 0)
  const levelParts = [0, 1, 2, 3].map((level) => ({ label: t(`levels.short.${level}`), value: levels[String(level)] ?? 0, color: LEVEL_COLOURS[level] }))
  const verifiedShare = levelTotal ? Math.round((((levels['2'] ?? 0) + (levels['3'] ?? 0)) / levelTotal) * 100) : 0

  const regionNow = byRegion(stock, (row) => row.metrics.active_listings ?? 0)
  const regionBefore = byRegion(firstStock, (row) => row.metrics.active_listings ?? 0)
  const topRegions = Object.entries(regionNow).sort(([, a], [, b]) => b - a).slice(0, 3)

  const demand = monthly(rows, ['searches', 'enquiry_events'])
  const peak = demand.reduce((best, entry, index) => (entry.enquiry_events > (demand[best]?.enquiry_events ?? -1) ? index : best), 0)

  const mix = CATEGORIES.map((category) => ({ category, value: sum(stock.filter((row) => row.category === category), 'active_listings') }))
  const mixTotal = mix.reduce((total, entry) => total + entry.value, 0)
  const mixColours = [NAVY, GOLD, '#64748b']

  return (
    <div className="space-y-5">
      <div className="grid items-stretch gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          {/* M2: three tiles, label left and a small icon square right. */}
          <div className="grid gap-4 sm:grid-cols-3">
            {tiles.map(({ key, icon: Icon, value, change }) => (
              <Card key={key} className="px-5 py-4">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-[14px] text-navy-soft">{t(`staff.market.tiles.${key}`)}</p>
                  <span className="grid size-9 place-items-center rounded-lg bg-paper text-navy-soft"><Icon className="size-[18px]" /></span>
                </div>
                <p className="mt-1 text-[30px] leading-tight font-semibold text-navy tabular-nums">{value}</p>
                <p className="mt-1"><Change value={change} /></p>
              </Card>
            ))}
          </div>

          <Card className="px-5 pt-4 pb-2">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <h2 className="text-[18px] font-medium text-navy">{t('staff.market.trend.title')}</h2>
              <span className="flex items-center gap-4 text-[13px] text-navy-soft">
                <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-navy" />{t('staff.market.trend.average')}</span>
                <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-gold" />{t('staff.market.trend.median')}</span>
              </span>
              <span className="ml-auto flex gap-1.5">
                {([12, 6, 3] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={span === value}
                    onClick={() => setSpan(value)}
                    className={`h-8 rounded-full px-3.5 text-[12.5px] ${span === value ? 'bg-navy text-white' : 'bg-paper text-navy-soft hover:text-navy'}`}
                  >
                    {t('staff.market.trend.months', { count: value })}
                  </button>
                ))}
              </span>
            </div>
            {shown.length ? (
              <TrendLine
                labels={shown.map((entry) => month(entry.month))}
                solid={shown.map((entry) => entry.average)}
                dashed={shown.map((entry) => entry.median)}
                format={money}
                ariaLabel={t('staff.market.trend.title')}
              />
            ) : (
              <Empty />
            )}
          </Card>
        </div>

        {/* M2: the donut with its legend as labelled progress bars. */}
        <Card className="px-5 py-5">
          <h2 className="text-[18px] font-medium text-navy">{t('staff.market.levels.title')}</h2>
          <div className="mt-5">
            <Donut parts={levelParts} center={`${verifiedShare}%`} />
          </div>
          <p className="mt-2 text-center text-[12.5px] text-muted">{t('staff.market.levels.center')}</p>
          <ul className="mt-6 space-y-4">
            {levelParts.map((part) => (
              <li key={part.label} className="grid grid-cols-[1fr_120px] items-center gap-3 text-[14px] text-navy">
                <span className="truncate">{part.label}</span>
                <span className="h-1.5 overflow-hidden rounded-full bg-paper">
                  <span className="block h-full rounded-full" style={{ width: `${levelTotal ? (part.value / levelTotal) * 100 : 0}%`, backgroundColor: part.color }} />
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {featured.length > 0 && (
        <section>
          <div className="flex items-center justify-between">
            <h2 className="text-[18px] font-medium text-navy">{t('staff.market.featured')}</h2>
            <Link to="/staff/marketing/featured" className="text-[13.5px] font-medium text-[#9a6c12] hover:underline">{t('staff.market.viewAll')}</Link>
          </div>
          <ul className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {featured.slice(0, 4).map((row, index) => (
              <li key={row.id} className="overflow-hidden rounded-[18px] border border-mist/70 bg-white">
                <div className="relative h-[120px] bg-paper">
                  <img src={row.cover_url ?? PHOTOS[index % PHOTOS.length]} alt="" className="size-full object-cover" />
                  <span className="absolute bottom-2 left-2 rounded-full bg-white/85 px-2.5 py-0.5 text-[11.5px] text-navy backdrop-blur">{t('staff.market.forSale')}</span>
                  <Link to={`/listings/${row.listing_id}`} target="_blank" aria-label={row.listing_id} className="absolute top-2 right-2 grid size-8 place-items-center rounded-full bg-white/40 text-white backdrop-blur hover:bg-white/60">
                    <ArrowRightIcon className="size-4 -rotate-45" />
                  </Link>
                </div>
                <div className="px-3.5 py-3">
                  <p className="truncate text-[15px] font-medium text-navy">{t(`market.category.${row.category}`)}, {row.area.split(', ')[0]}</p>
                  <p className="mt-0.5 flex items-center gap-1 truncate text-[12.5px] text-muted"><MapPinIcon className="size-3.5 shrink-0" />{row.area.split(', ').slice(1).join(', ')}</p>
                  <p className="mt-3 flex items-center justify-between gap-2">
                    <span className="text-[17px] font-semibold text-navy">{money(row.selling_price)}</span>
                    <span className="rounded-full bg-paper px-2.5 py-0.5 text-[11.5px] text-navy-soft">{row.listing_id.slice(0, 12)}</span>
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* M1: the regional matrix, a photo card per region. */}
      <Card className="px-5 py-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[20px] font-medium text-navy">{t('staff.market.regions.title')}</h2>
          <button type="button" onClick={onMap} className="inline-flex h-10 items-center gap-1.5 rounded-full border border-mist px-4 text-[13.5px] text-navy hover:border-navy/30">
            {t('staff.market.regions.map')}
            <ChevronRightIcon className="size-4 rotate-90" />
          </button>
        </div>
        {topRegions.length ? (
          <ul className="mt-4 grid gap-3 md:grid-cols-3">
            {topRegions.map(([id, value], index) => {
              const change = percentChange(value, regionBefore[id] ?? 0)
              return (
                <li key={id} className="relative flex h-[150px] overflow-hidden rounded-[22px] bg-[#f4f4f6]">
                  <div className="flex flex-1 flex-col justify-between px-4 py-4">
                    <p className="text-[17px] text-navy">{panel.areas[id] ?? '-'}</p>
                    <p className="flex items-end gap-2">
                      <span className="text-[36px] leading-none font-light text-navy tabular-nums">{value.toLocaleString()}</span>
                      {change !== null && (
                        <span className={`mb-5 rounded-full px-1.5 py-0.5 text-[10.5px] ${change >= 0 ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'}`}>
                          {change >= 0 ? '+' : ''}{change.toFixed(0)}%
                        </span>
                      )}
                    </p>
                  </div>
                  <img src={PHOTOS[index % PHOTOS.length]} alt="" className="w-[48%] rounded-[22px] object-cover" />
                </li>
              )
            })}
          </ul>
        ) : (
          <Empty />
        )}
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Card className="px-5 py-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-[18px] font-medium text-navy">{t('staff.market.demand.title')}</h2>
              <p className="text-[13px] text-muted">{t('staff.market.demand.subtitle')}</p>
            </div>
            <span className="flex gap-4 text-[13px] text-navy-soft">
              <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-[#e7e7ea]" />{t('staff.market.demand.searches')}</span>
              <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-gold" />{t('staff.market.demand.enquiries')}</span>
            </span>
          </div>
          {demand.length ? (
            <div className="mt-3">
              <GhostBars labels={demand.map((entry) => month(entry.month))} outer={demand.map((entry) => entry.searches)} inner={demand.map((entry) => entry.enquiry_events)} format={(value) => Math.round(value).toLocaleString()} highlight={peak} />
            </div>
          ) : (
            <Empty />
          )}
        </Card>

        <Card className="px-5 py-5">
          <h2 className="text-[18px] font-medium text-navy">{t('staff.market.mix.title')}</h2>
          <p className="text-[13px] text-muted">{t('staff.market.mix.subtitle')}</p>
          <ul className="mt-5 space-y-5">
            {mix.map((entry, index) => {
              const share = mixTotal ? entry.value / mixTotal : 0
              return (
                <li key={entry.category}>
                  <p className="mb-2 text-[15px] text-navy">
                    {t(`market.category.${entry.category}`)} <span className="font-medium" style={{ color: mixColours[index] === NAVY ? '#334155' : mixColours[index] }}>{Math.round(share * 100)}%</span>
                  </p>
                  <SegmentBar share={share} color={mixColours[index]} />
                </li>
              )
            })}
          </ul>
        </Card>
      </div>

      <Funnel rows={rows} previous={before} month={month} areas={panel.areas} />
    </div>
  )
}

function Empty() {
  const { t } = useTranslation()
  return <p className="py-10 text-center text-[13.5px] text-muted">{t('staff.market.empty')}</p>
}

// ---------------------------------------------------------------- funnel (M4)

function Funnel({ rows, previous, month, areas }: { rows: PanelRow[]; previous: PanelRow[]; month: (key: string) => string; areas: Record<string, string> }) {
  const { t } = useTranslation()
  const activity = byKind(rows, 'ACTIVITY')
  const stages = counts(activity, 'cohort_stages')
  const before = counts(previous, 'cohort_stages')
  const steps = STAGES.map((stage, index) => ({ label: t(`staff.market.funnel.stages.${stage}`), value: stages[stage] ?? 0, colour: [NAVY, '#334155', '#64748b', GOLD, '#e5b972'][index] }))
  const overall = stages.NEW ? (stages.WON ?? 0) / stages.NEW : null
  const overallBefore = before.NEW ? (before.WON ?? 0) / before.NEW : null
  const firstDays = sum(activity, 'first_enquiry_count') ? sum(activity, 'first_enquiry_days_sum') / sum(activity, 'first_enquiry_count') : null
  const saleDays = sum(activity, 'sale_count') ? sum(activity, 'sale_days_sum') / sum(activity, 'sale_count') : null
  const drops = steps.slice(1).map((step, index) => ({ from: steps[index], to: step, lost: steps[index].value - step.value }))
  const biggest = drops.reduce<(typeof drops)[number] | null>((best, drop) => (!best || drop.lost > best.lost ? drop : best), null)

  // Per month: enquiries (NEW) and each step rate, for the sparklines and trend.
  const months = new Map<string, Record<string, number>>()
  for (const row of activity) {
    const key = monthKey(row.day)
    const entry = months.get(key) ?? {}
    for (const [stage, value] of Object.entries(row.metrics.cohort_stages ?? {})) entry[stage] = (entry[stage] ?? 0) + value
    entry.enquiry_events = (entry.enquiry_events ?? 0) + (row.metrics.enquiry_events ?? 0)
    entry.searches = (entry.searches ?? 0) + (row.metrics.searches ?? 0)
    months.set(key, entry)
  }
  const series = [...months.entries()].sort(([a], [b]) => a.localeCompare(b))
  const rate = (from: string, to: string) => series.map(([, entry]) => (entry[from] ? (entry[to] ?? 0) / entry[from] : 0))
  const kpis = [
    { key: 'conversion', value: overall === null ? '-' : `${(overall * 100).toFixed(1)}%`, change: overall !== null && overallBefore ? percentChange(overall, overallBefore) : null, line: rate('NEW', 'WON'), colour: NAVY },
    { key: 'won', value: String(stages.WON ?? 0), change: percentChange(stages.WON ?? 0, before.WON ?? 0), line: series.map(([, entry]) => entry.WON ?? 0), colour: GOLD },
    { key: 'enquiries', value: (stages.NEW ?? 0).toLocaleString(), change: percentChange(stages.NEW ?? 0, before.NEW ?? 0), line: series.map(([, entry]) => entry.NEW ?? 0), colour: NAVY },
    { key: 'firstEnquiry', value: firstDays === null ? '-' : t('staff.market.funnel.days', { value: firstDays.toFixed(1) }), change: null, line: series.map(([, entry]) => entry.searches ?? 0), colour: GOLD },
    { key: 'sale', value: saleDays === null ? '-' : t('staff.market.funnel.days', { value: saleDays.toFixed(0) }), change: null, line: series.map(([, entry]) => entry.WON ?? 0), colour: '#64748b' },
  ]
  const pairs = [['NEW', 'CONTACTED'], ['CONTACTED', 'VIEWING'], ['VIEWING', 'CLOSING'], ['CLOSING', 'WON'], ['NEW', 'WON']] as const

  const regionDemand = byRegion(activity, (row) => (row.metrics.enquiry_events ?? 0) as number)
  const bestRegion = Object.entries(regionDemand).sort(([, a], [, b]) => b - a)[0]
  const bestSource = sources(rows)[0]
  const ranges = Object.entries(counts(activity, 'demand_price_ranges')).sort(([, a], [, b]) => b - a).slice(0, 5)
  const rangeTotal = ranges.reduce((total, [, value]) => total + value, 0)

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-[24px] font-semibold text-navy">{t('staff.market.funnel.title')}</h2>
        <p className="text-[14px] text-muted">{t('staff.market.funnel.subtitle')}</p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {kpis.map((kpi) => (
          <li key={kpi.key} className="rounded-xl border border-mist bg-white px-4 pt-3 pb-1">
            <p className="text-[15px] font-medium text-navy">{t(`staff.market.funnel.kpis.${kpi.key}`)}</p>
            <p className="text-[22px] font-semibold text-navy tabular-nums">{kpi.value}</p>
            <Change value={kpi.change} />
            <div className="mt-1 h-[38px]"><Sparkline values={kpi.line.length ? kpi.line : [0, 0]} color={kpi.colour} height={38} /></div>
          </li>
        ))}
      </ul>

      <div className="grid overflow-hidden rounded-xl border border-mist bg-white xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="border-mist px-5 py-4 xl:border-r">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-[17px] font-semibold text-navy">{t('staff.market.funnel.main')}</h3>
            <span className="rounded-md bg-gold/15 px-2 py-0.5 text-[11.5px] font-medium text-[#7a5410]">{t('staff.market.funnel.primary')}</span>
          </div>
          <p className="text-[12.5px] text-muted">{t('staff.market.funnel.steps', { count: steps.length })}</p>
          <div className="mt-4 overflow-x-auto">
            <div className="min-w-[620px]"><StepFunnel steps={steps} /></div>
          </div>
          <dl className="mt-4 grid gap-3 rounded-xl border border-mist px-4 py-3 text-[13px] sm:grid-cols-4">
            <div>
              <dt className="text-navy-soft">{t('staff.market.funnel.overall')}</dt>
              <dd className="text-[18px] font-semibold text-navy">{overall === null ? '-' : `${(overall * 100).toFixed(1)}%`}</dd>
            </div>
            <div>
              <dt className="text-navy-soft">{t('staff.market.funnel.dropoffs')}</dt>
              <dd className="text-[18px] font-semibold text-navy">{((stages.NEW ?? 0) - (stages.WON ?? 0)).toLocaleString()}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-navy-soft">{t('staff.market.funnel.biggest')}</dt>
              <dd className="font-medium text-danger">{biggest && biggest.lost > 0 ? `${biggest.from.label} → ${biggest.to.label} (${biggest.lost})` : '-'}</dd>
            </div>
          </dl>
        </div>
        <div className="px-5 py-4">
          <h3 className="text-[16px] font-semibold text-navy">{t('staff.market.funnel.performance')}</h3>
          <div className="mt-3 grid grid-cols-[1fr_auto_70px] gap-x-3 text-[10.5px] font-medium tracking-wide text-muted uppercase">
            <span>{t('staff.market.funnel.step')}</span>
            <span>{t('staff.market.funnel.rate')}</span>
            <span>{t('staff.market.funnel.trend')}</span>
          </div>
          <ul className="mt-2 space-y-2.5">
            {pairs.map(([from, to]) => {
              const value = stages[from] ? (stages[to] ?? 0) / stages[from] : null
              const line = rate(from, to)
              const rising = line.length > 1 && line[line.length - 1] >= line[0]
              return (
                <li key={`${from}-${to}`} className="grid grid-cols-[1fr_auto_70px] items-center gap-x-3 text-[12.5px] text-navy">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="grid size-6 shrink-0 place-items-center rounded-md bg-paper text-navy-soft"><ArrowRightIcon className="size-3.5" /></span>
                    <span className="truncate">{t(`staff.market.funnel.stages.${from}`)} → {t(`staff.market.funnel.stages.${to}`)}</span>
                  </span>
                  <span className="tabular-nums">{value === null ? '-' : `${(value * 100).toFixed(1)}%`}</span>
                  <span className="h-6"><Sparkline values={line.length ? line : [0, 0]} color={rising ? '#15803d' : '#dc2626'} height={24} fill={false} /></span>
                </li>
              )
            })}
          </ul>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="px-5 py-4">
          <h3 className="text-[16px] font-semibold text-navy">{t('staff.market.funnel.trendTitle')}</h3>
          {series.length > 1 ? (
            <>
              <TwoLines labels={series.map(([key]) => month(key))} first={series.map(([, entry]) => entry.enquiry_events ?? 0)} second={series.map(([, entry]) => (entry.VIEWING ?? 0) * 10)} colours={[NAVY, GOLD]} />
              <p className="mt-1 flex gap-4 text-[12px] text-navy-soft">
                <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-full bg-navy" />{t('staff.market.demand.enquiries')}</span>
                <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-full bg-gold" />{t('staff.market.funnel.viewingsScaled')}</span>
              </p>
            </>
          ) : (
            <Empty />
          )}
        </Card>
        <Card className="border-gold/25 bg-[#fdf8ee] px-5 py-4">
          <h3 className="flex items-center gap-2 text-[16px] font-semibold text-navy">{t('staff.market.insights.title')}</h3>
          <ul className="mt-3 space-y-2.5">
            {[
              { icon: AlertIcon, tone: 'text-danger', title: t('staff.market.insights.drop'), body: biggest && biggest.lost > 0 ? t('staff.market.insights.dropBody', { from: biggest.from.label, to: biggest.to.label, count: biggest.lost }) : t('staff.market.insights.none') },
              { icon: MapPinIcon, tone: 'text-[#9a6c12]', title: t('staff.market.insights.area'), body: bestRegion ? t('staff.market.insights.areaBody', { area: areas[bestRegion[0]] ?? '-', count: bestRegion[1] }) : t('staff.market.insights.none') },
              { icon: SearchIcon, tone: 'text-navy', title: t('staff.market.insights.source'), body: bestSource ? t('staff.market.insights.sourceBody', { tag: bestSource.tag, count: bestSource.views + bestSource.searches }) : t('staff.market.insights.none') },
            ].map(({ icon: Icon, tone, title, body }) => (
              <li key={title} className="rounded-xl bg-white/80 px-3 py-2.5">
                <p className="flex items-center gap-2 text-[13.5px] font-medium text-navy"><Icon className={`size-4 ${tone}`} />{title}</p>
                <p className="mt-0.5 text-[12.5px] text-navy-soft">{body}</p>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="px-5 py-4">
          <h3 className="text-[16px] font-semibold text-navy">{t('staff.market.ranges.title')}</h3>
          <ul className="mt-4 space-y-3">
            {ranges.map(([range, value]) => (
              <li key={range} className="grid grid-cols-[1fr_64px_44px] items-center gap-3 text-[12.5px] text-navy">
                <span className="leading-snug">{rangeLabel(range, t)}</span>
                <span className="h-1.5 overflow-hidden rounded-full bg-paper"><span className="block h-full rounded-full bg-navy" style={{ width: `${rangeTotal ? (value / rangeTotal) * 100 : 0}%` }} /></span>
                <span className="text-right text-navy-soft tabular-nums">{rangeTotal ? `${((value / rangeTotal) * 100).toFixed(1)}%` : '-'}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[12px] text-muted">{t('staff.market.ranges.based', { count: rangeTotal })}</p>
        </Card>
      </div>
    </section>
  )
}

function rangeLabel(range: string, t: (key: string) => string) {
  const [from, to] = range.split(':')
  if (from === 'ANY' && to === 'ANY') return t('staff.market.ranges.any')
  return `${t(`staff.market.ranges.${from}`)} - ${t(`staff.market.ranges.${to}`)}`
}

// ---------------------------------------------------------------- areas (M3)

function Areas({ panel, month }: { panel: Panel; month: (key: string) => string }) {
  const { t } = useTranslation()
  const [metric, setMetric] = useState<'searches' | 'enquiry_events' | 'won_deals'>('searches')
  const activity = byKind(panel.rows, 'ACTIVITY')
  const values = byRegion(activity, (row) => (row.metrics[metric] as number | undefined) ?? 0)
  const named = Object.entries(values).map(([id, value]) => ({ name: panel.areas[id] ?? id, value })).sort((a, b) => b.value - a.value)
  const max = Math.max(...named.map((area) => area.value), 1)
  const bandOf = useCallback((value: number): 0 | 1 | 2 => (value >= max * 0.66 ? 0 : value >= max * 0.33 ? 1 : 2), [max])
  const searches = byRegion(activity, (row) => row.metrics.searches ?? 0)
  const enquiries = byRegion(activity, (row) => (row.metrics.enquiry_events ?? 0) as number)
  const regionIds = Object.keys(searches).sort((a, b) => (searches[b] ?? 0) - (searches[a] ?? 0)).slice(0, 7)
  const visitors = monthly(panel.rows, ['views', 'enquiry_events'])
  const bands = [0, 1, 2].map((band) => {
    const low = band === 0 ? max * 0.66 : band === 1 ? max * 0.33 : 0
    const high = band === 0 ? max : band === 1 ? max * 0.66 : max * 0.33
    return `${Math.round(low).toLocaleString()} - ${Math.round(high).toLocaleString()}`
  })

  return (
    <div className="space-y-4">
      <div role="radiogroup" aria-label={t('staff.market.areas.metric')} className="flex flex-wrap gap-2">
        {(['searches', 'enquiry_events', 'won_deals'] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={metric === value}
            onClick={() => setMetric(value)}
            className={`h-9 rounded-full px-4 text-[13.5px] ${metric === value ? 'bg-navy font-medium text-white' : 'text-navy hover:bg-white'}`}
          >
            {t(`staff.market.areas.metrics.${value}`)}
          </button>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-4">
          <Card className="px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-[18px] font-medium text-navy">{t('staff.market.areas.demand')}</h2>
              <span className="flex gap-4 text-[12.5px] text-navy-soft">
                <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-gold" />{t('staff.market.demand.searches')}</span>
                <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-navy" />{t('staff.market.demand.enquiries')}</span>
              </span>
            </div>
            <p className="mt-2 text-[12px] text-muted">{t('staff.market.areas.count')}</p>
            {regionIds.length ? <GroupedBars labels={regionIds.map((id) => panel.areas[id] ?? id)} first={regionIds.map((id) => searches[id] ?? 0)} second={regionIds.map((id) => enquiries[id] ?? 0)} colours={[GOLD, NAVY]} /> : <Empty />}
          </Card>
          <Card className="px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-[18px] font-medium text-navy">{t('staff.market.areas.visitors')}</h2>
              <span className="flex gap-4 text-[12.5px] text-navy-soft">
                <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-navy" />{t('staff.market.areas.views')}</span>
                <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-gold" />{t('staff.market.demand.enquiries')}</span>
              </span>
            </div>
            {visitors.length > 1 ? <TwoLines labels={visitors.map((entry) => month(entry.month))} first={visitors.map((entry) => entry.views)} second={visitors.map((entry) => entry.enquiry_events)} colours={[NAVY, GOLD]} /> : <Empty />}
          </Card>
        </div>
        <Card className="px-5 py-4">
          <h2 className="text-[18px] font-medium text-navy">{t('staff.market.areas.map', { metric: t(`staff.market.areas.metrics.${metric}`) })}</h2>
          <div className="mt-4"><AreaMap areas={named} bandOf={bandOf} label={t('staff.market.areas.map', { metric: t(`staff.market.areas.metrics.${metric}`) })} /></div>
          <ul className="mt-4 space-y-1.5 text-[13px] text-navy">
            {bands.map((label, band) => (
              <li key={band} className="flex items-center gap-2.5"><span className="size-3 rounded-full" style={{ backgroundColor: BANDS[band] }} />{label}</li>
            ))}
          </ul>
          <p className="mt-3 flex items-start gap-2 text-[12px] text-muted"><InfoIcon className="mt-0.5 size-3.5 shrink-0" />{t('staff.market.areas.note')}</p>
        </Card>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- sources (M6)

function Sources({ panel, previous, month }: { panel: Panel; previous: Panel | null; month: (key: string) => string }) {
  const { t } = useTranslation()
  const [filter, setFilter] = useState<'all' | 'campaign' | 'other'>('all')
  const all = sources(panel.rows)
  const tagged = all.filter((row) => row.tag)
  const shown = tagged.filter((row) => filter === 'all' || (filter === 'campaign' ? sourceKind(row.tag) !== 'other' : sourceKind(row.tag) === 'other'))
  const [inspect, setInspect] = useState<string | null>(null)
  const current = shown.find((row) => row.tag === inspect) ?? shown[0] ?? null
  const activity = byKind(panel.rows, 'ACTIVITY')
  const totalVisits = sum(activity, 'views') + sum(activity, 'searches')
  const taggedVisits = tagged.reduce((total, row) => total + row.views + row.searches, 0)
  const taggedEnquiries = tagged.reduce((total, row) => total + row.enquiries, 0)
  const before = previous ? sources(previous.rows).filter((row) => row.tag) : []
  const beforeVisits = before.reduce((total, row) => total + row.views + row.searches, 0)
  const beforeEnquiries = before.reduce((total, row) => total + row.enquiries, 0)
  const byMonth = (tags: string[]) => {
    const months = new Map<string, number>()
    for (const row of activity) {
      let value = 0
      for (const tag of tags) value += ((row.metrics.sources_view ?? {})[tag] ?? 0) + ((row.metrics.sources_search ?? {})[tag] ?? 0)
      months.set(monthKey(row.day), (months.get(monthKey(row.day)) ?? 0) + value)
    }
    return [...months.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, value]) => value)
  }
  const visitsLine = byMonth(tagged.map((row) => row.tag))
  const coverageLine = monthly(panel.rows, ['views', 'searches']).map((entry, index) => {
    const total = entry.views + entry.searches
    return total ? (visitsLine[index] ?? 0) / total : 0
  })
  const enquiryLine = (() => {
    const months = new Map<string, number>()
    for (const row of activity) months.set(monthKey(row.day), (months.get(monthKey(row.day)) ?? 0) + Object.values(row.metrics.sources_enquiry ?? {}).reduce((total, value) => total + value, 0))
    return [...months.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, value]) => value)
  })()
  const top = [...tagged].sort((a, b) => b.enquiries - a.enquiries)[0]
  const maxShare = Math.max(...shown.map((row) => row.views + row.searches), 1)
  const detail = current ? tagDetail(panel.rows, current.tag) : null
  const kpis = [
    { key: 'visits', value: taggedVisits.toLocaleString(), change: percentChange(taggedVisits, beforeVisits), line: visitsLine },
    { key: 'enquiries', value: taggedEnquiries.toLocaleString(), change: percentChange(taggedEnquiries, beforeEnquiries), line: enquiryLine },
    { key: 'coverage', value: totalVisits ? `${Math.round((taggedVisits / totalVisits) * 100)}%` : '-', change: null, line: coverageLine },
  ]

  return (
    <div className="space-y-4">
      <div>
        <p className="flex items-center gap-2 text-[12px] font-medium tracking-[0.12em] text-muted uppercase">
          {t('staff.market.sources.kicker')}
          <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-0.5 text-[11px] tracking-normal text-success normal-case"><span className="size-1.5 rounded-full bg-success" />{t('staff.market.sources.live', { count: tagged.length })}</span>
        </p>
        <h2 className="mt-1 text-[30px] leading-tight font-semibold text-navy">{t('staff.market.sources.title')}</h2>
        <p className="text-[13.5px] text-muted">{t('staff.market.sources.subtitle', { count: tagged.length, share: totalVisits ? Math.round((taggedVisits / totalVisits) * 100) : 0 })}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <Card key={kpi.key} className="px-5 py-4">
            <p className="text-[14px] font-medium text-navy">{t(`staff.market.sources.kpis.${kpi.key}`)}</p>
            <div className="mt-2 flex items-end justify-between gap-3">
              <div>
                <p className="text-[28px] leading-none font-semibold text-navy tabular-nums">{kpi.value}</p>
                <p className="mt-2"><Change value={kpi.change} /></p>
              </div>
              <div className="h-[48px] w-[110px]"><Sparkline values={kpi.line.length ? kpi.line : [0, 0]} color="#15803d" height={48} fill={false} /></div>
            </div>
          </Card>
        ))}
        <section className="rounded-[20px] border border-gold/40 bg-[#fdf8ee] px-5 py-4">
          <p className="flex items-center gap-1.5 text-[12px] font-semibold tracking-[0.1em] text-[#7a5410] uppercase">★ {t('staff.market.sources.top')}</p>
          {top ? (
            <>
              <p className="mt-2 text-[13.5px] text-navy"><span className="font-mono text-[#7a5410]">{top.tag}</span> {t('staff.market.sources.topBody', { count: top.enquiries })}</p>
              <button type="button" onClick={() => setInspect(top.tag)} className="mt-3 inline-flex h-9 items-center gap-1.5 rounded-lg bg-navy px-3.5 text-[13px] font-semibold text-white">{t('staff.market.sources.inspect')} <ArrowRightIcon className="size-4" /></button>
            </>
          ) : (
            <p className="mt-2 text-[13px] text-muted">{t('staff.market.empty')}</p>
          )}
        </section>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <div>
              <h3 className="text-[17px] font-semibold text-navy">{t('staff.market.sources.all')}</h3>
              <p className="text-[12.5px] text-muted">{t('staff.market.sources.hint')}</p>
            </div>
            <div role="radiogroup" className="flex rounded-lg bg-paper p-1">
              {(['all', 'campaign', 'other'] as const).map((value) => (
                <button key={value} type="button" role="radio" aria-checked={filter === value} onClick={() => setFilter(value)} className={`h-8 rounded-md px-3.5 text-[13px] ${filter === value ? 'bg-white font-medium text-navy shadow-sm' : 'text-navy-soft'}`}>
                  {t(`staff.market.sources.filters.${value}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left">
              <thead className="border-y border-mist text-[11px] font-medium tracking-[0.08em] text-muted uppercase">
                <tr>
                  <th scope="col" className="px-5 py-3 font-medium">{t('staff.market.sources.columns.tag')}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t('staff.market.sources.columns.kind')}</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">{t('staff.market.sources.columns.visits')}</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">{t('staff.market.sources.columns.enquiries')}</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">{t('staff.market.sources.columns.won')}</th>
                  <th scope="col" className="px-5 py-3 font-medium">{t('staff.market.sources.columns.share')}</th>
                </tr>
              </thead>
              <tbody>
                {shown.length === 0 && (
                  <tr><td colSpan={6}><Empty /></td></tr>
                )}
                {shown.map((row) => {
                  const on = current?.tag === row.tag
                  const visits = row.views + row.searches
                  return (
                    <tr key={row.tag} onClick={() => setInspect(row.tag)} className={`cursor-pointer border-b border-mist/70 text-[13.5px] text-navy last:border-b-0 ${on ? 'bg-gold/[0.07] shadow-[inset_3px_0_0_#c89128]' : 'hover:bg-paper/60'}`}>
                      <td className="px-5 py-3">
                        <button type="button" onClick={() => setInspect(row.tag)} className="flex items-center gap-3 text-left">
                          <span className="grid size-8 place-items-center rounded-lg bg-navy text-[11px] font-semibold text-gold-light uppercase">{row.tag.slice(0, 2)}</span>
                          <span>
                            <span className="block font-mono text-[13px]">{row.tag}</span>
                            <span className="flex items-center gap-1 text-[11.5px] text-success"><span className="size-1.5 rounded-full bg-success" />{t('staff.market.sources.seen', { count: visits })}</span>
                          </span>
                        </button>
                      </td>
                      <td className="px-3 py-3 text-navy-soft">{t(`staff.market.sources.kinds.${sourceKind(row.tag)}`)}</td>
                      <td className="px-3 py-3 text-right font-semibold tabular-nums">{visits.toLocaleString()}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{row.enquiries.toLocaleString()}</td>
                      <td className="px-3 py-3 text-right text-success tabular-nums">{row.won.toLocaleString()}</td>
                      <td className="px-5 py-3">
                        <span className="flex items-center gap-2">
                          <span className="h-1.5 w-20 overflow-hidden rounded-full bg-paper"><span className="block h-full rounded-full bg-navy" style={{ width: `${(visits / maxShare) * 100}%` }} /></span>
                          <span className="text-[12.5px] text-navy-soft tabular-nums">{visits ? `${((row.enquiries / visits) * 100).toFixed(1)}%` : '-'}</span>
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {current && detail && (
          <div className="space-y-4">
            <section className="rounded-[20px] bg-navy px-5 py-4 text-white">
              <div className="flex items-center justify-between">
                <span className="rounded-md bg-white/10 px-2 py-0.5 text-[11px] font-semibold tracking-[0.12em] text-gold-light uppercase">{t('staff.market.sources.inspecting')}</span>
                <span className="rounded-full bg-success/25 px-2.5 py-0.5 text-[11.5px] text-[#86efac]">{t(`staff.market.sources.kinds.${sourceKind(current.tag)}`)}</span>
              </div>
              <p className="mt-3 font-mono text-[16px]">{current.tag}</p>
              <p className="text-[12.5px] text-white/60">{t('staff.market.sources.since', { month: detail.months[0] ? month(detail.months[0].month) : '-' })}</p>
              <dl className="mt-3 flex gap-6">
                <div><dd className="text-[24px] font-semibold tabular-nums">{(current.views + current.searches).toLocaleString()}</dd><dt className="text-[12px] text-white/60">{t('staff.market.sources.columns.visits')}</dt></div>
                <div><dd className="text-[24px] font-semibold tabular-nums">{current.views + current.searches ? `${((current.enquiries / (current.views + current.searches)) * 100).toFixed(1)}%` : '-'}</dd><dt className="text-[12px] text-white/60">{t('staff.market.sources.rate')}</dt></div>
                <div><dd className="text-[24px] font-semibold text-gold-light tabular-nums">{current.won}</dd><dt className="text-[12px] text-white/60">{t('staff.market.sources.columns.won')}</dt></div>
              </dl>
              <div className="mt-3 h-[70px]"><Sparkline values={detail.months.length ? detail.months.map((entry) => entry.value) : [0, 0]} color={GOLD} height={70} /></div>
            </section>
            <Card className="px-5 py-4">
              <h3 className="text-[11.5px] font-semibold tracking-[0.1em] text-muted uppercase">{t('staff.market.sources.topAreas', { tag: current.tag })}</h3>
              <ul className="mt-3 space-y-2">
                {detail.regions.slice(0, 4).map(([id, value]) => (
                  <li key={id} className="flex items-center justify-between text-[13.5px]">
                    <span className="rounded-md bg-paper px-2 py-0.5 font-mono text-[12.5px] text-navy">{panel.areas[id] ?? id}</span>
                    <span className="font-semibold text-navy tabular-nums">{value.toLocaleString()}</span>
                  </li>
                ))}
              </ul>
              <h3 className="mt-5 text-[11.5px] font-semibold tracking-[0.1em] text-muted uppercase">{t('staff.market.sources.funnel')}</h3>
              <ul className="mt-3 space-y-2">
                {[
                  { label: t('staff.market.sources.columns.visits'), value: current.views + current.searches, colour: NAVY },
                  { label: t('staff.market.sources.columns.enquiries'), value: current.enquiries, colour: '#475569' },
                  { label: t('staff.market.sources.columns.won'), value: current.won, colour: GOLD },
                ].map((step) => (
                  <li key={step.label} className="flex items-center gap-3">
                    <span className="flex h-8 items-center rounded-md px-3 text-[12.5px] font-medium text-white" style={{ width: `${Math.max(((step.value || 0) / Math.max(current.views + current.searches, 1)) * 100, 22)}%`, backgroundColor: step.colour }}>
                      {step.label}
                    </span>
                    <span className="font-mono text-[12.5px] text-navy tabular-nums">{step.value.toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        )}
      </div>
      <p className="flex items-center gap-2 text-[12px] text-muted"><ClockIcon className="size-3.5" />{t('staff.market.sources.note')}</p>
    </div>
  )
}
