import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/Alert'
import { ChevronDownIcon, CloseIcon, FilterIcon, SearchIcon, SortIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { whatsappTo } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { digitsOnly, formatNumber, formatShortDate } from '../../lib/format'
import { listerApi, NEXT_STAGE, type Lead, type LeadStage } from '../../lib/listerApi'
import { loadListingRows, rowTitle, type ListingRow } from './rows'
import { Avatar, RowMenu, StagePill, type MenuItem } from './ui'

type Action = { kind: 'move'; lead: Lead; stage: LeadStage } | { kind: 'followUp'; lead: Lead }
const STAGES: LeadStage[] = ['NEW', 'CONTACTED', 'VIEWING', 'NEGOTIATION', 'CLOSING', 'WON', 'LOST']

// After L13: the title, a search box on the left and Filter plus "Newest to
// oldest" on the right, then one white table with initials avatars, small
// outlined stage pills and a kebab of actions on every row.
export function EnquiriesPage() {
  const { t, i18n } = useTranslation()
  const [leads, setLeads] = useState<Lead[] | null>(null)
  const [rows, setRows] = useState<ListingRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [stage, setStage] = useState<LeadStage | ''>('')
  const [newest, setNewest] = useState(true)
  const [action, setAction] = useState<Action | null>(null)
  useDocumentTitle(t('lister.enquiries.title'))

  useEffect(() => {
    let live = true
    listerApi
      .leads()
      .then((loaded) => live && setLeads(loaded))
      .catch((caught) => live && setError(errorMessage(t, caught)))
    loadListingRows().then((loaded) => live && setRows(loaded), () => undefined)
    return () => {
      live = false
    }
  }, [t])

  const titleFor = (listingId: string) => {
    const row = rows.find((item) => item.listing.listing_id === listingId)
    return row ? rowTitle(t, row) : listingId
  }

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (leads ?? [])
      .filter((lead) => (!stage || lead.stage === stage) && (!needle || `${lead.buyer_name} ${lead.buyer_whatsapp} ${lead.listing_id}`.toLowerCase().includes(needle)))
      .sort((a, b) => (newest ? b.created_at.localeCompare(a.created_at) : a.created_at.localeCompare(b.created_at)))
  }, [leads, query, stage, newest])

  function replace(updated: Lead) {
    setLeads((current) => current?.map((lead) => (lead.id === updated.id ? updated : lead)) ?? null)
  }

  function actions(lead: Lead): MenuItem[] {
    const items: MenuItem[] = [
      {
        label: t('lister.enquiries.whatsapp'),
        onSelect: () => window.open(whatsappTo(lead.buyer_whatsapp, t('lister.enquiries.greeting', { name: lead.buyer_name, listing: titleFor(lead.listing_id) })), '_blank', 'noopener,noreferrer'),
      },
    ]
    const next = NEXT_STAGE[lead.stage]
    if (next) items.push({ label: t('lister.enquiries.moveTo', { stage: t(`lister.stages.${next}`) }), onSelect: () => setAction({ kind: 'move', lead, stage: next }) })
    if (lead.stage !== 'WON' && lead.stage !== 'LOST') {
      items.push({ label: t('lister.enquiries.followUp'), onSelect: () => setAction({ kind: 'followUp', lead }) })
      items.push({ label: t('lister.enquiries.markLost'), onSelect: () => setAction({ kind: 'move', lead, stage: 'LOST' }), tone: 'danger' })
    }
    return items
  }

  const columns = ['name', 'source', 'created', 'followUp', 'stage', 'listing'] as const

  return (
    <div>
      <h1 className="mb-6 text-[24px] font-medium text-navy">{t('lister.enquiries.title')}</h1>
      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <label className="relative block w-full sm:w-[282px]">
          <span className="sr-only">{t('lister.enquiries.search')}</span>
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-navy-soft" />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('lister.enquiries.search')}
            className="h-9 w-full rounded-md border border-mist bg-white pr-3 pl-9 text-[14px] text-navy outline-none placeholder:text-navy-soft focus:border-gold focus:ring-2 focus:ring-gold/20"
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <label className="relative inline-flex items-center">
            <span className="sr-only">{t('lister.enquiries.filter')}</span>
            <FilterIcon className="pointer-events-none absolute left-3.5 size-4 text-navy-soft" />
            <select
              value={stage}
              onChange={(event) => setStage(event.target.value as LeadStage | '')}
              className="h-9 appearance-none rounded-md border border-mist bg-white pr-9 pl-10 text-[14px] text-navy outline-none hover:border-navy-soft/40 focus:border-gold"
            >
              <option value="">{t('lister.enquiries.filter')}</option>
              {STAGES.map((value) => (
                <option key={value} value={value}>
                  {t(`lister.stages.${value}`)}
                </option>
              ))}
            </select>
            <ChevronDownIcon className="pointer-events-none absolute right-3 size-4 text-navy-soft" />
          </label>
          <button
            type="button"
            onClick={() => setNewest((value) => !value)}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-mist bg-white px-3.5 text-[14px] text-navy hover:border-navy-soft/40"
          >
            <SortIcon className="size-4 text-navy-soft" />
            {newest ? t('lister.enquiries.newest') : t('lister.enquiries.oldest')}
            <ChevronDownIcon className="size-4 text-navy-soft" />
          </button>
        </div>
      </div>

      <div className="hidden overflow-visible rounded-lg border border-mist bg-white md:block">
        <table className="w-full text-left">
          <caption className="sr-only">{t('lister.enquiries.title')}</caption>
          <thead>
            <tr className="border-b border-mist">
              {columns.map((column) => (
                <th key={column} scope="col" className="px-5 py-4 text-[13px] font-normal text-navy-soft first:pl-6">
                  {t(`lister.enquiries.columns.${column}`)}
                </th>
              ))}
              <th scope="col" className="w-14">
                <span className="sr-only">{t('lister.listings.actions')}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {leads === null &&
              [0, 1, 2].map((item) => (
                <tr key={item} className="border-b border-mist last:border-0">
                  <td colSpan={7} className="px-6 py-4">
                    <div className="h-9 animate-pulse rounded bg-paper" />
                  </td>
                </tr>
              ))}
            {leads !== null && shown.length === 0 && (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-sm text-muted">
                  {leads.length === 0 ? t('lister.enquiries.empty') : t('lister.listings.noMatch')}
                </td>
              </tr>
            )}
            {shown.map((lead) => (
              <tr key={lead.id} className="border-b border-mist text-[15px] text-navy last:border-0">
                <td className="py-3.5 pr-5 pl-6">
                  <span className="flex items-center gap-3">
                    <Avatar name={lead.buyer_name} className="size-11 text-[15px]" />
                    <span className="min-w-0">
                      <span className="block truncate">{lead.buyer_name}</span>
                      <span className="block text-[12px] text-muted tabular-nums">{lead.buyer_whatsapp}</span>
                    </span>
                  </span>
                </td>
                <td className="px-5 py-3.5 whitespace-nowrap">{t(`lister.sources.${lead.source}`)}</td>
                <td className="px-5 py-3.5 whitespace-nowrap tabular-nums">{formatShortDate(lead.created_at, i18n.language)}</td>
                <td className="px-5 py-3.5 whitespace-nowrap tabular-nums">{lead.follow_up_at ? formatShortDate(lead.follow_up_at, i18n.language) : <span className="text-muted">-</span>}</td>
                <td className="px-5 py-3.5">
                  <StagePill stage={lead.stage} />
                </td>
                <td className="max-w-[220px] truncate px-5 py-3.5">{titleFor(lead.listing_id)}</td>
                <td className="pr-4">
                  <RowMenu label={t('lister.listings.actions')} items={actions(lead)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Phones: the same rows as cards. */}
      <ul className="space-y-3 md:hidden">
        {leads !== null && shown.length === 0 && (
          <li className="rounded-lg border border-mist bg-white px-5 py-10 text-center text-sm text-muted">
            {leads.length === 0 ? t('lister.enquiries.empty') : t('lister.listings.noMatch')}
          </li>
        )}
        {shown.map((lead) => (
          <li key={lead.id} className="rounded-lg border border-mist bg-white p-4">
            <div className="flex items-start gap-3">
              <Avatar name={lead.buyer_name} className="size-10 text-[14px]" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-[15px] text-navy">{lead.buyer_name}</p>
                  <StagePill stage={lead.stage} />
                </div>
                <p className="mt-0.5 truncate text-[13px] text-navy-soft">{titleFor(lead.listing_id)}</p>
                <p className="mt-1.5 text-[12px] text-muted">
                  {t(`lister.sources.${lead.source}`)} · {formatShortDate(lead.created_at, i18n.language)}
                  {lead.follow_up_at && ` · ${t('lister.enquiries.followUpOn', { date: formatShortDate(lead.follow_up_at, i18n.language) })}`}
                </p>
              </div>
              <RowMenu label={t('lister.listings.actions')} items={actions(lead)} />
            </div>
          </li>
        ))}
      </ul>

      <AnimatePresence>
        {action && (
          <ActionDialog
            key={`${action.kind}-${action.lead.id}`}
            action={action}
            onClose={() => setAction(null)}
            onDone={(updated) => {
              replace(updated)
              setAction(null)
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function ActionDialog({ action, onClose, onDone }: { action: Action; onClose: () => void; onDone: (lead: Lead) => void }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [price, setPrice] = useState('')
  const [date, setDate] = useState(() => action.lead.follow_up_at?.slice(0, 10) ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lost = action.kind === 'move' && action.stage === 'LOST'
  const closing = action.kind === 'move' && action.stage === 'CLOSING'

  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [onClose])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if ((lost && !reason.trim()) || (closing && !price) || (action.kind === 'followUp' && !date)) {
      setError(t('validation.required'))
      return
    }
    setBusy(true)
    try {
      const updated =
        action.kind === 'followUp'
          ? await listerApi.followUp(action.lead.id, new Date(`${date}T09:00:00`).toISOString())
          : await listerApi.moveLead(action.lead.id, action.stage, reason.trim(), closing ? price : undefined)
      onDone(updated)
    } catch (caught) {
      setBusy(false)
      setError(errorMessage(t, caught))
    }
  }

  const title = action.kind === 'followUp' ? t('lister.enquiries.followUpTitle') : t('lister.enquiries.moveTitle', { stage: t(`lister.stages.${action.stage}`) })

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4" role="dialog" aria-modal="true" aria-labelledby="lead-action-title">
      <motion.div className="absolute inset-0 bg-navy/50 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.form
        onSubmit={(event) => void submit(event)}
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 16, scale: 0.98 }}
        className="relative w-full max-w-md rounded-[12px] bg-white p-6 shadow-lift"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="lead-action-title" className="text-lg font-semibold text-navy">
              {title}
            </h2>
            <p className="mt-1 text-sm text-muted">{action.lead.buyer_name}</p>
          </div>
          <button type="button" onClick={onClose} aria-label={t('lister.enquiries.cancel')} className="grid size-9 place-items-center rounded-[8px] border border-mist text-muted hover:text-navy">
            <CloseIcon className="size-4" />
          </button>
        </div>
        <div className="mt-5 space-y-4">
          {action.kind === 'followUp' && (
            <Labelled id="lead-date" label={t('lister.enquiries.followUpDate')}>
              <input id="lead-date" type="date" autoFocus value={date} onChange={(event) => setDate(event.target.value)} className="h-11 w-full rounded-[8px] border border-mist px-3 text-sm text-navy outline-none focus:border-gold" />
            </Labelled>
          )}
          {closing && (
            <Labelled id="lead-price" label={t('lister.enquiries.finalPrice')} hint={t('lister.enquiries.finalPriceHint')}>
              <input
                id="lead-price"
                inputMode="numeric"
                autoFocus
                value={price ? formatNumber(price, 'en') : ''}
                onChange={(event) => setPrice(digitsOnly(event.target.value))}
                className="h-11 w-full rounded-[8px] border border-mist px-3 text-sm text-navy outline-none focus:border-gold"
              />
            </Labelled>
          )}
          {action.kind === 'move' && !closing && (
            <Labelled id="lead-reason" label={lost ? t('lister.enquiries.lostReason') : t('lister.enquiries.note')}>
              <textarea id="lead-reason" rows={3} autoFocus value={reason} onChange={(event) => setReason(event.target.value)} className="block w-full rounded-[8px] border border-mist px-3 py-2.5 text-sm text-navy outline-none focus:border-gold" />
            </Labelled>
          )}
          {error && <Alert tone="error">{error}</Alert>}
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="h-11 rounded-[8px] border border-mist px-5 text-sm font-medium text-navy hover:border-navy/30">
            {t('lister.enquiries.cancel')}
          </button>
          <button type="submit" disabled={busy} className={`h-11 rounded-[8px] px-5 text-sm font-semibold disabled:opacity-60 ${lost ? 'bg-danger text-white' : 'bg-gold text-navy hover:bg-gold-light'}`}>
            {busy ? t('lister.enquiries.saving') : t('lister.enquiries.confirm')}
          </button>
        </div>
      </motion.form>
    </div>
  )
}

function Labelled({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-navy">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  )
}
