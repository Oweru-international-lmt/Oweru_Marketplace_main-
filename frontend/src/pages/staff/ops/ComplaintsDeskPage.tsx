import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { AlertIcon, ChevronDownIcon } from '../../../components/icons'
import { PageHeader } from '../../../components/PageHeader'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'
import { initials } from '../../../lib/initials'
import { staffApi, type DeskComplaint } from '../../../lib/staffApi'
import { ComplaintChip, RadioTabs, RowTable, SearchBox, type Column } from './ui'

const FILTERS = ['all', 'open', 'waiting', 'overdue', 'finalReview', 'done'] as const
type Filter = (typeof FILTERS)[number]

const MATCH: Record<Filter, (row: DeskComplaint) => boolean> = {
  all: () => true,
  open: (row) => row.status === 'RECEIVED' || row.status === 'IN_REVIEW' || row.status === 'WAITING_INFORMATION',
  waiting: (row) => row.status === 'WAITING_INFORMATION',
  overdue: (row) => row.overdue,
  finalReview: (row) => row.status === 'UNDER_FINAL_REVIEW',
  done: (row) => row.status === 'RESOLVED' || row.status === 'CLOSED',
}

// Soft avatar colours, after W4's round initials; chosen by name so a person keeps theirs.
const AVATARS = ['bg-[#e8eefb] text-[#3552a8]', 'bg-gold/15 text-[#7a5410]', 'bg-success-soft text-success', 'bg-[#f1e9fa] text-[#6b3fa0]', 'bg-navy/10 text-navy']

function avatarFor(name: string): string {
  let sum = 0
  for (const char of name) sum += char.charCodeAt(0)
  return AVATARS[sum % AVATARS.length]
}

// CMP-04 and CMP-08: every complaint the handler may see, after W4's table
// with W5's status tabs. Overdue rows say so in red.
export function ComplaintsDeskPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const filter: Filter = FILTERS.includes(params.get('filter') as Filter) ? (params.get('filter') as Filter) : 'all'
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<'newest' | 'due'>('newest')
  const [rows, setRows] = useState<DeskComplaint[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    staffApi
      .complaints()
      .then((list) => !cancelled && setRows(list))
      .catch((failure: unknown) => !cancelled && setError(errorMessage(t, failure)))
    return () => {
      cancelled = true
    }
  }, [t])

  const shown = useMemo(() => {
    if (!rows) return []
    const text = query.trim().toLowerCase()
    return rows
      .filter(MATCH[filter])
      .filter((row) => !text || row.reference.toLowerCase().includes(text) || row.name.toLowerCase().includes(text))
      .sort((a, b) => (sort === 'newest' ? b.created_at.localeCompare(a.created_at) : a.resolution_due_at.localeCompare(b.resolution_due_at)))
  }, [rows, filter, query, sort])

  const columns: Column<DeskComplaint>[] = [
    {
      key: 'name',
      label: t('staff.complaints.complainant'),
      render: (row) => (
        <span className="flex items-center gap-3">
          <span className={`grid size-8 shrink-0 place-items-center rounded-full text-[11px] font-semibold ${avatarFor(row.name)}`}>{initials(row.name)}</span>
          <span className="truncate font-medium">{row.name}</span>
        </span>
      ),
    },
    { key: 'reference', label: t('staff.complaints.number'), render: (row) => <span className="font-mono text-[11px] text-muted">{row.reference}</span> },
    {
      key: 'type',
      label: t('staff.complaints.type'),
      render: (row) => (
        <span className="block max-w-[180px] truncate" title={t(`complaint.types.${row.category}`)}>
          {t(`complaint.types.${row.category}`)}
        </span>
      ),
    },
    {
      key: 'team',
      label: t('staff.complaints.team'),
      render: (row) => (
        <span className="block max-w-[140px] truncate text-navy/75" title={t(`staff.routes.${row.route}`)}>
          {t(`staff.routes.${row.route}`)}
        </span>
      ),
    },
    { key: 'status', label: t('staff.complaints.status'), render: (row) => <ComplaintChip status={row.status} /> },
    {
      key: 'due',
      label: t('staff.complaints.target'),
      // CMP-08: overdue shows as a red date with an alert mark, and says so to screen readers.
      render: (row) =>
        row.overdue ? (
          <span className="inline-flex items-center gap-1.5 font-medium text-danger" title={t('staff.complaints.overdue')}>
            <AlertIcon className="size-4" />
            {formatShortDate(row.resolution_due_at, i18n.language)}
            <span className="sr-only">{t('staff.complaints.overdue')}</span>
          </span>
        ) : (
          <span className="text-navy/75">{formatShortDate(row.resolution_due_at, i18n.language)}</span>
        ),
    },
    { key: 'received', label: t('staff.complaints.received'), render: (row) => <span className="text-navy/75">{formatShortDate(row.created_at, i18n.language)}</span> },
    {
      key: 'more',
      label: '',
      className: 'w-12 text-right',
      render: (row) => (
        <Link
          to={`/staff/complaints/${row.id}`}
          onClick={(event) => event.stopPropagation()}
          aria-label={t('staff.complaints.open', { reference: row.reference })}
          className="inline-grid size-8 place-items-center rounded-[6px] text-lg leading-none text-muted hover:bg-mist/60 hover:text-navy"
        >
          ···
        </Link>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title={t('staff.complaints.title')}
        description={rows ? t('staff.complaints.total', { count: rows.length }) : undefined}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <SearchBox label={t('staff.complaints.search')} value={query} onChange={setQuery} />
            <label className="relative inline-flex items-center gap-2 text-[13px] text-muted">
              {t('staff.complaints.sortBy')}
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as 'newest' | 'due')}
                className="h-10 appearance-none rounded-[6px] border border-mist bg-white pr-9 pl-3 font-medium text-navy outline-none focus:border-gold"
              >
                <option value="newest">{t('staff.complaints.sortNewest')}</option>
                <option value="due">{t('staff.complaints.sortDue')}</option>
              </select>
              <ChevronDownIcon className="pointer-events-none absolute right-3 size-4 text-muted" />
            </label>
          </div>
        }
      />

      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <RadioTabs
          label={t('staff.complaints.filter')}
          value={filter}
          onChange={(value: Filter) => setParams(value === 'all' ? {} : { filter: value })}
          options={FILTERS.map((value) => ({ value, label: t(`staff.complaints.filters.${value}`), count: rows ? rows.filter(MATCH[value]).length : undefined }))}
        />
      </div>

      {error ? (
        <Alert tone="error">{error}</Alert>
      ) : !rows ? (
        <FullPageLoader inline />
      ) : (
        <RowTable
          caption={t('staff.complaints.title')}
          columns={columns}
          rows={shown}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/staff/complaints/${row.id}`)}
          empty={t('staff.complaints.empty')}
        />
      )}
    </>
  )
}
