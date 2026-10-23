import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../../components/Alert'
import { CheckIcon, PlusIcon, TrashIcon } from '../../../components/icons'
import { adminApi, type Band, type Examples, type RateTable } from '../../../lib/adminApi'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'

// PAY-01 and D5: Management drafts a new version of the commission table and
// publishes it. Published versions never change; deals keep the version
// they were priced with.

type Row = { upper: string; oweru: string }

const percent = (rate: string) => String(Number((Number(rate) * 100).toFixed(4)))
const rate = (value: string) => (Number(value) / 100).toFixed(6)
const shillings = (value: string, language: string) => Number(value).toLocaleString(language.startsWith('sw') ? 'sw-TZ' : 'en-GB')

function toRows(bands: Band[]): Row[] {
  return bands.map((band) => ({ upper: band.upper ?? '', oweru: percent(band.oweru_rate) }))
}

function toBands(rows: Row[], total: string): Band[] {
  let lower = 0
  return rows.map((row, index) => {
    const last = index === rows.length - 1
    const band: Band = { lower: String(lower), upper: last ? null : row.upper, oweru_rate: rate(row.oweru), agent_rate: (Number(total) - Number(rate(row.oweru))).toFixed(6) }
    lower = Number(row.upper) + 1
    return band
  })
}

export function RateEditor({ examples }: { examples: Examples }) {
  const { t, i18n } = useTranslation()
  const [versions, setVersions] = useState<RateTable[] | null>(null)
  const [editing, setEditing] = useState<{ id?: string; version: number; total: string; rows: Row[] } | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState('')

  useEffect(() => {
    adminApi.rateVersions().then(setVersions, (failure) => setError(errorMessage(t, failure)))
  }, [t])

  const current = versions?.find((row) => row.current) ?? null
  const draft = versions?.find((row) => !row.published_at) ?? null
  const nextVersion = Math.max(0, ...(versions ?? []).map((row) => row.version)) + 1

  function startFrom(source: { total_rate: string; bands: Band[] }, id?: string, version = nextVersion) {
    setSaved('')
    setError('')
    setEditing({ id, version, total: percent(source.total_rate), rows: toRows(source.bands) })
  }

  async function save(publish: boolean) {
    if (!editing) return
    const total = rate(editing.total)
    const bands = toBands(editing.rows, total)
    setBusy(true)
    setError('')
    try {
      const table = await adminApi.saveRateDraft({ version: editing.version, total_rate: total, bands }, editing.id)
      if (publish) await adminApi.publishRate(table.id)
      const fresh = await adminApi.rateVersions()
      setVersions(fresh)
      setSaved(publish ? t('admin.rates.published', { version: table.version }) : t('admin.rates.draftSaved', { version: table.version }))
      setEditing(publish ? null : { ...editing, id: table.id })
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  if (!versions) return <div className="h-40 animate-pulse rounded-xl bg-paper" />

  const problems = editing ? validate(editing, t) : []

  return (
    <div className="space-y-5">
      {error && <Alert tone="error">{error}</Alert>}
      {saved && <Alert tone="success">{saved}</Alert>}

      {!editing && (
        <>
          <div>
            <p className="text-[13px] font-medium text-navy">{current ? t('admin.rates.current', { version: current.version, date: current.published_at ? formatShortDate(current.published_at, i18n.language) : '' }) : t('admin.rates.none')}</p>
            {current && <BandTable bands={current.bands} total={current.total_rate} />}
          </div>
          <div className="flex flex-wrap gap-2">
            {draft ? (
              <button type="button" onClick={() => startFrom(draft, draft.id, draft.version)} className="h-10 rounded-[6px] bg-gold px-4 text-[13px] font-semibold text-navy">{t('admin.rates.continueDraft', { version: draft.version })}</button>
            ) : (
              <button type="button" onClick={() => startFrom(current ?? examples.rate_table)} className="h-10 rounded-[6px] bg-gold px-4 text-[13px] font-semibold text-navy">{t('admin.rates.newDraft')}</button>
            )}
          </div>
        </>
      )}

      <AnimatePresence>
        {editing && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="rounded-xl border border-gold/40 bg-[#fffaf0] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-[14px] font-semibold text-navy">{t('admin.rates.editing', { version: editing.version })}</p>
              <label className="flex items-center gap-2 text-[13px] text-navy-soft">
                {t('admin.rates.total')}
                <input inputMode="decimal" value={editing.total} onChange={(event) => setEditing({ ...editing, total: event.target.value })} className="h-9 w-20 rounded-lg border border-mist bg-white px-2 text-right text-[13px] text-navy" />
                %
              </label>
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[560px] text-[13px]">
                <thead>
                  <tr className="text-left text-[12px] text-muted">
                    <th className="py-2 font-medium">{t('admin.rates.from')}</th>
                    <th className="py-2 font-medium">{t('admin.rates.to')}</th>
                    <th className="py-2 font-medium">{t('admin.rates.oweru')}</th>
                    <th className="py-2 font-medium">{t('admin.rates.agent')}</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {editing.rows.map((row, index) => {
                    const last = index === editing.rows.length - 1
                    const lower = index === 0 ? 0 : Number(editing.rows[index - 1].upper) + 1
                    const agent = Number(editing.total) - Number(row.oweru)
                    return (
                      <tr key={index} className="border-t border-mist/70">
                        <td className="py-2 pr-3 text-navy-soft tabular-nums">{`TSh ${shillings(String(lower || 0), i18n.language)}`}</td>
                        <td className="py-2 pr-3">
                          {last ? (
                            <span className="text-navy-soft">{t('admin.rates.andAbove')}</span>
                          ) : (
                            <input inputMode="numeric" value={row.upper} onChange={(event) => setEditing({ ...editing, rows: editing.rows.map((item, position) => (position === index ? { ...item, upper: event.target.value.replace(/\D/g, '') } : item)) })} className="h-9 w-40 rounded-lg border border-mist bg-white px-2 text-right text-[13px] text-navy tabular-nums" />
                          )}
                        </td>
                        <td className="py-2 pr-3">
                          <span className="inline-flex items-center gap-1">
                            <input inputMode="decimal" value={row.oweru} onChange={(event) => setEditing({ ...editing, rows: editing.rows.map((item, position) => (position === index ? { ...item, oweru: event.target.value } : item)) })} className="h-9 w-20 rounded-lg border border-mist bg-white px-2 text-right text-[13px] text-navy" />
                            %
                          </span>
                        </td>
                        <td className={`py-2 pr-3 tabular-nums ${agent < 0 ? 'text-danger' : 'text-navy'}`}>{`${Number(agent.toFixed(4))}%`}</td>
                        <td className="py-2 text-right">
                          {editing.rows.length > 1 && (
                            <button type="button" aria-label={t('admin.rates.removeBand')} onClick={() => setEditing({ ...editing, rows: editing.rows.filter((_, position) => position !== index) })} className="grid size-8 place-items-center rounded-full text-muted hover:bg-danger-soft hover:text-danger">
                              <TrashIcon className="size-4" />
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-[12px]">
              <button type="button" onClick={() => setEditing({ ...editing, rows: [...editing.rows.slice(0, -1), { upper: '', oweru: editing.rows.at(-1)?.oweru ?? '0' }, editing.rows.at(-1) ?? { upper: '', oweru: '0' }] })} className="inline-flex items-center gap-1 font-medium text-[#9a6c12]">
                <PlusIcon className="size-3.5" />
                {t('admin.rates.addBand')}
              </button>
              <button type="button" onClick={() => setEditing({ ...editing, total: percent(examples.rate_table.total_rate), rows: toRows(examples.rate_table.bands) })} className="font-medium text-[#3552a8]">{t('admin.rates.useExample')}</button>
            </div>
            {problems.length > 0 && (
              <ul className="mt-3 space-y-1 text-[12px] text-danger">
                {problems.map((problem) => <li key={problem}>{problem}</li>)}
              </ul>
            )}
            <p className="mt-3 text-[12px] text-muted">{t('admin.rates.publishNote')}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => setEditing(null)} className="h-10 rounded-[6px] border border-mist bg-white px-4 text-[13px] text-navy">{t('admin.cancel')}</button>
              <button type="button" disabled={busy || problems.length > 0} onClick={() => void save(false)} className="h-10 rounded-[6px] border border-navy px-4 text-[13px] font-medium text-navy disabled:opacity-50">{t('admin.rates.saveDraft')}</button>
              <button type="button" disabled={busy || problems.length > 0} onClick={() => void save(true)} className="inline-flex h-10 items-center gap-2 rounded-[6px] bg-gold px-4 text-[13px] font-semibold text-navy disabled:opacity-50">
                <CheckIcon className="size-4" />
                {t('admin.rates.publish')}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div>
        <p className="text-[13px] font-medium text-navy">{t('admin.rates.history')}</p>
        <ul className="mt-2 divide-y divide-mist/70 rounded-xl border border-mist">
          {versions.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-[13px]">
              <span className="font-semibold text-navy">{t('admin.rates.version', { version: row.version })}</span>
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${row.current ? 'bg-success-soft text-success' : row.published_at ? 'bg-paper text-muted' : 'bg-gold/15 text-[#7a5410]'}`}>
                {row.current ? t('admin.rates.inForce') : row.published_at ? t('admin.rates.past') : t('admin.rates.draft')}
              </span>
              <span className="ml-auto text-[12px] text-muted">{row.published_at ? `${row.published_by || t('admin.audit.system')} · ${formatShortDate(row.published_at, i18n.language)}` : ''}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function validate(editing: { total: string; rows: Row[] }, t: (key: string, options?: Record<string, unknown>) => string) {
  const problems: string[] = []
  const total = Number(editing.total)
  if (!(total > 0 && total < 100)) problems.push(t('admin.rates.problems.total'))
  let previous = -1
  editing.rows.forEach((row, index) => {
    const oweru = Number(row.oweru)
    if (!(oweru >= 0) || oweru > total) problems.push(t('admin.rates.problems.share', { band: index + 1 }))
    if (index < editing.rows.length - 1) {
      const upper = Number(row.upper)
      if (!row.upper || upper <= previous) problems.push(t('admin.rates.problems.order', { band: index + 1 }))
      previous = upper
    }
  })
  return [...new Set(problems)]
}

export function BandTable({ bands, total }: { bands: Band[]; total: string }) {
  const { t, i18n } = useTranslation()
  return (
    <div className="mt-2 overflow-x-auto rounded-xl border border-mist">
      <table className="w-full min-w-[520px] text-[13px]">
        <thead>
          <tr className="bg-[#f3f5f9] text-left text-[12px] text-navy-soft">
            <th className="px-4 py-2.5 font-medium">{t('admin.rates.price')}</th>
            <th className="px-4 py-2.5 text-right font-medium">{t('admin.rates.oweru')}</th>
            <th className="px-4 py-2.5 text-right font-medium">{t('admin.rates.agent')}</th>
            <th className="px-4 py-2.5 text-right font-medium">{t('admin.rates.total')}</th>
          </tr>
        </thead>
        <tbody>
          {bands.map((band) => (
            <tr key={band.lower} className="border-t border-mist/70">
              <td className="px-4 py-2.5 text-navy tabular-nums">{band.upper ? t('admin.rates.range', { from: shillings(band.lower, i18n.language), to: shillings(band.upper, i18n.language) }) : t('admin.rates.above', { from: shillings(band.lower, i18n.language) })}</td>
              <td className="px-4 py-2.5 text-right font-medium text-navy tabular-nums">{`${percent(band.oweru_rate)}%`}</td>
              <td className="px-4 py-2.5 text-right text-navy tabular-nums">{`${percent(band.agent_rate)}%`}</td>
              <td className="px-4 py-2.5 text-right text-muted tabular-nums">{`${percent(total)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
