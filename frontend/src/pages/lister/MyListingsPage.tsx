import { useEffect, useMemo, useState, type ComponentType, type ReactNode, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { BuildingIcon, ChevronDownIcon, ClockIcon, HomeIcon, ImageIcon, LandIcon, PlusIcon, RulerIcon, SearchIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatNumber, formatRelative, formatTsh } from '../../lib/format'
import { listerApi } from '../../lib/listerApi'
import { CATEGORIES, type Category } from '../../lib/marketApi'
import { ListingsMap } from './ListingsMap'
import { isStatusFilter, loadListingRows, rowAddress, rowTitle, STATUS_FILTERS, type ListingRow, type StatusFilter } from './rows'
import { ListingStatusPill, RowMenu, type MenuItem } from './ui'

const CATEGORY_ICON: Record<Category, ComponentType<SVGProps<SVGSVGElement>>> = { LAND: LandIcon, HOUSE: HomeIcon, COMMERCIAL: BuildingIcon }
type Sort = 'newest' | 'oldest' | 'priceHigh' | 'priceLow'

// After L11: the title with "Add property" on the right, a search box and
// dropdown filters in one row, listing cards on the left and the price map on
// the right. The status submenu lives in the sidebar (and as chips on phones).
export function MyListingsPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [search, setSearch] = useSearchParams()
  const [rows, setRows] = useState<ListingRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(() => {
    const state = location.state as { published?: string; saved?: boolean } | null
    return state?.published ? t('lister.listings.published') : state?.saved ? t('lister.listings.saved') : null
  })
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<Category | ''>('')
  const [sort, setSort] = useState<Sort>('newest')
  const [hovered, setHovered] = useState<string | null>(null)
  const [now] = useState(() => Date.now())
  useDocumentTitle(t('lister.listings.title'))

  const status = search.get('status')
  const filter: StatusFilter | null = isStatusFilter(status) ? status : null

  useEffect(() => {
    let live = true
    loadListingRows()
      .then((loaded) => live && setRows(loaded))
      .catch((caught) => live && setError(errorMessage(t, caught)))
    return () => {
      live = false
    }
  }, [t])

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const list = (rows ?? []).filter((row) => {
      if (filter && !(STATUS_FILTERS[filter] as string[]).includes(row.listing.status)) return false
      if (category && row.property?.category !== category) return false
      if (needle && !`${rowTitle(t, row)} ${rowAddress(row)} ${row.listing.listing_id}`.toLowerCase().includes(needle)) return false
      return true
    })
    const price = (row: ListingRow) => Number(row.listing.selling_price)
    const sorters: Record<Sort, (a: ListingRow, b: ListingRow) => number> = {
      newest: (a, b) => b.listing.created_at.localeCompare(a.listing.created_at),
      oldest: (a, b) => a.listing.created_at.localeCompare(b.listing.created_at),
      priceHigh: (a, b) => price(b) - price(a),
      priceLow: (a, b) => price(a) - price(b),
    }
    return [...list].sort(sorters[sort])
  }, [rows, filter, category, query, sort, t])

  async function withdraw(row: ListingRow) {
    setError(null)
    try {
      const updated = await listerApi.withdraw(row.listing.listing_id)
      setRows((current) => current?.map((item) => (item.listing.listing_id === updated.listing_id ? { ...item, listing: updated } : item)) ?? null)
      setNotice(t('lister.listings.withdrawn'))
    } catch (caught) {
      setError(errorMessage(t, caught))
    }
  }

  function actions(row: ListingRow): MenuItem[] {
    const id = row.listing.listing_id
    const items: MenuItem[] = [{ label: t('lister.listings.edit'), onSelect: () => navigate(`/lister/listings/${id}`) }]
    if (row.listing.status === 'DRAFT') items.push({ label: t('lister.listings.publish'), onSelect: () => navigate(`/lister/listings/${id}?step=4`) })
    if (row.listing.status === 'ACTIVE' || row.listing.status === 'UNDER_OFFER') {
      items.push({ label: t('lister.listings.viewPublic'), onSelect: () => navigate(`/listings/${id}`) })
      items.push({ label: t('lister.listings.withdraw'), onSelect: () => void withdraw(row), tone: 'danger' })
    }
    return items
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-[24px] font-normal text-navy">{t('lister.listings.title')}</h1>
        <Link
          to="/lister/listings/new"
          className="inline-flex h-10 items-center gap-2 rounded-md bg-gold px-4 text-[14px] font-medium text-navy transition-colors hover:bg-gold-light"
        >
          <PlusIcon className="size-4" />
          {t('lister.addListing')}
        </Link>
      </div>

      {notice && (
        <div className="mb-4">
          <Alert tone="success">{notice}</Alert>
        </div>
      )}
      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {/* Phones have no sidebar submenu in view, so the statuses sit here. */}
      <div className="-mx-1 mb-3 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] lg:hidden">
        {(['', ...Object.keys(STATUS_FILTERS)] as ('' | StatusFilter)[]).map((key) => {
          const on = (filter ?? '') === key
          return (
            <button
              key={key || 'all'}
              type="button"
              onClick={() => {
                setNotice(null)
                setSearch(key ? { status: key } : {})
              }}
              aria-pressed={on}
              className={`h-9 shrink-0 rounded-full border px-3.5 text-[13px] ${on ? 'border-gold/50 bg-gold/12 font-medium text-[#7a5410]' : 'border-mist bg-white text-navy-soft'}`}
            >
              {t(`lister.filters.${key || 'all'}`)}
            </button>
          )
        })}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="relative block w-full sm:w-[300px]">
          <span className="sr-only">{t('lister.listings.search')}</span>
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-navy-soft" />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('lister.listings.search')}
            className="h-11 w-full rounded-md border border-mist bg-white pr-3 pl-10 text-[14px] text-navy outline-none placeholder:text-muted/80 focus:border-gold focus:ring-2 focus:ring-gold/20"
          />
        </label>
        <Dropdown
          label={t('lister.listings.type')}
          value={category}
          onChange={(value) => setCategory(value as Category | '')}
          options={[{ value: '', label: t('lister.listings.type') }, ...CATEGORIES.map((value) => ({ value, label: t(`market.category.${value}`) }))]}
        />
        <Dropdown
          label={t('lister.listings.sort')}
          value={sort}
          onChange={(value) => setSort(value as Sort)}
          options={(['newest', 'oldest', 'priceHigh', 'priceLow'] as const).map((value) => ({ value, label: t(`lister.listings.sorts.${value}`) }))}
        />
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 lg:grid-cols-[minmax(0,1.12fr)_minmax(0,1fr)]">
        <ul className="space-y-3" aria-busy={rows === null}>
          {rows === null &&
            [0, 1, 2].map((item) => <li key={item} className="h-[164px] animate-pulse rounded-lg border border-mist bg-white" />)}
          {rows !== null && shown.length === 0 && (
            <li className="rounded-lg border border-dashed border-mist bg-white px-6 py-12 text-center">
              <p className="text-[15px] text-navy">{rows.length === 0 ? t('lister.listings.emptyTitle') : t('lister.listings.noMatch')}</p>
              {rows.length === 0 && (
                <Link to="/lister/listings/new" className="mt-3 inline-flex items-center gap-2 text-[14px] font-semibold text-[#9a6c12] hover:underline">
                  <PlusIcon className="size-4" />
                  {t('lister.addListing')}
                </Link>
              )}
            </li>
          )}
          {shown.map((row) => {
            const Icon = row.property ? CATEGORY_ICON[row.property.category] : HomeIcon
            const open = () => navigate(`/lister/listings/${row.listing.listing_id}`)
            const published = row.listing.status !== 'DRAFT'
            return (
              <li
                key={row.listing.listing_id}
                onMouseEnter={() => setHovered(row.listing.listing_id)}
                onMouseLeave={() => setHovered(null)}
                className="flex gap-4 rounded-lg border border-mist bg-white p-2 transition-shadow hover:shadow-[0_6px_20px_-12px_rgba(15,23,42,0.35)]"
              >
                <button type="button" onClick={open} className="size-[104px] shrink-0 overflow-hidden rounded-md bg-paper sm:size-[146px]" tabIndex={-1} aria-hidden="true">
                  {row.cover ? (
                    <img src={row.cover} alt="" className="size-full object-cover" />
                  ) : (
                    <span className="grid size-full place-items-center text-muted/60">
                      <ImageIcon className="size-7" />
                    </span>
                  )}
                </button>
                <div className="min-w-0 flex-1 py-1 pr-1">
                  <div className="flex items-start justify-between gap-2">
                    <Link to={`/lister/listings/${row.listing.listing_id}`} className="min-w-0 truncate text-[19px] leading-tight font-normal text-navy hover:underline sm:text-[23px]">
                      {rowTitle(t, row)}
                    </Link>
                    <span className="flex shrink-0 items-center gap-1 pt-1">
                      <span className="hidden sm:inline-flex">
                        <ListingStatusPill status={row.listing.status} />
                      </span>
                      <RowMenu label={t('lister.listings.actions')} items={actions(row)} />
                    </span>
                  </div>
                  <p className="mt-1 truncate text-[13.5px] text-navy-soft">{rowAddress(row) || row.listing.listing_id}</p>
                  <ul className="mt-2.5 flex flex-wrap items-center gap-y-1 text-[13.5px] text-navy">
                    {row.property && (
                      <Fact icon={Icon} first>
                        {t(`market.category.${row.property.category}`)}
                      </Fact>
                    )}
                    {row.property?.stated_size && (
                      <Fact icon={RulerIcon}>
                        {formatNumber(row.property.stated_size, i18n.language)} {t(`lister.unitsShort.${row.property.size_unit}`, { defaultValue: row.property.size_unit })}
                      </Fact>
                    )}
                    <Fact icon={ImageIcon}>{t('market.photoCount', { count: row.photoCount })}</Fact>
                  </ul>
                  <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-mist pt-2.5 text-[13.5px] text-navy">
                    <span className="inline-flex items-center gap-1.5">
                      <ClockIcon className="size-4 text-gold" />
                      {t(published ? 'lister.listings.listedAgo' : 'lister.listings.createdAgo', {
                        when: formatRelative(published ? row.listing.updated_at : row.listing.created_at, i18n.language, now),
                      })}
                    </span>
                    <span className="font-medium tabular-nums">{formatTsh(row.listing.selling_price, i18n.language)}</span>
                    <span className="sm:hidden">
                      <ListingStatusPill status={row.listing.status} />
                    </span>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>

        <div className="sticky top-24 hidden h-[calc(100vh-190px)] min-h-[420px] lg:block">
          <ListingsMap rows={shown} highlighted={hovered} onOpen={(id) => navigate(`/lister/listings/${id}`)} />
        </div>
      </div>
    </div>
  )
}

function Fact({ icon: Icon, first = false, className = '', children }: { icon: ComponentType<SVGProps<SVGSVGElement>>; first?: boolean; className?: string; children: ReactNode }) {
  return (
    <li className={`inline-flex items-center gap-1.5 ${first ? 'pr-3' : 'border-l border-mist px-3'} ${className}`}>
      <Icon className="size-4 text-gold" />
      {children}
    </li>
  )
}

// L11's filter buttons: a bordered box with the value and a chevron.
function Dropdown({ label, value, options, onChange }: { label: string; value: string; options: { value: string; label: string }[]; onChange: (value: string) => void }) {
  return (
    <label className="relative block min-w-0 flex-1 sm:inline-block sm:flex-none">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full appearance-none rounded-md border border-mist bg-white pr-10 pl-4 text-[14px] text-navy outline-none hover:border-navy-soft/40 focus:border-gold focus:ring-2 focus:ring-gold/20"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-navy-soft" />
    </label>
  )
}
