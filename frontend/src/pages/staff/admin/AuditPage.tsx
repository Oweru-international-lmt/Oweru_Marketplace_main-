import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../../components/Alert'
import { FilterIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { adminApi, type AuditFilters, type AuditPage as Page, type AuditRow } from '../../../lib/adminApi'
import { errorMessage } from '../../../lib/errors'
import { Initials } from '../partners/ui'

// ADM-04. After R19: a filter line, then rows with the person, the record,
// the action as a coloured word, the type and the time; a row opens the
// before and after.

function verb(action: string) {
  const last = action.split('.').at(-1) ?? action
  if (/(created|approved|registered|published|confirmed|seeded|assigned|invited|sent|paid)$/.test(last)) return { word: last, tone: 'text-success' }
  if (/(deleted|revoked|suspended|deactivated|declined|cancelled|dismissed|rejected|failed)$/.test(last)) return { word: last, tone: 'text-danger' }
  if (/(accessed|viewed)$/.test(last)) return { word: last, tone: 'text-muted' }
  return { word: last, tone: 'text-[#3552a8]' }
}

function stamp(value: string, language: string) {
  const date = new Date(value)
  const locale = language.startsWith('sw') ? 'sw-TZ' : 'en-GB'
  return [new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short', year: 'numeric' }).format(date), new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(date)]
}

export function AuditPage() {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  useDocumentTitle(t('admin.audit.title'))
  const [filters, setFilters] = useState<AuditFilters>({ page: 1 })
  const [draft, setDraft] = useState({ q: '', action: '', date_from: '', date_to: '' })
  const [data, setData] = useState<Page | null>(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    adminApi.audit(filters).then(
      (result) => live && setData(result),
      (failure) => live && setError(errorMessage(t, failure)),
    )
    return () => {
      live = false
    }
  }, [filters, t])

  function apply(event: React.FormEvent) {
    event.preventDefault()
    setOpen(null)
    setFilters({ ...draft, page: 1 })
  }

  const page = filters.page ?? 1
  const input = 'h-9 rounded-lg border border-mist bg-white px-3 text-[13px] text-navy outline-none focus:border-gold'

  return (
    <div className="pb-10">
      <h1 className="text-[24px] font-semibold text-navy">{t('admin.audit.title')}</h1>
      <p className="mt-1 text-[13px] text-muted">{t('admin.audit.subtitle')}</p>

      <form onSubmit={apply} className="mt-5 flex flex-wrap items-center gap-2 rounded-xl border border-mist bg-white px-3 py-2.5">
        <FilterIcon className="size-4 text-muted" />
        <input aria-label={t('admin.audit.search')} placeholder={t('admin.audit.search')} value={draft.q} onChange={(event) => setDraft({ ...draft, q: event.target.value })} className={`${input} min-w-[180px] flex-1`} />
        <select aria-label={t('admin.audit.group')} value={draft.action} onChange={(event) => setDraft({ ...draft, action: event.target.value })} className={input}>
          <option value="">{t('admin.audit.anyGroup')}</option>
          {data?.groups.map((group) => <option key={group} value={`${group}.`}>{group.replace(/_/g, ' ')}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-[12px] text-muted">
          {t('admin.audit.from')}
          <input type="date" value={draft.date_from} onChange={(event) => setDraft({ ...draft, date_from: event.target.value })} className={input} />
        </label>
        <label className="flex items-center gap-1.5 text-[12px] text-muted">
          {t('admin.audit.to')}
          <input type="date" value={draft.date_to} onChange={(event) => setDraft({ ...draft, date_to: event.target.value })} className={input} />
        </label>
        <button type="submit" className="h-9 rounded-lg bg-gold px-4 text-[13px] font-semibold text-navy">{t('admin.audit.apply')}</button>
        {filters.actor && (
          <button type="button" onClick={() => setFilters({ ...filters, actor: undefined, page: 1 })} className="h-9 rounded-lg border border-mist px-3 text-[12px] text-navy">{t('admin.audit.clearPerson')}</button>
        )}
      </form>
      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}

      <div className="mt-4 overflow-hidden rounded-xl border border-mist bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-[13px]">
            <thead>
              <tr className="bg-[#f3f5f9] text-[12px] text-navy-soft">
                <th className="px-5 py-3 font-medium">{t('admin.audit.columns.person')}</th>
                <th className="px-3 py-3 font-medium">{t('admin.audit.columns.record')}</th>
                <th className="px-3 py-3 font-medium">{t('admin.audit.columns.action')}</th>
                <th className="px-3 py-3 font-medium">{t('admin.audit.columns.type')}</th>
                <th className="px-5 py-3 font-medium">{t('admin.audit.columns.time')}</th>
              </tr>
            </thead>
            <tbody>
              {data?.results.length === 0 && <tr><td colSpan={5} className="px-5 py-12 text-center text-muted">{t('admin.audit.empty')}</td></tr>}
              {data?.results.map((row, index) => (
                <AuditLine key={row.id} row={row} index={index} reduce={reduce} open={open === row.id} onToggle={() => setOpen(open === row.id ? null : row.id)} onPerson={(actor) => setFilters({ ...filters, actor, page: 1 })} language={i18n.language} />
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between gap-3 border-t border-mist px-5 py-3 text-[12px] text-muted">
          <span>{data ? t('admin.audit.showing', { count: data.results.length }) : ''}</span>
          <span className="flex items-center gap-3">
            <button type="button" disabled={page <= 1} onClick={() => setFilters({ ...filters, page: page - 1 })} className="font-medium text-[#3552a8] disabled:text-muted/60">{t('admin.audit.previous')}</button>
            <span>{t('admin.audit.page', { page })}</span>
            <button type="button" disabled={!data?.has_next} onClick={() => setFilters({ ...filters, page: page + 1 })} className="font-medium text-[#3552a8] disabled:text-muted/60">{t('admin.audit.next')}</button>
          </span>
        </div>
      </div>
    </div>
  )
}

function AuditLine({ row, index, reduce, open, onToggle, onPerson, language }: { row: AuditRow; index: number; reduce: boolean | null; open: boolean; onToggle: () => void; onPerson: (actor: string) => void; language: string }) {
  const { t } = useTranslation()
  const action = verb(row.action)
  const [day, time] = stamp(row.created_at, language)
  const keys = [...new Set([...Object.keys(row.before ?? {}), ...Object.keys(row.after ?? {})])]
  return (
    <>
      <motion.tr initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: Math.min(index, 15) * 0.02 }} onClick={onToggle} className={`cursor-pointer border-t border-mist/70 ${open ? 'bg-[#f6f1e6]' : 'hover:bg-paper/70'}`}>
        <td className="px-5 py-3">
          <span className="flex items-center gap-2.5">
            <Initials name={row.actor || t('admin.audit.system')} className="size-8" />
            <span>
              <span className="block font-medium text-navy">{row.actor || t('admin.audit.system')}</span>
              {row.actor_id && (
                <button type="button" onClick={(event) => { event.stopPropagation(); onPerson(row.actor_id as string) }} className="text-[11px] text-muted hover:text-[#9a6c12]">{t('admin.audit.onlyThem')}</button>
              )}
            </span>
          </span>
        </td>
        <td className="px-3 py-3"><span className="inline-block max-w-[150px] truncate rounded bg-paper px-2 py-0.5 font-mono text-[11px] text-navy-soft" title={row.entity_id}>{row.entity_id || '·'}</span></td>
        <td className={`px-3 py-3 text-[11px] font-semibold tracking-[0.08em] uppercase ${action.tone}`}>{action.word.replace(/_/g, ' ')}</td>
        <td className="px-3 py-3 text-navy-soft">{row.entity_type}</td>
        <td className="px-5 py-3 text-navy-soft tabular-nums">
          <span className="block">{day}</span>
          <span className="block text-[11px] text-muted">{time}</span>
        </td>
      </motion.tr>
      <AnimatePresence>
        {open && (
          <tr>
            <td colSpan={5} className="bg-[#fbf8f1] px-5 py-0">
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                <p className="pt-3 font-mono text-[11px] text-muted">{row.action}</p>
                {keys.length === 0 ? (
                  <p className="py-3 text-[12px] text-muted">{t('admin.audit.noDetail')}</p>
                ) : (
                  <table className="my-3 w-full text-[12px]">
                    <thead>
                      <tr className="text-muted">
                        <th className="w-48 py-1 text-left font-medium">{t('admin.audit.field')}</th>
                        <th className="py-1 text-left font-medium">{t('admin.audit.before')}</th>
                        <th className="py-1 text-left font-medium">{t('admin.audit.after')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {keys.map((key) => (
                        <tr key={key} className="border-t border-mist/60 align-top">
                          <td className="py-1.5 font-mono text-navy-soft">{key}</td>
                          <td className="py-1.5 font-mono break-all text-danger/80">{key in (row.before ?? {}) ? JSON.stringify(row.before[key]) : ''}</td>
                          <td className="py-1.5 font-mono break-all text-success">{key in (row.after ?? {}) ? JSON.stringify(row.after[key]) : ''}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </motion.div>
            </td>
          </tr>
        )}
      </AnimatePresence>
    </>
  )
}
