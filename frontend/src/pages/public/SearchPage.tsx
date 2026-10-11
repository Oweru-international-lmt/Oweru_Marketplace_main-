import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import {
  BanknoteIcon,
  CloseIcon,
  FilterIcon,
  HomeIcon,
  MapPinIcon,
  RulerIcon,
  SearchIcon,
  ShieldIcon,
  WhatsAppIcon,
} from '../../components/icons'
import { ResultCard, ResultCardSkeleton } from '../../components/market/ResultCard'
import { VerificationBadge } from '../../components/market/VerificationBadge'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { whatsappLink } from '../../lib/config'
import { formatNumber, formatTsh, formatTshShort } from '../../lib/format'
import { gsap, MOTION_OK, useGSAP } from '../../lib/gsap'
import {
  CATEGORIES,
  LEVELS,
  marketApi,
  SEARCH_KEYS,
  SORTS,
  TITLE_TYPES,
  type Place,
  type SearchPage as Page,
  type SearchParams,
} from '../../lib/marketApi'
import {
  CategoryField,
  FilterPanel,
  Group,
  LevelField,
  LocationFields,
  RangeField,
  TitleTypeField,
  type Change,
  type Places,
} from './search/FilterPanel'
import { FilterPill } from './search/FilterPill'

const PAGE_SIZE = 12

// Only values the API accepts reach it; anything else in the URL is dropped.
function readParams(params: URLSearchParams): SearchParams {
  const result: Record<string, string> = {}
  for (const key of SEARCH_KEYS) {
    const value = params.get(key)?.trim()
    if (value) result[key] = value
  }
  if (result.category && !(CATEGORIES as readonly string[]).includes(result.category)) delete result.category
  if (result.title_type && !(TITLE_TYPES as readonly string[]).includes(result.title_type)) delete result.title_type
  if (result.sort && !(SORTS as readonly string[]).includes(result.sort)) delete result.sort
  if (result.min_verification_level && !['1', '2', '3'].includes(result.min_verification_level)) delete result.min_verification_level
  for (const key of ['min_price', 'max_price', 'min_size', 'max_size', 'page'] as const) {
    if (result[key] && !/^\d+$/.test(result[key])) delete result[key]
  }
  return result as SearchParams
}

type Result = { key: string; page?: Page; failed?: boolean }

// Horizon Realty's visual language on Zoopla's search mechanics: a location
// bar, a row of filter pills, a results bar, and the Horizon grid cards. The
// side column is where the map goes once the API returns approximate pins.
export function SearchPage() {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('search.title'))
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(() => readParams(searchParams), [searchParams])
  const key = JSON.stringify(filters)
  const [result, setResult] = useState<Result | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [sheetOpen, setSheetOpen] = useState(false)
  const places = usePlaces(filters.region, filters.district)

  // `key` is the serialised filters, so it alone decides when to refetch.
  useEffect(() => {
    let cancelled = false
    const params = JSON.parse(key) as SearchParams
    marketApi
      .search({ ...params, page_size: String(PAGE_SIZE) })
      .then((page) => !cancelled && setResult({ key, page }))
      .catch(() => !cancelled && setResult({ key, failed: true }))
    return () => {
      cancelled = true
    }
  }, [key, attempt])

  const current = result?.key === key ? result : null
  const loading = current === null

  // Any filter change goes back to page 1; page changes keep the filters.
  function update(changes: Change) {
    const next = new URLSearchParams()
    const merged: Record<string, string | undefined> = { ...filters, page: undefined, ...changes }
    for (const [name, value] of Object.entries(merged)) if (value) next.set(name, value)
    setSearchParams(next)
  }

  function goToPage(page: number) {
    update({ page: page > 1 ? String(page) : undefined })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const clearAll = () => setSearchParams(filters.sort ? { sort: filters.sort } : {})
  const activeCount = Object.keys(filters).filter((name) => name !== 'sort' && name !== 'page').length

  return (
    <div className="mx-auto max-w-7xl px-4 pt-8 pb-20 sm:px-8 sm:pt-12">
      <SearchHeader />

      {/* Zoopla's search bar, holding the location choice. */}
      <div className="mt-7 hidden items-stretch rounded-lg bg-white p-1.5 shadow-card lg:flex">
        <span className="grid w-12 shrink-0 place-items-center text-gold">
          <MapPinIcon className="size-5" />
        </span>
        <LocationFields filters={filters} places={places} onChange={update} inline />
        <button
          type="button"
          aria-label={t('search.title')}
          onClick={() => document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          className="grid w-14 shrink-0 place-items-center rounded-md bg-navy text-white transition-colors hover:bg-navy-soft"
        >
          <SearchIcon className="size-5" />
        </button>
      </div>

      {/* Results bar: count on the left, sort on the right. */}
      <div id="results" className="mt-7 flex scroll-mt-24 flex-wrap items-center justify-between gap-3">
        <p className="flex items-baseline gap-2 text-navy" aria-live="polite">
          {current?.page ? (
            <>
              <span className="text-2xl font-bold">{formatNumber(current.page.count, i18n.language)}</span>
              <span className="text-sm text-muted">{t('search.results', { count: current.page.count }).replace(String(current.page.count), '').trim()}</span>
            </>
          ) : (
            <span className="text-2xl">&nbsp;</span>
          )}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSheetOpen(true)}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-white px-4 text-[13px] font-semibold text-navy ring-1 ring-mist hover:ring-navy/30 lg:hidden"
          >
            <FilterIcon className="size-4 text-gold" />
            {t('search.filters')}
            {activeCount > 0 && <span className="grid size-5 place-items-center rounded-full bg-gold text-[11px] font-bold text-navy">{activeCount}</span>}
          </button>
          <label className="flex items-center gap-2 text-[13px] text-muted">
            <span className="hidden sm:inline">{t('search.sort')}</span>
            <select
              value={filters.sort ?? 'NEWEST'}
              onChange={(event) => update({ sort: event.target.value === 'NEWEST' ? undefined : event.target.value })}
              className="h-10 cursor-pointer rounded-md border border-mist bg-white px-3 text-[13px] font-semibold text-navy outline-none focus:border-gold focus:ring-4 focus:ring-gold/20"
            >
              {SORTS.map((sort) => (
                <option key={sort} value={sort}>
                  {t(`market.sort.${sort}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {/* Zoopla's filter pills. */}
      <div className="mt-4 hidden flex-wrap items-center gap-2 lg:flex">
        <DesktopPills filters={filters} onChange={update} />
        {activeCount > 0 && (
          <button type="button" onClick={clearAll} className="text-link ml-2 text-[13px]">
            {t('search.clearAll')}
          </button>
        )}
      </div>

      <div className="lg:hidden">
        <ActiveChips filters={filters} places={places} onRemove={update} onClear={clearAll} />
      </div>

      <div className="mt-6 grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section aria-label={t('search.title')} aria-busy={loading} className="min-w-0">
          <Results
            loading={loading}
            current={current}
            hasFilters={activeCount > 0}
            onRetry={() => setAttempt((value) => value + 1)}
            onClear={() => setSearchParams({})}
            onPage={goToPage}
            pageNumber={Number(filters.page ?? 1)}
          />
        </section>
        <SideColumn />
      </div>

      <AnimatePresence>
        {sheetOpen && (
          <FilterSheet count={current?.page?.count ?? null} onClose={() => setSheetOpen(false)}>
            <FilterPanel filters={filters} places={places} onChange={update} />
          </FilterSheet>
        )}
      </AnimatePresence>
    </div>
  )
}

function SearchHeader() {
  const { t } = useTranslation()
  const root = useRef<HTMLElement>(null)

  useGSAP(
    () => {
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap.from('[data-head]', { opacity: 0, y: 14, duration: 0.6, stagger: 0.08, ease: 'power3.out' })
      })
    },
    { scope: root },
  )

  return (
    <header ref={root} className="max-w-2xl">
      <p data-head className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">
        {t('search.kicker')}
      </p>
      <h1 data-head className="mt-3 font-serif text-[32px] leading-[1.15] font-semibold text-balance text-navy sm:text-[40px]">
        {t('search.titleLead')} <span className="text-gold">{t('search.titleAccent')}</span>
      </h1>
    </header>
  )
}

function DesktopPills({ filters, onChange }: { filters: SearchParams; onChange: (change: Change) => void }) {
  const { t, i18n } = useTranslation()
  const short = (value: string) => formatTshShort(value, i18n.language)
  const size = (value: string) => formatNumber(value, i18n.language)

  const priceValue =
    filters.min_price && filters.max_price
      ? t('search.rangeBoth', { min: short(filters.min_price), max: short(filters.max_price) })
      : filters.min_price
        ? t('search.priceFrom', { value: short(filters.min_price) })
        : filters.max_price
          ? t('search.priceTo', { value: short(filters.max_price) })
          : undefined
  const sizeValue =
    filters.min_size && filters.max_size
      ? t('search.rangeBoth', { min: size(filters.min_size), max: size(filters.max_size) })
      : filters.min_size
        ? t('search.sizeFrom', { value: size(filters.min_size) })
        : filters.max_size
          ? t('search.sizeTo', { value: size(filters.max_size) })
          : undefined
  const moreCount = [filters.title_type, filters.min_verification_level].filter(Boolean).length

  return (
    <>
      <FilterPill
        label={t('search.category')}
        icon={HomeIcon}
        value={filters.category ? t(`market.category.${filters.category}`) : undefined}
        onClear={() => onChange({ category: undefined })}
      >
        <CategoryField filters={filters} onChange={onChange} />
      </FilterPill>
      <FilterPill label={t('search.price')} icon={BanknoteIcon} value={priceValue} onClear={() => onChange({ min_price: undefined, max_price: undefined })}>
        <RangeField min={filters.min_price} max={filters.max_price} onCommit={(min, max) => onChange({ min_price: min, max_price: max })} />
      </FilterPill>
      <FilterPill label={t('search.size')} icon={RulerIcon} value={sizeValue} onClear={() => onChange({ min_size: undefined, max_size: undefined })}>
        <RangeField min={filters.min_size} max={filters.max_size} onCommit={(min, max) => onChange({ min_size: min, max_size: max })} />
      </FilterPill>
      <FilterPill
        label={t('search.more')}
        icon={FilterIcon}
        width="w-[380px]"
        value={moreCount ? t('search.moreCount', { count: moreCount }) : undefined}
        onClear={() => onChange({ title_type: undefined, min_verification_level: undefined })}
      >
        <div className="space-y-6">
          <Group title={t('search.titleType')}>
            <TitleTypeField filters={filters} onChange={onChange} />
          </Group>
          <Group title={t('search.level')}>
            <LevelField filters={filters} onChange={onChange} />
          </Group>
        </div>
      </FilterPill>
    </>
  )
}

// Until the map arrives: what the levels mean, and the full check.
function SideColumn() {
  const { t } = useTranslation()
  return (
    <aside className="hidden space-y-6 xl:block">
      <div className="sticky top-24 space-y-6">
        <section aria-labelledby="guide-title" className="rounded-lg bg-white p-6 shadow-card">
          <p className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('home.ladderKicker')}</p>
          <h2 id="guide-title" className="mt-2 font-serif text-2xl font-semibold text-navy">
            {t('search.guideTitle')}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">{t('search.guideBody')}</p>
          <ul className="mt-5 space-y-4">
            {[...LEVELS].reverse().map((level) => (
              <li key={level} className="space-y-1.5">
                <VerificationBadge level={level} />
                <p className="text-[13px] leading-relaxed text-muted">{t(`levels.meaning${level}`)}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="relative overflow-hidden rounded-lg bg-navy p-6 text-white">
          <ShieldIcon className="absolute -top-5 -right-5 size-28 text-white/5" />
          <p className="text-xs font-semibold tracking-[0.2em] text-gold-light uppercase">{t('listing.fullCheckTitle')}</p>
          <p className="mt-3 text-sm leading-relaxed text-white/75">{t('listing.fullCheckBody')}</p>
          <a
            href={whatsappLink(t('site.supportMessage'))}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-5 inline-flex h-11 items-center gap-2 rounded-md bg-gold px-5 text-sm font-semibold text-navy hover:bg-gold-light"
          >
            <WhatsAppIcon className="size-4" />
            {t('site.support')}
          </a>
        </section>
      </div>
    </aside>
  )
}

// Regions once; districts and wards for the chosen parent. Stored with the
// parent id so a stale answer never shows under a different choice.
function usePlaces(region?: string, district?: string): Places {
  const [regions, setRegions] = useState<Place[]>([])
  const [districts, setDistricts] = useState<{ parent: string; rows: Place[] } | null>(null)
  const [wards, setWards] = useState<{ parent: string; rows: Place[] } | null>(null)

  useEffect(() => {
    let cancelled = false
    marketApi
      .regions()
      .then((rows) => !cancelled && setRegions(rows))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!region) return
    let cancelled = false
    marketApi
      .districts(region)
      .then((rows) => !cancelled && setDistricts({ parent: region, rows }))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [region])

  useEffect(() => {
    if (!district) return
    let cancelled = false
    marketApi
      .wards(district)
      .then((rows) => !cancelled && setWards({ parent: district, rows }))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [district])

  return {
    regions,
    districts: region && districts?.parent === region ? districts.rows : [],
    wards: district && wards?.parent === district ? wards.rows : [],
  }
}

// Phones and tablets: removable chips for every active filter.
function ActiveChips({
  filters,
  places,
  onRemove,
  onClear,
}: {
  filters: SearchParams
  places: Places
  onRemove: (changes: Change) => void
  onClear: () => void
}) {
  const { t, i18n } = useTranslation()
  const name = (rows: Place[], id?: string) => rows.find((row) => row.id === id)?.name

  const chips: { id: string; label: string; clear: Change }[] = []
  if (filters.category) chips.push({ id: 'category', label: t(`market.category.${filters.category}`), clear: { category: undefined } })
  if (filters.region)
    chips.push({ id: 'region', label: name(places.regions, filters.region) ?? t('search.region'), clear: { region: undefined, district: undefined, ward: undefined } })
  if (filters.district)
    chips.push({ id: 'district', label: name(places.districts, filters.district) ?? t('search.district'), clear: { district: undefined, ward: undefined } })
  if (filters.ward) chips.push({ id: 'ward', label: name(places.wards, filters.ward) ?? t('search.ward'), clear: { ward: undefined } })
  if (filters.min_price) chips.push({ id: 'min_price', label: t('search.priceFrom', { value: formatTsh(filters.min_price, i18n.language) }), clear: { min_price: undefined } })
  if (filters.max_price) chips.push({ id: 'max_price', label: t('search.priceTo', { value: formatTsh(filters.max_price, i18n.language) }), clear: { max_price: undefined } })
  if (filters.min_size) chips.push({ id: 'min_size', label: t('search.sizeFrom', { value: filters.min_size }), clear: { min_size: undefined } })
  if (filters.max_size) chips.push({ id: 'max_size', label: t('search.sizeTo', { value: filters.max_size }), clear: { max_size: undefined } })
  if (filters.title_type) chips.push({ id: 'title_type', label: t(`market.titleType.${filters.title_type}`), clear: { title_type: undefined } })
  if (filters.min_verification_level)
    chips.push({
      id: 'level',
      label: t('search.levelAtLeast', { label: t(`levels.short.${filters.min_verification_level}`) }),
      clear: { min_verification_level: undefined },
    })

  if (chips.length === 0) return null

  return (
    <div className="mt-5 flex flex-wrap items-center gap-2">
      <AnimatePresence initial={false} mode="popLayout">
        {chips.map((chip) => (
          <motion.button
            key={chip.id}
            layout
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.18 }}
            type="button"
            onClick={() => onRemove(chip.clear)}
            aria-label={t('search.removeFilter', { label: chip.label })}
            className="inline-flex h-9 items-center gap-1.5 rounded-full bg-navy px-3.5 text-sm font-medium text-white hover:bg-navy-soft"
          >
            {chip.label}
            <CloseIcon className="size-3.5" />
          </motion.button>
        ))}
      </AnimatePresence>
      <button type="button" onClick={onClear} className="text-link ml-1 text-sm">
        {t('search.clearAll')}
      </button>
    </div>
  )
}

function Results({
  loading,
  current,
  hasFilters,
  onRetry,
  onClear,
  onPage,
  pageNumber,
}: {
  loading: boolean
  current: Result | null
  hasFilters: boolean
  onRetry: () => void
  onClear: () => void
  onPage: (page: number) => void
  pageNumber: number
}) {
  const { t } = useTranslation()
  const grid = useRef<HTMLDivElement>(null)
  const page = current?.page

  // New results rise in with a short stagger (kept small for long lists).
  useGSAP(
    () => {
      if (!page?.results.length) return
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap.from('[data-card]', { opacity: 0, y: 18, duration: 0.45, stagger: 0.05, ease: 'power2.out', clearProps: 'all' })
      })
    },
    { scope: grid, dependencies: [page], revertOnUpdate: true },
  )

  if (loading) {
    return (
      <div className="grid gap-5">
        {Array.from({ length: 3 }, (_, index) => (
          <ResultCardSkeleton key={index} />
        ))}
      </div>
    )
  }

  if (current?.failed) {
    return (
      <div className="rounded-lg bg-white p-10 text-center shadow-card">
        <p className="font-serif text-2xl font-semibold text-navy">{t('search.errorTitle')}</p>
        <p className="mt-2 text-sm text-muted">{t('common.networkError')}</p>
        <button type="button" onClick={onRetry} className="mt-6 inline-flex h-11 items-center rounded-md bg-navy px-6 text-sm font-semibold text-white hover:bg-navy-soft">
          {t('search.retry')}
        </button>
      </div>
    )
  }

  if (!page || page.results.length === 0) {
    return (
      <div className="rounded-lg bg-white p-10 text-center shadow-card sm:p-14">
        <span className="mx-auto grid size-14 place-items-center rounded-full bg-gold/10 text-gold">
          <SearchIcon className="size-7" />
        </span>
        <p className="mt-5 font-serif text-2xl font-semibold text-navy">{t('search.emptyTitle')}</p>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted">{hasFilters ? t('search.emptyBody') : t('search.emptyNoFilters')}</p>
        {hasFilters && (
          <button type="button" onClick={onClear} className="text-link mt-5 text-sm">
            {t('search.clearAll')}
          </button>
        )}
      </div>
    )
  }

  const totalPages = Math.max(1, Math.ceil(page.count / PAGE_SIZE))

  return (
    <>
      <div ref={grid} className="grid gap-5">
        {page.results.map((listing, index) => (
          <ResultCard key={listing.listing_id} listing={listing} priority={index < 2} />
        ))}
      </div>
      {totalPages > 1 && (
        <nav aria-label={t('search.pagination')} className="mt-10 flex items-center justify-between gap-4 border-t border-mist pt-6">
          <button
            type="button"
            disabled={!page.previous}
            onClick={() => page.previous && onPage(page.previous)}
            className="h-11 rounded-xl bg-white px-5 text-sm font-semibold text-navy ring-1 ring-mist hover:ring-navy/30 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t('search.previous')}
          </button>
          <span className="text-sm text-muted">{t('search.pageOf', { page: pageNumber, total: totalPages })}</span>
          <button
            type="button"
            disabled={!page.next}
            onClick={() => page.next && onPage(page.next)}
            className="h-11 rounded-xl bg-navy px-5 text-sm font-semibold text-white hover:bg-navy-soft disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t('search.next')}
          </button>
        </nav>
      )}
    </>
  )
}

// Phone filters: a bottom sheet that can be dragged down to close.
function FilterSheet({ count, onClose, children }: { count: number | null; onClose: () => void; children: ReactNode }) {
  const { t } = useTranslation()
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    const previousOverflow = document.body.style.overflow
    const previousFocus = document.activeElement as HTMLElement | null
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKey)
    panel.current?.focus()
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKey)
      previousFocus?.focus()
    }
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label={t('search.filters')}>
      <motion.div className="absolute inset-0 bg-navy/60 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.div
        ref={panel}
        tabIndex={-1}
        className="absolute inset-x-0 bottom-0 flex max-h-[88dvh] flex-col rounded-t-3xl bg-white shadow-2xl outline-none"
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', stiffness: 380, damping: 38 }}
        drag="y"
        dragConstraints={{ top: 0, bottom: 0 }}
        dragElastic={{ top: 0, bottom: 0.6 }}
        onDragEnd={(_, info) => {
          if (info.offset.y > 120 || info.velocity.y > 600) onClose()
        }}
      >
        <div className="flex justify-center px-5 pt-3 pb-2">
          <span className="h-1.5 w-10 rounded-full bg-mist" aria-hidden="true" />
        </div>
        <div className="flex items-center justify-between px-5 pb-3">
          <h2 className="font-serif text-xl font-semibold text-navy">{t('search.filters')}</h2>
          <button type="button" onClick={onClose} aria-label={t('site.closeMenu')} className="grid size-10 place-items-center rounded-xl text-navy ring-1 ring-mist">
            <CloseIcon className="size-5" />
          </button>
        </div>
        {/* Stop drags that start inside the form so selects and inputs stay usable. */}
        <div className="flex-1 overflow-y-auto px-5 pb-4" onPointerDownCapture={(event) => event.stopPropagation()}>
          {children}
        </div>
        <div className="border-t border-mist p-4">
          <button type="button" onClick={onClose} className="h-12 w-full rounded-md bg-navy text-sm font-semibold text-white hover:bg-navy-soft">
            {count === null ? t('search.apply') : `${t('search.apply')} (${count})`}
          </button>
        </div>
      </motion.div>
    </div>
  )
}
