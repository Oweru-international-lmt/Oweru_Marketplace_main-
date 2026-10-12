import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { ArrowRightIcon, BarsIcon, BuildingIcon, CalendarIcon, ChatIcon, IdCardIcon, InboxIcon, ListIcon, PlusIcon, WhatsAppIcon } from '../../components/icons'
import { PageHeader } from '../../components/PageHeader'
import { errorMessage } from '../../lib/errors'
import { formatShortDate, formatTime, formatTsh } from '../../lib/format'
import { listerApi, OPEN_STAGES, type Lead, type LeadStage, type ListerIdentity } from '../../lib/listerApi'
import { loadListingRows, rowTitle, type ListingRow } from './rows'
import { CountCard, ListingStatusPill, Notice, Panel, StagePill } from './ui'

type Data = { rows: ListingRow[]; leads: Lead[]; identity: ListerIdentity | null; now: number }

const SOURCE_ICON = { ENQUIRY: ChatIcon, WHATSAPP_CONTACT: WhatsAppIcon, VIEWING_REQUEST: CalendarIcon }
const WEEK = 7 * 86_400_000

// After L10: three counts, the latest listings as a table, then the latest
// enquiries beside a bar chart of where enquiries stand.
export function ListerHomePage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    Promise.all([loadListingRows(), listerApi.leads(), listerApi.identity().catch(() => null)])
      .then(([rows, leads, identity]) => live && setData({ rows, leads, identity, now: Date.now() }))
      .catch((caught) => live && setError(errorMessage(t, caught)))
    return () => {
      live = false
    }
  }, [t])

  const rows = data?.rows ?? []
  const leads = data ? [...data.leads].sort((a, b) => b.created_at.localeCompare(a.created_at)) : []
  const titleFor = (listingId: string) => {
    const row = rows.find((item) => item.listing.listing_id === listingId)
    return row ? rowTitle(t, row) : listingId
  }
  const live = rows.filter((row) => row.listing.status === 'ACTIVE' || row.listing.status === 'UNDER_OFFER').length
  const verified = data?.identity?.status === 'APPROVED'

  return (
    <>
      <PageHeader
        title={t('lister.home.title')}
        actions={
          <Link
            to="/lister/listings/new"
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-gold px-4 text-[13px] font-semibold text-navy transition-colors hover:bg-gold-light"
          >
            <PlusIcon className="size-4" />
            {t('lister.addListing')}
          </Link>
        }
      />
      {error && <Alert tone="error">{error}</Alert>}

      {data && !verified && (
        <div className="mb-5">
          <Notice
            icon={IdCardIcon}
            title={t('lister.home.verifyTitle')}
            body={t('lister.home.verifyBody')}
            action={
              <Link to="/lister/identity" className="inline-flex h-10 items-center rounded-lg bg-navy px-4 text-[13px] font-semibold text-white hover:bg-navy-soft">
                {t('lister.home.verifyAction')}
              </Link>
            }
          />
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-3">
        <CountCard
          label={t('lister.home.total')}
          icon={BuildingIcon}
          value={data ? rows.length : '-'}
          note={t('lister.home.drafts', { count: rows.filter((row) => row.listing.status === 'DRAFT').length })}
        />
        <CountCard
          label={t('lister.home.newEnquiries')}
          icon={InboxIcon}
          value={data ? leads.filter((lead) => lead.stage === 'NEW').length : '-'}
          note={t('lister.home.thisWeek', { count: data ? leads.filter((lead) => data.now - new Date(lead.created_at).getTime() < WEEK).length : 0 })}
        />
        <CountCard
          label={t('lister.home.live')}
          icon={ListIcon}
          value={data ? live : '-'}
          note={t('lister.home.sold', { count: rows.filter((row) => row.listing.status === 'SOLD').length })}
        />
      </div>

      <Panel
        title={t('lister.home.recentListings')}
        icon={BuildingIcon}
        className="mt-5"
        action={<ViewAll to="/lister/listings" />}
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left">
            <caption className="sr-only">{t('lister.home.recentListings')}</caption>
            <thead>
              <tr className="bg-[#f4f6f9] text-[13px] tracking-[0.04em] text-navy-soft uppercase">
                {['property', 'location', 'price', 'status', 'kind'].map((column, index) => (
                  <th key={column} scope="col" className={`px-6 py-3.5 font-medium ${index > 0 ? 'border-l border-mist/70' : ''}`}>
                    {t(`lister.home.columns.${column}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data && rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-sm text-muted">
                    {t('lister.home.noListings')}{' '}
                    <Link to="/lister/listings/new" className="font-semibold text-[#9a6c12] underline underline-offset-2">
                      {t('lister.addListing')}
                    </Link>
                  </td>
                </tr>
              )}
              {rows.slice(0, 5).map((row) => (
                <tr
                  key={row.listing.listing_id}
                  onClick={() => navigate(`/lister/listings/${row.listing.listing_id}`)}
                  className="cursor-pointer border-t border-mist text-[15px] text-navy transition-colors hover:bg-paper"
                >
                  <td className="px-6 py-5">
                    <Link to={`/lister/listings/${row.listing.listing_id}`} className="hover:underline" onClick={(event) => event.stopPropagation()}>
                      {rowTitle(t, row)}
                    </Link>
                  </td>
                  <td className="px-6 py-5">{row.place?.district ?? '-'}</td>
                  <td className="px-6 py-5 tabular-nums">{formatTsh(row.listing.selling_price, i18n.language)}</td>
                  <td className="px-6 py-5">
                    <ListingStatusPill status={row.listing.status} />
                  </td>
                  <td className="px-6 py-5">{t(`lister.kinds.${row.listing.lister_kind}`)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)]">
        <Panel title={t('lister.home.recentEnquiries')} icon={InboxIcon} action={<ViewAll to="/lister/enquiries" />}>
          <ul className="divide-y divide-mist/70">
            {data && leads.length === 0 && <li className="px-6 py-10 text-center text-sm text-muted">{t('lister.home.noEnquiries')}</li>}
            {leads.slice(0, 4).map((lead) => {
              const Icon = SOURCE_ICON[lead.source]
              const today = new Date(lead.created_at).toDateString() === new Date(data?.now ?? 0).toDateString()
              return (
                <li key={lead.id} className="flex gap-4 px-6 py-5">
                  <span className="grid size-12 shrink-0 place-items-center rounded-lg border border-mist text-[#9a6c12] shadow-[0_1px_2px_rgba(15,23,42,0.06)]">
                    <Icon className="size-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2.5">
                      <p className="truncate text-[16px] text-navy">{lead.buyer_name}</p>
                      <StagePill stage={lead.stage} />
                      <span className="ml-auto shrink-0 text-[13px] text-muted">
                        {today ? formatTime(lead.created_at, i18n.language) : formatShortDate(lead.created_at, i18n.language)}
                      </span>
                    </div>
                    <p className="mt-1.5 truncate text-[15px] text-navy">
                      {t('lister.home.for')} {titleFor(lead.listing_id)}
                    </p>
                    <p className="mt-1 text-[14px] text-navy-soft">{t(`lister.sources.${lead.source}`)}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </Panel>

        <Panel title={t('lister.home.stagesTitle')} icon={BarsIcon}>
          <StageBars leads={leads} />
        </Panel>
      </div>
    </>
  )
}

function ViewAll({ to }: { to: string }) {
  const { t } = useTranslation()
  return (
    <Link to={to} className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap text-[15px] text-[#9a6c12] hover:underline">
      {t('lister.home.viewAll')}
      <ArrowRightIcon className="size-4" />
    </Link>
  )
}

// L10's performance chart: one bar per open stage, the busiest in solid gold.
// One series, so no legend; each bar carries its count.
function StageBars({ leads }: { leads: Lead[] }) {
  const { t } = useTranslation()
  const counts = OPEN_STAGES.map((stage): [LeadStage, number] => [stage, leads.filter((lead) => lead.stage === stage).length])
  const top = Math.max(...counts.map(([, count]) => count))
  const scale = Math.max(4, Math.ceil(top / 4) * 4)
  const ticks = [scale, (scale * 3) / 4, scale / 2, scale / 4, 0]

  return (
    <div className="px-6 pt-6 pb-5">
      <div className="relative h-[220px]">
        {ticks.map((tick) => (
          <div key={tick} className="absolute inset-x-0 flex items-center gap-3" style={{ top: `${(1 - tick / scale) * 100}%` }}>
            <span className="w-6 -translate-y-1/2 text-right text-[11px] text-muted tabular-nums">{tick}</span>
            <span className="h-px flex-1 -translate-y-1/2 bg-mist/80" />
          </div>
        ))}
        <ul className="absolute inset-y-0 right-0 left-9 flex items-end justify-around gap-3">
          {counts.map(([stage, count]) => (
            <li key={stage} className="flex h-full w-full max-w-[64px] flex-col items-center justify-end" title={`${t(`lister.stages.${stage}`)}: ${count}`}>
              <span className="mb-1 text-[11px] font-medium text-navy tabular-nums">{count}</span>
              <span
                className={`w-full rounded-t-[4px] ${count === top && top > 0 ? 'bg-gold' : 'bg-gold/20'}`}
                style={{ height: `${(count / scale) * 100}%`, minHeight: count ? 4 : 2 }}
              />
            </li>
          ))}
        </ul>
      </div>
      <ul className="mt-2 ml-9 flex justify-around gap-3">
        {counts.map(([stage]) => (
          <li key={stage} className="w-full max-w-[64px] truncate text-center text-[11px] text-muted">
            {t(`lister.stagesShort.${stage}`)}
          </li>
        ))}
      </ul>
      <p className="sr-only">{counts.map(([stage, count]) => `${t(`lister.stages.${stage}`)}: ${count}`).join(', ')}</p>
    </div>
  )
}
