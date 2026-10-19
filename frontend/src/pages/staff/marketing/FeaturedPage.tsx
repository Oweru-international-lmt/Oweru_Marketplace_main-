import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import aerial from '../../../assets/photos/dar-aerial-720.webp'
import coast from '../../../assets/photos/dar-coast-720.webp'
import sunset from '../../../assets/photos/dar-sunset-720.webp'
import { Alert } from '../../../components/Alert'
import { BuildingIcon, CalendarIcon, ClockIcon, CloseIcon, ListIcon, MapPinIcon, MoreIcon, PlusIcon, SearchIcon, DashboardIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate, formatTshShort } from '../../../lib/format'
import { panelApi, type Featured } from '../../../lib/panelApi'
import { periodState, STATE_TONE, toLocalInput } from './period'
import { Chip, Panel } from './ui'

const PHOTOS = [aerial, coast, sunset]
type State = ReturnType<typeof periodState>
type Draft = { id?: string; version: number; listing_id: string; starts_at: string; ends_at: string; enabled: boolean }

// MAR-01, after M10: four count tiles, a filter row with a grid or list
// switch, then each featured listing as a photo card with its place, price,
// run dates and status.
export function FeaturedPage() {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('staff.marketing.featured.title'))
  const [rows, setRows] = useState<Featured[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [state, setState] = useState<'all' | State>('all')
  const [layout, setLayout] = useState<'grid' | 'list'>('grid')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [now, setNow] = useState(() => Date.now())

  const load = useCallback(() => {
    panelApi.featured().then(
      (loaded) => {
        setNow(Date.now())
        setRows(loaded)
      },
      (caught) => setError(errorMessage(t, caught)),
    )
  }, [t])

  useEffect(() => {
    load()
  }, [load])

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (rows ?? []).filter((row) => (state === 'all' || periodState(row, now) === state) && (!needle || `${row.listing_id} ${row.area}`.toLowerCase().includes(needle)))
  }, [rows, query, state, now])
  const tally = (value: State) => (rows ?? []).filter((row) => periodState(row, now) === value).length

  const tiles = [
    { key: 'live', icon: BuildingIcon, value: tally('live'), note: t('staff.marketing.featured.notes.live') },
    { key: 'scheduled', icon: CalendarIcon, value: tally('scheduled'), note: t('staff.marketing.featured.notes.scheduled') },
    { key: 'ended', icon: ClockIcon, value: tally('ended'), note: t('staff.marketing.featured.notes.ended') },
    { key: 'off', icon: CloseIcon, value: tally('off'), note: t('staff.marketing.featured.notes.off') },
  ] as const

  function newDraft(): Draft {
    const start = new Date()
    const end = new Date(start.getTime() + 14 * 86_400_000)
    return { version: 0, listing_id: '', starts_at: start.toISOString(), ends_at: end.toISOString(), enabled: true }
  }

  return (
    <div className="space-y-5">
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {tiles.map(({ key, icon: Icon, value, note }) => (
          <li key={key} className="rounded-[18px] border border-mist/80 bg-white px-5 py-4">
            <p className="flex items-center gap-2.5 text-[15px] text-navy">
              <span className="grid size-8 place-items-center rounded-lg border border-mist text-navy-soft"><Icon className="size-4" /></span>
              {t(`staff.marketing.featured.tiles.${key}`)}
            </p>
            <p className="mt-3 text-[34px] leading-none font-medium text-navy tabular-nums">{rows ? value : '-'}</p>
            <p className="mt-2 text-[13px] text-navy-soft">{note}</p>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        <label className="relative">
          <span className="sr-only">{t('staff.marketing.featured.search')}</span>
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('staff.marketing.featured.search')} className="h-10 w-64 rounded-lg bg-[#f1f2f4] pr-3 pl-9 text-[13.5px] outline-none placeholder:text-muted/80 focus:ring-2 focus:ring-gold/30" />
        </label>
        <select value={state} onChange={(event) => setState(event.target.value as typeof state)} aria-label={t('staff.marketing.featured.status')} className="h-10 rounded-lg border border-mist bg-white px-3 text-[13.5px] text-navy">
          {(['all', 'live', 'scheduled', 'ended', 'off'] as const).map((value) => <option key={value} value={value}>{t(`staff.marketing.featured.states.${value}`)}</option>)}
        </select>
        <span className="flex gap-1">
          <button type="button" aria-pressed={layout === 'grid'} aria-label={t('staff.marketing.featured.grid')} onClick={() => setLayout('grid')} className={`grid size-10 place-items-center rounded-lg border ${layout === 'grid' ? 'border-gold/60 bg-gold/10 text-[#9a6c12]' : 'border-mist text-navy-soft'}`}><DashboardIcon className="size-4" /></button>
          <button type="button" aria-pressed={layout === 'list'} aria-label={t('staff.marketing.featured.list')} onClick={() => setLayout('list')} className={`grid size-10 place-items-center rounded-lg border ${layout === 'list' ? 'border-gold/60 bg-gold/10 text-[#9a6c12]' : 'border-mist text-navy-soft'}`}><ListIcon className="size-4" /></button>
        </span>
        <button type="button" onClick={() => setDraft(newDraft())} className="ml-auto inline-flex h-10 items-center gap-2 rounded-lg bg-navy px-4 text-[14px] font-medium text-white hover:bg-navy-soft">
          <PlusIcon className="size-4" />
          {t('staff.marketing.featured.add')}
        </button>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      {rows !== null && shown.length === 0 ? (
        <Panel className="py-14 text-center text-[14px] text-muted">{t('staff.marketing.featured.empty')}</Panel>
      ) : (
        <ul className={layout === 'grid' ? 'grid gap-4 sm:grid-cols-2 xl:grid-cols-4' : 'space-y-3'}>
          {rows === null && [0, 1, 2, 3].map((index) => <li key={index} className="h-[300px] animate-pulse rounded-[20px] bg-paper" />)}
          {shown.map((row, index) => {
            const current = periodState(row, now)
            const [place, ...rest] = row.area.split(', ')
            return (
              <li key={row.id} className={`rounded-[20px] border border-mist/80 bg-white p-3 ${layout === 'list' ? 'flex items-center gap-4' : ''}`}>
                <div className={`relative overflow-hidden rounded-[14px] bg-paper ${layout === 'list' ? 'h-[90px] w-[140px] shrink-0' : 'h-[150px]'}`}>
                  <img src={row.cover_url ?? PHOTOS[index % PHOTOS.length]} alt="" className="size-full object-cover" />
                  <span className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-white/95 px-2.5 py-1 text-[12px] text-navy"><MapPinIcon className="size-3.5" />{rest[rest.length - 1] ?? place}</span>
                  <CardMenu
                    onEdit={() => setDraft({ id: row.id, version: row.version, listing_id: row.listing_id, starts_at: row.starts_at, ends_at: row.ends_at, enabled: row.enabled })}
                    onToggle={async () => {
                      try {
                        await panelApi.saveFeatured({ listing_id: row.listing_id, starts_at: row.starts_at, ends_at: row.ends_at, enabled: !row.enabled, version: row.version }, row.id)
                        load()
                      } catch (caught) {
                        setError(errorMessage(t, caught))
                      }
                    }}
                    enabled={row.enabled}
                  />
                </div>
                <div className={layout === 'list' ? 'min-w-0 flex-1' : 'px-1 pt-3'}>
                  <p className="flex items-start justify-between gap-2">
                    <span className="truncate text-[16px] font-medium text-navy">{t(`market.category.${row.category}`)}, {place}</span>
                    <span className="shrink-0 text-[16px] font-semibold text-navy">{formatTshShort(row.selling_price, i18n.language)}</span>
                  </p>
                  <p className="mt-1 flex items-center gap-1.5 text-[13px] text-navy-soft">
                    <CalendarIcon className="size-3.5" />
                    {formatShortDate(row.starts_at, i18n.language)} - {formatShortDate(row.ends_at, i18n.language)}
                  </p>
                  <p className="mt-3 flex items-center justify-between gap-2">
                    <Chip tone={STATE_TONE[current]}>{t(`staff.marketing.featured.states.${current}`)}</Chip>
                    <span className="truncate font-mono text-[11.5px] text-muted">{row.listing_id}</span>
                  </p>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      <AnimatePresence>
        {draft && (
          <FeaturedDrawer
            draft={draft}
            onClose={() => setDraft(null)}
            onSaved={() => {
              setDraft(null)
              load()
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function CardMenu({ onEdit, onToggle, enabled }: { onEdit: () => void; onToggle: () => void; enabled: boolean }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => !root.current?.contains(event.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  return (
    <div ref={root} className="absolute top-2 right-2">
      <button type="button" aria-label={t('staff.marketing.featured.actions')} aria-expanded={open} onClick={() => setOpen((value) => !value)} className="grid size-8 place-items-center rounded-lg bg-white text-navy shadow-sm">
        <MoreIcon className="size-4" />
      </button>
      {open && (
        <ul className="absolute top-full right-0 z-10 mt-1 w-44 overflow-hidden rounded-lg border border-mist bg-white py-1 text-[13.5px] shadow-lg">
          <li><button type="button" onClick={() => { setOpen(false); onEdit() }} className="block w-full px-3.5 py-2 text-left text-navy hover:bg-paper">{t('staff.marketing.featured.edit')}</button></li>
          <li><button type="button" onClick={() => { setOpen(false); onToggle() }} className="block w-full px-3.5 py-2 text-left text-navy hover:bg-paper">{enabled ? t('staff.marketing.featured.turnOff') : t('staff.marketing.featured.turnOn')}</button></li>
        </ul>
      )}
    </div>
  )
}

function FeaturedDrawer({ draft, onClose, onSaved }: { draft: Draft; onClose: () => void; onSaved: () => void }) {
  const { t } = useTranslation()
  const [values, setValues] = useState(draft)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function save() {
    setBusy(true)
    setError(null)
    try {
      await panelApi.saveFeatured({ listing_id: values.listing_id.trim(), starts_at: values.starts_at, ends_at: values.ends_at, enabled: values.enabled, version: values.version }, values.id)
      onSaved()
    } catch (caught) {
      setError(errorMessage(t, caught))
      setBusy(false)
    }
  }
  const field = 'mt-1.5 h-11 w-full rounded-lg border border-mist px-3 text-[14px] text-navy outline-none focus:border-gold'
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[1000] flex justify-end bg-navy/40" onClick={onClose}>
      <motion.form
        role="dialog"
        aria-modal="true"
        aria-labelledby="featured-title"
        initial={{ x: 40 }}
        animate={{ x: 0 }}
        exit={{ x: 40 }}
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault()
          void save()
        }}
        className="flex h-full w-full max-w-[420px] flex-col bg-white p-6"
      >
        <div className="flex items-center justify-between">
          <h2 id="featured-title" className="text-[19px] font-semibold text-navy">{values.id ? t('staff.marketing.featured.editTitle') : t('staff.marketing.featured.add')}</h2>
          <button type="button" onClick={onClose} aria-label={t('staff.marketing.featured.close')} className="grid size-9 place-items-center rounded-full hover:bg-paper"><CloseIcon className="size-4" /></button>
        </div>
        <label className="mt-6 block text-[14px] text-navy">
          {t('staff.marketing.featured.listing')}
          <input required value={values.listing_id} disabled={Boolean(values.id)} onChange={(event) => setValues({ ...values, listing_id: event.target.value })} placeholder="OWR-L-000012" className={`${field} font-mono disabled:bg-paper`} />
          <span className="mt-1 block text-[12px] text-muted">{t('staff.marketing.featured.listingHint')}</span>
        </label>
        <label className="mt-4 block text-[14px] text-navy">
          {t('staff.marketing.featured.starts')}
          <input type="datetime-local" required value={toLocalInput(values.starts_at)} onChange={(event) => setValues({ ...values, starts_at: new Date(event.target.value).toISOString() })} className={field} />
        </label>
        <label className="mt-4 block text-[14px] text-navy">
          {t('staff.marketing.featured.ends')}
          <input type="datetime-local" required value={toLocalInput(values.ends_at)} onChange={(event) => setValues({ ...values, ends_at: new Date(event.target.value).toISOString() })} className={field} />
        </label>
        <label className="mt-4 flex items-center gap-2.5 text-[14px] text-navy">
          <input type="checkbox" checked={values.enabled} onChange={(event) => setValues({ ...values, enabled: event.target.checked })} className="size-4 accent-[#c89128]" />
          {t('staff.marketing.featured.enabled')}
        </label>
        {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
        <div className="mt-auto flex justify-end gap-2 pt-6">
          <button type="button" onClick={onClose} className="h-11 rounded-lg border border-mist px-4 text-[14px] text-navy">{t('staff.marketing.featured.cancel')}</button>
          <button type="submit" disabled={busy} className="h-11 rounded-lg bg-navy px-5 text-[14px] font-medium text-white disabled:opacity-60">{busy ? t('staff.marketing.featured.saving') : t('staff.marketing.featured.save')}</button>
        </div>
      </motion.form>
    </motion.div>
  )
}
