import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { ShieldIcon } from '../../../components/icons'
import { PageHeader } from '../../../components/PageHeader'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate, formatTsh } from '../../../lib/format'
import type { FullCheck, FullCheckStatus } from '../../../lib/servicesApi'
import { staffApi } from '../../../lib/staffApi'
import { CheckChip, RadioTabs, RowTable, SearchBox, type Column } from './ui'

const FILTERS = ['all', 'AWAITING_PAYMENT', 'AWAITING_CONSENT', 'IN_PROGRESS', 'UNDER_REVIEW', 'finished'] as const
type Filter = (typeof FILTERS)[number]
const FINISHED: FullCheckStatus[] = ['PASSED', 'PROBLEM_FOUND', 'NOT_COMPLETED']

function matches(filter: Filter, check: FullCheck): boolean {
  if (filter === 'all') return true
  if (filter === 'finished') return FINISHED.includes(check.status)
  return check.status === filter
}

// Full checks for staff, after W4's table and W5's tabs: Management sees all
// of them (payments to confirm first), a Verifier the ones assigned to them.
export function FullChecksDeskPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const filter: Filter = FILTERS.includes(params.get('status') as Filter) ? (params.get('status') as Filter) : 'all'
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState<FullCheck[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    staffApi
      .fullChecks()
      .then((page) => !cancelled && setRows(page.results))
      .catch((failure: unknown) => !cancelled && setError(errorMessage(t, failure)))
    return () => {
      cancelled = true
    }
  }, [t])

  const shown = useMemo(() => {
    const text = query.trim().toLowerCase()
    return (rows ?? []).filter((check) => matches(filter, check)).filter((check) => !text || check.property_id.toLowerCase().includes(text) || check.payment_reference.includes(text))
  }, [rows, filter, query])

  const columns: Column<FullCheck>[] = [
    {
      key: 'property',
      label: t('staff.checks.property'),
      render: (check) => (
        <span className="flex items-center gap-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-navy/10 text-navy">
            <ShieldIcon className="size-4" />
          </span>
          <span className="font-mono text-[13px] font-semibold">{check.property_id}</span>
        </span>
      ),
    },
    { key: 'kind', label: t('staff.checks.kind'), render: (check) => t(`staff.checks.kinds.${check.kind}`) },
    { key: 'status', label: t('staff.checks.status'), render: (check) => <CheckChip status={check.status} /> },
    { key: 'fee', label: t('staff.checks.fee'), render: (check) => <span className="tabular-nums">{formatTsh(check.fee, i18n.language)}</span> },
    { key: 'reference', label: t('staff.checks.reference'), render: (check) => <span className="font-mono text-xs text-muted">{check.payment_reference.slice(0, 8)}…</span> },
    { key: 'ordered', label: t('staff.checks.ordered'), render: (check) => <span className="text-navy/75">{formatShortDate(check.created_at, i18n.language)}</span> },
    {
      key: 'more',
      label: '',
      className: 'w-12 text-right',
      render: (check) => (
        <Link
          to={`/staff/full-checks/${check.id}`}
          onClick={(event) => event.stopPropagation()}
          aria-label={t('staff.checks.open', { property: check.property_id })}
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
        title={t('staff.checks.title')}
        description={rows ? t('staff.checks.total', { count: rows.length }) : undefined}
        actions={<SearchBox label={t('staff.checks.search')} value={query} onChange={setQuery} />}
      />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <RadioTabs
          label={t('staff.checks.filter')}
          value={filter}
          onChange={(value: Filter) => setParams(value === 'all' ? {} : { status: value })}
          options={FILTERS.map((value) => ({
            value,
            label: value === 'all' || value === 'finished' ? t(`staff.checks.filters.${value}`) : t(`staff.stageShort.${value}`),
            count: rows ? rows.filter((check) => matches(value, check)).length : undefined,
          }))}
        />
      </div>
      {error ? (
        <Alert tone="error">{error}</Alert>
      ) : !rows ? (
        <FullPageLoader inline />
      ) : (
        <RowTable
          caption={t('staff.checks.title')}
          columns={columns}
          rows={shown}
          rowKey={(check) => check.id}
          onOpen={(check) => navigate(`/staff/full-checks/${check.id}`)}
          empty={t('staff.checks.empty')}
        />
      )}
    </>
  )
}
