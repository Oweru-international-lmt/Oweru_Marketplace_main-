import { useEffect, useMemo, useState, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { ClockIcon, FilterIcon, MailIcon, PlusIcon, SearchIcon, TickIcon, UsersIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { formatRelative } from '../../../lib/format'
import { panelApi, type Campaign } from '../../../lib/panelApi'
import { Chip, NestedTile, Panel } from './ui'

const PAGE = 6

function CursorIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="m4 4 7 17 2.5-7.5L21 11 4 4Z" />
    </svg>
  )
}

function status(row: Campaign): 'sending' | 'sent' | 'failed' {
  if (row.sent + row.failed + row.cancelled < row.recipients) return 'sending'
  return row.failed > 0 && row.sent === 0 ? 'failed' : 'sent'
}

// MAR-03, after M8: four tiles, then each campaign as a card with its own
// figures in grey boxes; only people who agreed to marketing receive it.
export function CampaignsPage() {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('staff.marketing.campaigns.title'))
  const [rows, setRows] = useState<Campaign[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [state, setState] = useState<'all' | 'sending' | 'sent' | 'failed'>('all')
  const [page, setPage] = useState(0)

  useEffect(() => {
    panelApi.campaigns().then(setRows, (caught) => setError(errorMessage(t, caught)))
  }, [t])

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (rows ?? []).filter(
      (row) =>
        (state === 'all' || status(row) === state) &&
        (!needle || `${row.subject_sw} ${row.subject_en} ${row.source_tag}`.toLowerCase().includes(needle)),
    )
  }, [rows, query, state])
  const pages = Math.max(1, Math.ceil(shown.length / PAGE))
  const visible = shown.slice(page * PAGE, page * PAGE + PAGE)
  const totals = (rows ?? []).reduce((all, row) => ({ recipients: all.recipients + row.recipients, sent: all.sent + row.sent, clicks: all.clicks + row.clicks }), { recipients: 0, sent: 0, clicks: 0 })
  const clickRate = totals.sent ? (totals.clicks / totals.sent) * 100 : null

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[28px] leading-tight font-medium text-navy">{t('staff.marketing.campaigns.title')}</h1>
          <p className="mt-1 text-[14px] text-muted">{t('staff.marketing.campaigns.subtitle')}</p>
        </div>
        <Link to="/staff/marketing/campaigns/new" className="inline-flex h-12 items-center gap-2 rounded-xl bg-navy px-5 text-[15px] font-medium text-white shadow-[0_6px_16px_-6px_rgba(15,23,42,0.5)] hover:bg-navy-soft">
          <PlusIcon className="size-5" />
          {t('staff.marketing.campaigns.new')}
        </Link>
      </header>

      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <NestedTile icon={MailIcon} label={t('staff.marketing.campaigns.tiles.total')} value={rows?.length ?? '-'} />
        <NestedTile icon={UsersIcon} label={t('staff.marketing.campaigns.tiles.recipients')} value={totals.recipients.toLocaleString()} />
        <NestedTile icon={TickIcon} label={t('staff.marketing.campaigns.tiles.sent')} value={totals.sent.toLocaleString()} chip={totals.recipients ? <Chip tone="good">{Math.round((totals.sent / totals.recipients) * 100)}%</Chip> : undefined} />
        <NestedTile icon={CursorIcon} label={t('staff.marketing.campaigns.tiles.clickRate')} value={clickRate === null ? '-' : `${clickRate.toFixed(1)}%`} />
      </div>

      <Panel className="px-5 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[22px] font-medium text-navy">{t('staff.marketing.campaigns.recent')}</h2>
          <div className="flex flex-wrap gap-2">
            <label className="relative">
              <span className="sr-only">{t('staff.marketing.campaigns.search')}</span>
              <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
              <input
                type="search"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value)
                  setPage(0)
                }}
                placeholder={t('staff.marketing.campaigns.search')}
                className="h-10 w-60 rounded-lg border border-mist pr-3 pl-9 text-[13.5px] outline-none placeholder:text-muted/80 focus:border-gold"
              />
            </label>
            <label className="relative">
              <span className="sr-only">{t('staff.marketing.campaigns.status')}</span>
              <select
                value={state}
                onChange={(event) => {
                  setState(event.target.value as typeof state)
                  setPage(0)
                }}
                className="h-10 rounded-lg border border-mist bg-white pr-8 pl-3 text-[13.5px] text-navy outline-none focus:border-gold"
              >
                {(['all', 'sending', 'sent', 'failed'] as const).map((value) => <option key={value} value={value}>{t(`staff.marketing.campaigns.states.${value}`)}</option>)}
              </select>
            </label>
            <span className="inline-flex h-10 items-center gap-2 rounded-lg border border-mist px-3 text-[13.5px] text-navy-soft">
              <FilterIcon className="size-4" />
              {t('staff.marketing.campaigns.consentOnly')}
            </span>
          </div>
        </div>

        <ul className="mt-5 space-y-3">
          {rows === null && [0, 1].map((index) => <li key={index} className="h-[150px] animate-pulse rounded-[18px] bg-paper" />)}
          {rows !== null && visible.length === 0 && <li className="rounded-[18px] border border-mist py-12 text-center text-[14px] text-muted">{t('staff.marketing.campaigns.empty')}</li>}
          {visible.map((row) => {
            const subject = i18n.language === 'en' ? row.subject_en : row.subject_sw
            const other = i18n.language === 'en' ? row.subject_sw : row.subject_en
            const state = status(row)
            const figures = [
              ['recipients', row.recipients.toLocaleString()],
              ['sent', row.sent.toLocaleString()],
              ['failed', row.failed.toLocaleString()],
              ['clicks', row.clicks.toLocaleString()],
              ['clickRate', row.sent ? `${((row.clicks / row.sent) * 100).toFixed(1)}%` : '-'],
            ] as const
            return (
              <li key={row.id} className="rounded-[18px] border border-mist/80 px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 gap-3">
                    <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-mist bg-white text-navy"><MailIcon className="size-[18px]" /></span>
                    <div className="min-w-0">
                      <p className="truncate text-[16px] font-medium text-navy">{subject}</p>
                      <p className="flex flex-wrap items-center gap-x-2 text-[13px] text-navy-soft">
                        <span className="truncate">{other}</span>
                        <span aria-hidden="true" className="size-1 rounded-full bg-muted" />
                        <span className="inline-flex items-center gap-1"><ClockIcon className="size-3.5" />{formatRelative(row.created_at, i18n.language)}</span>
                      </p>
                    </div>
                  </div>
                  <Chip tone={state === 'sent' ? 'good' : state === 'failed' ? 'bad' : 'gold'}>{t(`staff.marketing.campaigns.states.${state}`)}</Chip>
                </div>
                <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
                  <p className="flex flex-wrap gap-2">
                    <span className="rounded-lg bg-paper px-2.5 py-1 font-mono text-[12px] text-navy-soft">{row.source_tag}</span>
                    <span className="rounded-lg bg-paper px-2.5 py-1 text-[12px] text-navy-soft">{row.target_path}</span>
                  </p>
                  <dl className="grid w-full grid-cols-2 gap-2 sm:w-auto sm:grid-cols-5">
                    {figures.map(([key, value]) => (
                      <div key={key} className="min-w-[104px] rounded-xl bg-[#f6f6f8] px-3.5 py-2.5">
                        <dt className="text-[13px] text-navy-soft">{t(`staff.marketing.campaigns.figures.${key}`)}</dt>
                        <dd className="text-[19px] text-navy tabular-nums">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </li>
            )
          })}
        </ul>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-[13px] text-navy-soft">
          <span>{t('staff.marketing.campaigns.page', { page: page + 1, pages })}</span>
          <span className="flex items-center gap-1.5">
            <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)} className="h-8 rounded-lg border border-mist px-3 disabled:opacity-40">{t('staff.locationChecks.previous')}</button>
            {Array.from({ length: pages }, (_, index) => (
              <button key={index} type="button" aria-current={index === page ? 'page' : undefined} onClick={() => setPage(index)} className={`size-8 rounded-lg text-[12.5px] ${index === page ? 'bg-navy text-white' : 'border border-mist'}`}>
                {String(index + 1).padStart(2, '0')}
              </button>
            ))}
            <button type="button" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} className="h-8 rounded-lg border border-mist px-3 disabled:opacity-40">{t('staff.locationChecks.next')}</button>
          </span>
        </div>
      </Panel>
    </div>
  )
}
