import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useState, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../../components/Alert'
import { BuildingIcon, CalendarIcon, ClockIcon, CloseIcon, DocumentIcon, ImageIcon, PlusIcon, UsersIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'
import { panelApi, type Content, type ContentInput, type Featured } from '../../../lib/panelApi'
import { isoDay, monthKey } from '../market/data'
import { periodState, STATE_TONE, toLocalInput } from './period'
import { Chip, Panel } from './ui'

type Draft = ContentInput & { id?: string }

function BannerIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <rect x="3" y="5" width="18" height="12" rx="2" />
      <path d="M7 21h10M7 9h6M7 13h4" />
    </svg>
  )
}

// MAR-02 and MAR-04, after M11: a block of counts split by hairlines, visits
// from content links by month with the busiest month marked, and the latest
// banners and pages; each is edited in Swahili and English side by side.
export function ContentPage() {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('staff.marketing.content.title'))
  const [rows, setRows] = useState<Content[] | null>(null)
  const [featured, setFeatured] = useState<Featured[]>([])
  const [visits, setVisits] = useState<{ month: string; value: number }[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [all, setAll] = useState(false)
  const [hover, setHover] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())

  const load = useCallback(() => {
    panelApi.content().then(
      (loaded) => {
        setNow(Date.now())
        setRows(loaded)
      },
      (caught) => setError(errorMessage(t, caught)),
    )
    panelApi.featured().then(setFeatured, () => setFeatured([]))
  }, [t])

  useEffect(() => {
    load()
  }, [load])

  // Visits that came through these banners' and pages' tagged links.
  useEffect(() => {
    if (!rows) return
    const tags = new Set(rows.map((row) => row.source_tag))
    const end = new Date()
    const start = new Date(end.getFullYear(), end.getMonth() - 11, 1)
    panelApi.panel({ start: isoDay(start), end: isoDay(end) }).then(
      (panel) => {
        const months = new Map<string, number>()
        for (let index = 0; index < 12; index++) months.set(monthKey(isoDay(new Date(start.getFullYear(), start.getMonth() + index, 15))), 0)
        for (const row of panel.rows) {
          if (row.kind !== 'ACTIVITY') continue
          let value = 0
          for (const [tag, count] of Object.entries(row.metrics.sources_view ?? {})) if (tags.has(tag)) value += count
          if (value) months.set(monthKey(row.day), (months.get(monthKey(row.day)) ?? 0) + value)
        }
        setVisits([...months.entries()].map(([month, value]) => ({ month, value })))
      },
      () => setVisits(null),
    )
  }, [rows])

  const tally = useMemo(() => {
    const list = rows ?? []
    const live = (kind: Content['kind']) => list.filter((row) => row.kind === kind && periodState(row, now) === 'live').length
    return {
      banners: live('BANNER'),
      pages: live('PAGE'),
      scheduled: list.filter((row) => periodState(row, now) === 'scheduled').length,
      ended: list.filter((row) => periodState(row, now) === 'ended').length,
      featured: featured.filter((row) => periodState(row, now) === 'live').length,
      visits: (visits ?? []).reduce((total, entry) => total + entry.value, 0),
    }
  }, [rows, featured, visits, now])

  const tiles = [
    { key: 'banners', icon: BannerIcon },
    { key: 'pages', icon: DocumentIcon },
    { key: 'scheduled', icon: CalendarIcon },
    { key: 'featured', icon: BuildingIcon },
    { key: 'visits', icon: UsersIcon },
    { key: 'ended', icon: ClockIcon },
  ] as const

  const month = (key: string) => new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { month: 'short' }).format(new Date(`${key}-01T00:00:00`))
  // Whole-number axis: the top is the next multiple of four.
  const maxVisits = Math.max(4, Math.ceil(Math.max(...(visits ?? []).map((entry) => entry.value), 0) / 4) * 4)
  const peak = (visits ?? []).reduce((best, entry, index, list) => (entry.value > (list[best]?.value ?? -1) ? index : best), 0)
  const active = hover ?? peak
  const listed = all ? rows ?? [] : (rows ?? []).slice(0, 5)

  function blank(kind: Content['kind']): Draft {
    const start = new Date()
    return { kind, slug: '', title_sw: '', title_en: '', body_sw: '', body_en: '', target_path: '/', source_tag: '', starts_at: start.toISOString(), ends_at: new Date(start.getTime() + 30 * 86_400_000).toISOString(), enabled: true, version: 0 }
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-[16px] font-medium text-navy"><BannerIcon className="size-4" />{t('staff.marketing.content.title')}</h1>
        <div className="flex gap-2">
          <button type="button" onClick={() => setDraft(blank('BANNER'))} className="inline-flex h-10 items-center gap-2 rounded-lg bg-navy px-4 text-[14px] font-medium text-white"><PlusIcon className="size-4" />{t('staff.marketing.content.addBanner')}</button>
          <button type="button" onClick={() => setDraft(blank('PAGE'))} className="inline-flex h-10 items-center gap-2 rounded-lg border border-mist bg-white px-4 text-[14px] text-navy"><PlusIcon className="size-4" />{t('staff.marketing.content.addPage')}</button>
        </div>
      </header>

      {error && <Alert tone="error">{error}</Alert>}

      <Panel className="overflow-hidden">
        <ul className="grid sm:grid-cols-2 lg:grid-cols-3">
          {tiles.map(({ key, icon: Icon }, index) => (
            <li key={key} className={`flex items-center gap-4 px-6 py-5 ${index % 3 ? 'lg:border-l' : ''} ${index >= 3 ? 'lg:border-t' : ''} border-mist max-lg:border-b`}>
              <span className="grid size-12 shrink-0 place-items-center rounded-xl border border-mist text-navy"><Icon className="size-5" /></span>
              <span>
                <span className="block text-[13.5px] text-navy-soft">{t(`staff.marketing.content.tiles.${key}`)}</span>
                <span className="block text-[22px] font-medium text-navy tabular-nums">{rows ? tally[key].toLocaleString() : '-'}</span>
              </span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel className="px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[18px] font-medium text-navy">{t('staff.marketing.content.visits')}</h2>
          <span className="inline-flex h-9 items-center rounded-lg border border-mist px-3 text-[13px] text-navy-soft">{t('staff.marketing.content.lastYear')}</span>
        </div>
        {visits === null ? (
          <p className="py-12 text-center text-[13.5px] text-muted">{t('staff.marketing.content.noVisits')}</p>
        ) : (
          <div className="relative mt-4 grid h-[260px] grid-cols-[28px_1fr] gap-2">
            <div className="flex flex-col justify-between pb-6 text-right text-[11px] text-muted tabular-nums">
              {[1, 0.75, 0.5, 0.25, 0].map((share) => <span key={share}>{Math.round(share * maxVisits)}</span>)}
            </div>
            <ul className="relative flex items-end gap-2 border-l border-dashed border-mist pb-6 pl-2" onMouseLeave={() => setHover(null)}>
              {visits.map((entry, index) => (
                <li key={entry.month} className="relative flex h-full flex-1 flex-col items-center justify-end" onMouseEnter={() => setHover(index)}>
                  {index === active && entry.value > 0 && (
                    <span className="absolute z-10 rounded-lg border border-mist bg-white px-2.5 py-1.5 text-[12px] whitespace-nowrap text-navy shadow-md" style={{ bottom: `calc(${(entry.value / maxVisits) * 100}% + 4px)` }}>
                      <span className="block font-medium">{month(entry.month)}</span>
                      <span className="flex items-center gap-1.5"><span className="size-2 rounded-sm bg-gold" />{t('staff.marketing.content.visitCount', { count: entry.value })}</span>
                    </span>
                  )}
                  <span
                    className={`w-full max-w-[52px] rounded-t-md ${index === active ? 'bg-[radial-gradient(#fff_1px,transparent_1px)] bg-gold [background-size:5px_5px]' : 'bg-[#e8ebf2]'}`}
                    style={{ height: `${Math.max((entry.value / maxVisits) * 100, 3)}%` }}
                  />
                  <span className="absolute -bottom-6 text-[12px] text-navy-soft">{month(entry.month)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Panel>

      <Panel className="px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[18px] font-medium text-navy">{t('staff.marketing.content.latest')}</h2>
          <button type="button" onClick={() => setAll((value) => !value)} className="text-[15px] text-[#9a6c12] hover:underline">{all ? t('staff.marketing.content.showLess') : t('staff.market.viewAll')}</button>
        </div>
        <ul className="mt-3 space-y-2">
          {rows === null && [0, 1].map((index) => <li key={index} className="h-[66px] animate-pulse rounded-xl bg-paper" />)}
          {rows !== null && rows.length === 0 && <li className="py-10 text-center text-[14px] text-muted">{t('staff.marketing.content.empty')}</li>}
          {listed.map((row) => {
            const state = periodState(row, now)
            return (
              <li key={row.id}>
                <button type="button" onClick={() => setDraft({ ...row })} className="grid w-full grid-cols-[48px_minmax(0,1fr)_auto] items-center gap-4 rounded-xl bg-[#f6f6f8] px-3 py-3 text-left hover:bg-paper sm:grid-cols-[48px_minmax(0,1fr)_160px_110px]">
                  <span className="grid size-12 place-items-center rounded-lg bg-white text-navy">{row.kind === 'BANNER' ? <ImageIcon className="size-5" /> : <DocumentIcon className="size-5" />}</span>
                  <span className="min-w-0">
                    <span className="block truncate text-[15px] text-navy">{i18n.language === 'en' ? row.title_en : row.title_sw}</span>
                    <span className="block truncate text-[12.5px] text-navy-soft">{t(`staff.marketing.content.kinds.${row.kind}`)} · <span className="font-mono">{row.source_tag}</span></span>
                  </span>
                  <span className="hidden text-[12.5px] text-navy-soft sm:block">
                    <span className="block text-[11.5px] text-muted">{t('staff.marketing.content.runs')}</span>
                    {formatShortDate(row.starts_at, i18n.language)} - {formatShortDate(row.ends_at, i18n.language)}
                  </span>
                  <Chip tone={STATE_TONE[state]}>{t(`staff.marketing.featured.states.${state}`)}</Chip>
                </button>
              </li>
            )
          })}
        </ul>
      </Panel>

      <AnimatePresence>
        {draft && (
          <ContentDrawer
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

function ContentDrawer({ draft, onClose, onSaved }: { draft: Draft; onClose: () => void; onSaved: () => void }) {
  const { t } = useTranslation()
  const [values, setValues] = useState<Draft>(draft)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setValues((current) => ({ ...current, [key]: value }))

  async function save() {
    setBusy(true)
    setError(null)
    const { id, ...input } = values
    try {
      await panelApi.saveContent({ ...input, slug: input.slug.trim(), source_tag: input.source_tag.trim() }, id)
      onSaved()
    } catch (caught) {
      setError(errorMessage(t, caught))
      setBusy(false)
    }
  }

  const field = 'mt-1.5 w-full rounded-lg border border-mist px-3 text-[14px] text-navy outline-none focus:border-gold'
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[1000] flex justify-end bg-navy/40" onClick={onClose}>
      <motion.form
        role="dialog"
        aria-modal="true"
        aria-labelledby="content-title"
        initial={{ x: 40 }}
        animate={{ x: 0 }}
        exit={{ x: 40 }}
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault()
          void save()
        }}
        className="flex h-full w-full max-w-[760px] flex-col overflow-y-auto bg-white p-6"
      >
        <div className="flex items-center justify-between">
          <h2 id="content-title" className="text-[19px] font-semibold text-navy">{t(values.id ? 'staff.marketing.content.edit' : values.kind === 'BANNER' ? 'staff.marketing.content.addBanner' : 'staff.marketing.content.addPage')}</h2>
          <button type="button" onClick={onClose} aria-label={t('staff.marketing.featured.close')} className="grid size-9 place-items-center rounded-full hover:bg-paper"><CloseIcon className="size-4" /></button>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {(['sw', 'en'] as const).map((lang) => (
            <fieldset key={lang} className="rounded-xl border border-mist p-4">
              <legend className="px-1 text-[13px] font-semibold text-navy">{t(`staff.marketing.composer.languages.${lang}`)}</legend>
              <label className="block text-[13.5px] text-navy">
                {t('staff.marketing.content.fields.title')}
                <input required maxLength={200} value={lang === 'sw' ? values.title_sw : values.title_en} onChange={(event) => set(lang === 'sw' ? 'title_sw' : 'title_en', event.target.value)} className={`${field} h-11`} />
              </label>
              <label className="mt-3 block text-[13.5px] text-navy">
                {t('staff.marketing.content.fields.body')}
                <textarea required rows={6} maxLength={10000} value={lang === 'sw' ? values.body_sw : values.body_en} onChange={(event) => set(lang === 'sw' ? 'body_sw' : 'body_en', event.target.value)} className={`${field} py-2.5`} />
              </label>
            </fieldset>
          ))}
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-[13.5px] text-navy">
            {t('staff.marketing.content.fields.kind')}
            <select value={values.kind} onChange={(event) => set('kind', event.target.value as Content['kind'])} className={`${field} h-11 bg-white`}>
              <option value="BANNER">{t('staff.marketing.content.kinds.BANNER')}</option>
              <option value="PAGE">{t('staff.marketing.content.kinds.PAGE')}</option>
            </select>
          </label>
          <label className="block text-[13.5px] text-navy">
            {t('staff.marketing.content.fields.slug')}
            <input required maxLength={50} value={values.slug} onChange={(event) => set('slug', event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))} className={`${field} h-11 font-mono`} />
          </label>
          <label className="block text-[13.5px] text-navy">
            {t('staff.marketing.content.fields.link')}
            <input required value={values.target_path} onChange={(event) => set('target_path', event.target.value)} placeholder="/listings" className={`${field} h-11`} />
          </label>
          <label className="block text-[13.5px] text-navy">
            {t('staff.marketing.composer.tag')}
            <input required maxLength={100} value={values.source_tag} onChange={(event) => set('source_tag', event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))} className={`${field} h-11 font-mono`} />
          </label>
          <label className="block text-[13.5px] text-navy">
            {t('staff.marketing.featured.starts')}
            <input type="datetime-local" required value={toLocalInput(values.starts_at)} onChange={(event) => set('starts_at', new Date(event.target.value).toISOString())} className={`${field} h-11`} />
          </label>
          <label className="block text-[13.5px] text-navy">
            {t('staff.marketing.featured.ends')}
            <input type="datetime-local" required value={toLocalInput(values.ends_at)} onChange={(event) => set('ends_at', new Date(event.target.value).toISOString())} className={`${field} h-11`} />
          </label>
        </div>
        <label className="mt-4 flex items-center gap-2.5 text-[14px] text-navy">
          <input type="checkbox" checked={values.enabled} onChange={(event) => set('enabled', event.target.checked)} className="size-4 accent-[#c89128]" />
          {t('staff.marketing.featured.enabled')}
        </label>
        <p className="mt-3 text-[12px] text-muted">{t('staff.marketing.composer.wording')}</p>
        {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
        <div className="mt-auto flex justify-end gap-2 pt-6">
          <button type="button" onClick={onClose} className="h-11 rounded-lg border border-mist px-4 text-[14px] text-navy">{t('staff.marketing.featured.cancel')}</button>
          <button type="submit" disabled={busy} className="h-11 rounded-lg bg-navy px-5 text-[14px] font-medium text-white disabled:opacity-60">{busy ? t('staff.marketing.featured.saving') : t('staff.marketing.featured.save')}</button>
        </div>
      </motion.form>
    </motion.div>
  )
}
