import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import heroImage from '../../../assets/photos/dar-aerial-1200.webp'
import { Alert } from '../../../components/Alert'
import {
  AlertIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClockIcon,
  FilterIcon,
  ImageIcon,
  ResetIcon,
  SearchIcon,
  SortIcon,
} from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { formatRelative, formatShortDate } from '../../../lib/format'
import { staffApi, type CheckSummary, type LocationCheckRow } from '../../../lib/staffApi'

type Tab = 'waiting' | 'decided'
type Category = 'ALL' | 'LAND' | 'HOUSE' | 'COMMERCIAL'

// VER-02 queue, after C2 and C1: a photo band with the page name, a category
// switch and four count tiles laid over it; the late checks as a strip of
// cards; then one table (C1's rows: photo, place and date, chips, status)
// beside this month's results.
export function LocationChecksPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  useDocumentTitle(t('staff.locationChecks.title'))
  const [tab, setTab] = useState<Tab>('waiting')
  const [category, setCategory] = useState<Category>('ALL')
  const [query, setQuery] = useState('')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [newestFirst, setNewestFirst] = useState(false)
  const [summary, setSummary] = useState<CheckSummary | null>(null)
  const [waiting, setWaiting] = useState<LocationCheckRow[] | null>(null)
  const [decided, setDecided] = useState<LocationCheckRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    staffApi.checkSummary().then(setSummary, () => setSummary(null))
    staffApi.checks('waiting').then((page) => setWaiting(page.results), (caught) => setError(errorMessage(t, caught)))
    staffApi.checks('decided').then((page) => setDecided(page.results), () => setDecided([]))
  }, [t])

  useEffect(() => {
    load()
  }, [load])

  function refresh() {
    setError(null)
    load()
  }

  const rows = tab === 'waiting' ? waiting : decided
  const shown = useMemo(() => {
    if (!rows) return null
    const needle = query.trim().toLowerCase()
    const kept = rows.filter(
      (row) =>
        (category === 'ALL' || row.category === category) &&
        (!flaggedOnly || row.duplicate_count > 0) &&
        (!needle || `${row.property_id} ${row.area} ${row.lister_name}`.toLowerCase().includes(needle)),
    )
    return newestFirst ? [...kept].reverse() : kept
  }, [rows, category, flaggedOnly, query, newestFirst])
  const late = (waiting ?? []).filter((row) => row.late)

  const tiles = [
    { key: 'waiting', value: summary?.waiting, tone: 'text-navy' },
    { key: 'late', value: summary?.late, tone: 'text-danger' },
    { key: 'passed', value: summary?.passed_this_month, tone: 'text-navy' },
    { key: 'failed', value: summary?.failed_this_month, tone: 'text-navy' },
  ] as const

  return (
    <div className="space-y-5">
      {/* C2: the photo band, with the tiles over its lower edge. */}
      <section className="relative isolate overflow-hidden rounded-2xl border border-mist/70">
        <img src={heroImage} alt="" className="absolute inset-0 -z-10 size-full object-cover" />
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-[#f8f8f9] via-[#f8f8f9]/90 to-[#f8f8f9]/35" />
        <div className="px-5 pt-6 pb-5 sm:px-7 sm:pt-7">
          <h1 className="text-[26px] leading-tight font-semibold text-navy sm:text-[30px]">{t('staff.locationChecks.title')}</h1>
          <p className="mt-1.5 text-[14px] text-navy-soft">{t('staff.locationChecks.subtitle')}</p>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <div role="radiogroup" aria-label={t('staff.locationChecks.columns.details')} className="flex max-w-full overflow-x-auto rounded-xl bg-white/80 p-1 shadow-[0_1px_2px_rgba(15,23,42,0.06)] ring-1 ring-mist/70 backdrop-blur [scrollbar-width:none]">
              {(['ALL', 'LAND', 'HOUSE', 'COMMERCIAL'] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={category === value}
                  onClick={() => setCategory(value)}
                  className={`h-9 rounded-lg px-3.5 text-[13.5px] whitespace-nowrap transition-colors sm:px-5 ${
                    category === value ? 'bg-white font-semibold text-navy shadow-[0_1px_3px_rgba(15,23,42,0.12)]' : 'text-navy-soft hover:text-navy'
                  }`}
                >
                  {value === 'ALL' ? t('staff.outbox.kinds.all') : t(`market.category.${value}`)}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={refresh}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-navy px-4 text-[13.5px] font-semibold text-white hover:bg-navy-soft"
            >
              <ResetIcon className="size-4" />
              {t('staff.locationChecks.refresh')}
            </button>
          </div>

          <ul className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {tiles.map((tile) => (
              <li key={tile.key} className="rounded-xl bg-white/95 px-4 py-3.5 shadow-[0_2px_10px_rgba(15,23,42,0.08)] ring-1 ring-mist/60 backdrop-blur">
                <p className="text-[13.5px] font-medium text-navy">{t(`staff.locationChecks.tiles.${tile.key}`)}</p>
                <p className="mt-1 flex items-baseline gap-2">
                  <span className={`text-[30px] leading-none font-semibold tabular-nums ${tile.tone}`}>{tile.value ?? '-'}</span>
                  <span className="text-[12px] text-muted">{t(`staff.locationChecks.tiles.${tile.key}Note`)}</span>
                </p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {error && <Alert tone="error">{error}</Alert>}

      {late.length > 0 && <LateStrip rows={late} onOpen={(id) => navigate(`/staff/checks/${id}`)} />}

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_260px]">
        <section className="overflow-hidden rounded-xl border border-mist/80 bg-white">
          {/* C1: tabs with counts, then search with Filter and Sort. */}
          <div role="tablist" aria-label={t('staff.locationChecks.title')} className="flex gap-6 border-b border-mist px-5">
            {(['waiting', 'decided'] as const).map((value) => {
              const count = value === 'waiting' ? waiting?.length : decided?.length
              const on = tab === value
              return (
                <button
                  key={value}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  onClick={() => setTab(value)}
                  className={`relative inline-flex h-14 items-center gap-2 text-[15px] ${on ? 'font-medium text-[#9a6c12]' : 'text-navy-soft hover:text-navy'}`}
                >
                  {t(`staff.locationChecks.tabs.${value}`)}
                  <span className="grid h-5 min-w-5 place-items-center rounded-full bg-paper px-1.5 text-[11.5px] text-navy-soft tabular-nums">{count ?? '-'}</span>
                  {on && <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-gold" />}
                </button>
              )
            })}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <label className="relative block w-full sm:w-80">
              <span className="sr-only">{t('staff.locationChecks.search')}</span>
              <SearchIcon className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t('staff.locationChecks.search')}
                className="h-10 w-full rounded-lg border border-mist bg-white pr-3 pl-10 text-[13.5px] text-navy outline-none placeholder:text-muted/80 focus:border-gold focus:ring-2 focus:ring-gold/20"
              />
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                aria-pressed={flaggedOnly}
                onClick={() => setFlaggedOnly((value) => !value)}
                className={`inline-flex h-10 items-center gap-2 rounded-lg border px-3.5 text-[13.5px] ${flaggedOnly ? 'border-gold bg-gold/10 text-navy' : 'border-mist text-navy hover:border-navy/30'}`}
              >
                <FilterIcon className="size-4" />
                {t('staff.locationChecks.columns.flags')}
              </button>
              <button
                type="button"
                aria-pressed={newestFirst}
                onClick={() => setNewestFirst((value) => !value)}
                className="inline-flex h-10 items-center gap-2 rounded-lg border border-mist px-3.5 text-[13.5px] text-navy hover:border-navy/30"
              >
                <SortIcon className="size-4" />
                {newestFirst ? t('market.sort.NEWEST') : t('staff.locationChecks.tiles.waitingNote')}
              </button>
            </div>
          </div>

          <CheckTable rows={shown} tab={tab} language={i18n.language} onOpen={(id) => navigate(`/staff/checks/${id}`)} empty={rows && rows.length > 0 ? t('staff.locationChecks.noMatch') : t(tab === 'waiting' ? 'staff.locationChecks.emptyWaiting' : 'staff.locationChecks.emptyDecided')} />
        </section>

        <ResultsCard summary={summary} />
      </div>
    </div>
  )
}

// C2's "Urgent attention": one card per late check, four at a time.
function LateStrip({ rows, onOpen }: { rows: LocationCheckRow[]; onOpen: (id: string) => void }) {
  const { t } = useTranslation()
  const [now] = useState(() => Date.now())
  const track = useRef<HTMLUListElement>(null)
  const scroll = (direction: 1 | -1) => track.current?.scrollBy({ left: direction * track.current.clientWidth, behavior: 'smooth' })
  return (
    <section className="rounded-xl border border-mist/80 bg-white/95 px-4 py-3.5 shadow-[0_2px_10px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold text-navy">
          {t('staff.locationChecks.lateStrip')}
          <span className="grid h-5 min-w-5 place-items-center rounded-full bg-paper px-1.5 text-[11.5px] font-normal text-navy-soft">{rows.length}</span>
        </h2>
        <div className="flex gap-1">
          <button type="button" onClick={() => scroll(-1)} aria-label={t('staff.locationChecks.previous')} className="grid size-8 place-items-center rounded-full text-navy hover:bg-paper">
            <ChevronLeftIcon className="size-4" />
          </button>
          <button type="button" onClick={() => scroll(1)} aria-label={t('staff.locationChecks.next')} className="grid size-8 place-items-center rounded-full text-navy hover:bg-paper">
            <ChevronRightIcon className="size-4" />
          </button>
        </div>
      </div>
      <ul ref={track} className="mt-3 flex snap-x gap-3 overflow-x-auto pb-1 [scrollbar-width:none]">
        {rows.map((row) => (
          <li key={row.id} className="w-[260px] shrink-0 snap-start sm:w-[calc((100%-36px)/4)] sm:min-w-[230px]">
            <button
              type="button"
              onClick={() => onOpen(row.id)}
              className="flex w-full items-center gap-3 rounded-lg border border-mist px-3 py-2.5 text-left transition-colors hover:border-gold/60 hover:bg-paper/50"
            >
              <span className="relative grid size-11 shrink-0 place-items-center overflow-hidden rounded-md bg-paper">
                {row.cover_url ? <img src={row.cover_url} alt="" className="size-full object-cover" /> : <ImageIcon className="size-4 text-muted" />}
                <span title={t('staff.locationChecks.statuses.LATE')} className="absolute right-0.5 bottom-0.5 grid size-4 place-items-center rounded bg-danger text-white">
                  <ClockIcon className="size-2.5" />
                </span>
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-[14px] font-semibold text-navy">{t('staff.locationChecks.waitedDays', { count: Math.max(1, Math.round((now - new Date(row.submitted_at).getTime()) / 86_400_000)) })}</span>
                  <span className="shrink-0 text-[11px] text-muted tabular-nums">{row.property_id}</span>
                </span>
                <span className="block truncate text-[12.5px] text-navy-soft">{row.area.split(',').slice(0, 2).join(',')}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

const STATUS_CHIP: Record<string, string> = {
  PENDING: 'bg-[#eef2f8] text-navy',
  LATE: 'bg-danger-soft text-danger',
  APPROVED: 'bg-success-soft text-success',
  REJECTED: 'bg-gold/15 text-[#7a5410]',
  EXPIRED: 'bg-mist/70 text-muted',
  REVOKED: 'bg-mist/70 text-muted',
}

function CheckTable({ rows, tab, language, onOpen, empty }: { rows: LocationCheckRow[] | null; tab: Tab; language: string; onOpen: (id: string) => void; empty: string }) {
  const { t } = useTranslation()
  const header = 'px-5 py-3 text-left text-[13px] font-normal text-navy-soft'
  return (
    <table className="w-full table-fixed text-left max-md:block">
      <caption className="sr-only">{t(`staff.locationChecks.tabs.${tab}`)}</caption>
      <thead className="border-y border-mist bg-paper/60 max-md:sr-only">
        <tr>
          <th scope="col" className={`${header} w-[36%]`}>
            <span className="inline-flex items-center gap-1.5">{t('staff.locationChecks.columns.property')}<SortIcon className="size-3.5 text-muted" /></span>
          </th>
          <th scope="col" className={`${header} w-[22%]`}>{t('staff.locationChecks.columns.details')}</th>
          <th scope="col" className={`${header} w-[24%]`}>
            <span className="inline-flex items-center gap-1.5">{t('staff.locationChecks.columns.status')}<SortIcon className="size-3.5 text-muted" /></span>
          </th>
          <th scope="col" className={`${header} w-[18%]`}>{t('staff.locationChecks.columns.flags')}</th>
        </tr>
      </thead>
      <tbody className="max-md:block">
        {rows === null &&
          [0, 1, 2, 3].map((index) => (
            <tr key={index} className="border-b border-mist/70 max-md:block">
              <td colSpan={4} className="px-5 py-3.5 max-md:block">
                <div className="h-12 animate-pulse rounded-lg bg-paper" />
              </td>
            </tr>
          ))}
        {rows !== null && rows.length === 0 && (
          <tr className="max-md:block">
            <td colSpan={4} className="px-5 py-14 text-center text-[14px] text-muted max-md:block">{empty}</td>
          </tr>
        )}
        {rows?.map((row) => {
          const status = row.status === 'PENDING' && row.late ? 'LATE' : row.status
          const when = tab === 'waiting' ? row.submitted_at : (row.reviewed_at ?? row.submitted_at)
          const [place, ...rest] = row.area.split(', ')
          return (
            <tr
              key={row.id}
              onClick={() => onOpen(row.id)}
              className="cursor-pointer border-b border-mist/70 transition-colors last:border-b-0 hover:bg-paper/60 max-md:grid max-md:grid-cols-[minmax(0,1fr)_auto] max-md:gap-x-3 max-md:gap-y-2 max-md:px-4 max-md:py-3.5"
            >
              <td className="px-5 py-3.5 max-md:col-span-2 max-md:p-0">
                <button type="button" onClick={() => onOpen(row.id)} className="flex w-full items-center gap-4 text-left">
                  <span className="grid h-[50px] w-[78px] shrink-0 place-items-center overflow-hidden rounded-lg bg-paper">
                    {row.cover_url ? <img src={row.cover_url} alt="" className="size-full object-cover" loading="lazy" /> : <ImageIcon className="size-5 text-muted" />}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[15px] text-navy">{[place, rest[0]].filter(Boolean).join(', ')}</span>
                    <span className="block truncate text-[13px] text-navy-soft tabular-nums">
                      {row.property_id} · {formatShortDate(when, language)}
                    </span>
                  </span>
                </button>
              </td>
              <td className="px-5 py-3.5 max-md:p-0 max-md:pl-[94px]">
                <span className="flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-[#f1f1f3] px-2.5 py-1 text-[12.5px] whitespace-nowrap text-navy">{t(`market.category.${row.category}`)}</span>
                  <span className="rounded-full bg-[#f1f1f3] px-2.5 py-1 text-[12.5px] whitespace-nowrap text-navy">{t(`market.titleType.${row.title_type}`)}</span>
                </span>
              </td>
              <td className="px-5 py-3.5 max-md:row-start-3 max-md:p-0 max-md:pl-[94px]">
                <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-navy-soft">
                  <span className={`rounded-md px-2 py-0.5 text-[12.5px] font-medium ${STATUS_CHIP[status]}`}>{t(`staff.locationChecks.statuses.${status}`)}</span>
                  <span aria-hidden="true" className="text-muted max-md:hidden">·</span>
                  <span className="inline-flex items-center gap-1.5 whitespace-nowrap"><ClockIcon className="size-3.5 text-muted" />{formatRelative(when, language)}</span>
                </span>
              </td>
              <td className="px-5 py-3.5 text-[13px] max-md:row-start-3 max-md:self-center max-md:p-0">
                {row.duplicate_count > 0 ? (
                  <span className="inline-flex items-center gap-1.5 font-medium text-[#9a6c12]">
                    <AlertIcon className="size-3.5" />
                    {t('staff.locationChecks.duplicate', { count: row.duplicate_count })}
                  </span>
                ) : (
                  <span className="text-navy-soft">{t('staff.locationChecks.allClear')}</span>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// C2's side card: one ring and a short legend with counts.
function ResultsCard({ summary }: { summary: CheckSummary | null }) {
  const { t } = useTranslation()
  const passed = summary?.passed_this_month ?? 0
  const failed = summary?.failed_this_month ?? 0
  const waiting = summary?.waiting ?? 0
  const total = passed + failed + waiting
  const decided = passed + failed
  const rate = decided ? Math.round((passed / decided) * 100) : 0
  const parts = [
    { key: 'passed', value: passed, color: '#0f172a' },
    { key: 'failed', value: failed, color: '#c89128' },
    { key: 'waiting', value: waiting, color: '#cbd5e1' },
  ] as const
  const radius = 54
  const circumference = 2 * Math.PI * radius
  let offset = 0
  return (
    <section className="rounded-xl border border-mist/80 bg-white">
      <h2 className="flex items-center justify-center gap-2 border-b border-mist px-4 py-3.5 text-[14px] font-medium text-navy">
        <ClockIcon className="size-4 text-gold" />
        {t('staff.locationChecks.results.title')}
      </h2>
      <div className="px-5 py-5">
        <div className="relative mx-auto size-[168px]">
          <svg viewBox="0 0 140 140" className="size-full -rotate-90" aria-hidden="true">
            <circle cx="70" cy="70" r={radius} fill="none" stroke="#f1f1f3" strokeWidth="22" />
            {total > 0 &&
              parts.map((part) => {
                const length = (part.value / total) * circumference
                const dash = Math.max(length - 2, 0)
                const element = (
                  <circle
                    key={part.key}
                    cx="70"
                    cy="70"
                    r={radius}
                    fill="none"
                    stroke={part.color}
                    strokeWidth="22"
                    strokeDasharray={`${dash} ${circumference - dash}`}
                    strokeDashoffset={-offset}
                  />
                )
                offset += length
                return element
              })}
          </svg>
          <p className="absolute inset-0 grid place-items-center text-center">
            <span>
              <span className="block text-[28px] leading-none font-semibold text-navy tabular-nums">{rate}%</span>
              <span className="mt-1 block text-[11.5px] text-muted">{t('staff.locationChecks.results.rate')}</span>
            </span>
          </p>
        </div>
        <ul className="mt-5 space-y-2.5">
          {parts.map((part) => (
            <li key={part.key} className="flex items-center gap-2 text-[13px]">
              <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: part.color }} />
              <span className="flex-1 font-medium text-navy">{t(`staff.locationChecks.results.${part.key}`)}</span>
              <span className="rounded-md bg-paper px-1.5 text-[12px] text-navy-soft tabular-nums">{part.value}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
