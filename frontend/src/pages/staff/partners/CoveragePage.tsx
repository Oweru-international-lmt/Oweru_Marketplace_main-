import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { ChevronRightIcon, UsersIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { partnersApi, type Coverage, type CoverageRow } from '../../../lib/partnersApi'
import type { ProfessionalType } from '../../../lib/tasksApi'
import { AreaMap, type AreaPalette } from '../market/AreaMap'
import { Count } from './ui'

// LOC-07. After R14: a dark map panel with a breadcrumb of places and a
// layers box, stat cards on the right, then the areas at the current level.

type Layer = 'officials' | ProfessionalType
type Scope = { region?: string; district?: string; ward?: string }

const LAYERS: Layer[] = ['officials', 'SURVEYOR', 'AFISA_MIPANGO_MIJI', 'PLANNER']
const DARK: AreaPalette = { bands: ['#e0b04f', '#a87b25', '#5f4b25'], empty: '#26324a', stroke: '#0f172a', text: 'fill-white/85', darkText: 'fill-navy' }

function share(row: Pick<CoverageRow, 'covered' | 'localities'>) {
  return row.localities ? Math.round((row.covered / row.localities) * 100) : 0
}

export function CoveragePage() {
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  useDocumentTitle(t('coverage.title'))
  const [scope, setScope] = useState<Scope>({})
  const [data, setData] = useState<Coverage | null>(null)
  const [regions, setRegions] = useState<CoverageRow[]>([])
  const [layer, setLayer] = useState<Layer>('officials')
  const [waitingOnly, setWaitingOnly] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let live = true
    partnersApi.coverage(scope).then(
      (result) => {
        if (!live) return
        setData(result)
        if (result.level === 'region') setRegions(result.rows)
      },
      (failure) => live && setError(errorMessage(t, failure)),
    )
    return () => {
      live = false
    }
  }, [scope, t])

  // The map always shows the regions; deeper levels keep their region lit.
  useEffect(() => {
    if (regions.length || !scope.region) return
    partnersApi.coverage({}).then((result) => setRegions(result.rows), () => undefined)
  }, [regions.length, scope.region])

  const valueOf = (row: CoverageRow) => (layer === 'officials' ? share(row) : row.professionals[layer] ?? 0)
  const areas = useMemo(
    () => regions.map((row) => ({ name: row.name, value: waitingOnly ? row.waiting : layer === 'officials' ? share(row) : row.professionals[layer] ?? 0 })).filter((row) => row.value > 0),
    [regions, layer, waitingOnly],
  )
  const top = Math.max(1, ...areas.map((row) => row.value))
  const bandOf = (value: number): 0 | 1 | 2 => (value >= top * 0.66 ? 0 : value >= top * 0.33 ? 1 : 2)

  const rows = data?.rows ?? []
  const totals = rows.reduce(
    (sum, row) => ({ localities: sum.localities + row.localities, covered: sum.covered + row.covered, officials: sum.officials + row.officials, waiting: sum.waiting + row.waiting }),
    { localities: 0, covered: 0, officials: 0, waiting: 0 },
  )
  const pros = (type: ProfessionalType) => data?.professionals[type] ?? 0
  const selectedRegion = data?.crumbs[0]?.name

  function open(row: CoverageRow) {
    if (!data || data.level === 'locality') return
    if (data.level === 'region') setScope({ region: row.id })
    else if (data.level === 'district') setScope({ ...scope, district: row.id })
    else setScope({ ...scope, ward: row.id })
  }

  function crumb(index: number) {
    if (!data) return
    const ids = data.crumbs.map((item) => item.id)
    setScope(index < 0 ? {} : index === 0 ? { region: ids[0] } : index === 1 ? { region: ids[0], district: ids[1] } : { region: ids[0], district: ids[1], ward: ids[2] })
  }

  const cards = [
    { label: t('coverage.cards.covered'), value: share(totals), suffix: '%', note: t('coverage.cards.coveredNote', { covered: totals.covered, total: totals.localities }) },
    { label: t('coverage.cards.officials'), value: totals.officials, note: t('coverage.cards.officialsNote') },
    { label: t('coverage.cards.waiting'), value: totals.waiting, note: t('coverage.cards.waitingNote'), alert: totals.waiting > 0 },
    { label: t('coverage.cards.professionals'), value: pros('SURVEYOR') + pros('AFISA_MIPANGO_MIJI') + pros('PLANNER'), note: t('coverage.cards.professionalsNote', { surveyors: pros('SURVEYOR'), amm: pros('AFISA_MIPANGO_MIJI'), planners: pros('PLANNER') }) },
  ]

  return (
    <div className="pb-10">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-navy">{t('coverage.title')}</h1>
          <p className="mt-1 text-[13px] text-muted">{t('coverage.subtitle')}</p>
        </div>
        <Link to="/staff/partners" className="inline-flex h-10 items-center gap-2 rounded-xl border border-mist bg-white px-4 text-[13px] font-medium text-navy hover:border-navy-soft/40">
          <UsersIcon className="size-4" />
          {t('coverage.partnersLink')}
        </Link>
      </div>
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
        <section className="relative overflow-hidden rounded-2xl bg-navy px-5 pt-4 pb-5 text-white">
          <nav aria-label={t('coverage.breadcrumb')} className="flex flex-wrap items-center gap-1.5 text-[15px]">
            <button type="button" onClick={() => crumb(-1)} className={`font-semibold ${data?.crumbs.length ? 'text-white/70 hover:text-white' : 'text-white'}`}>Tanzania</button>
            {data?.crumbs.map((item, index) => (
              <span key={item.id} className="inline-flex items-center gap-1.5">
                <ChevronRightIcon className="size-4 text-white/40" />
                <button type="button" onClick={() => crumb(index)} className={index === data.crumbs.length - 1 ? 'font-semibold text-gold' : 'text-white/70 hover:text-white'}>{item.name}</button>
              </span>
            ))}
          </nav>

          <div className="mt-3 grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
            <motion.div initial={reduce ? false : { opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="self-start rounded-xl bg-white p-4 text-navy shadow-lift">
              <p className="text-[13px] font-semibold">{t('coverage.layers')}</p>
              <div className="mt-3 space-y-1 rounded-lg bg-paper p-1.5">
                {LAYERS.map((item) => {
                  const on = layer === item && !waitingOnly
                  return (
                    <button key={item} type="button" role="radio" aria-checked={on} onClick={() => { setLayer(item); setWaitingOnly(false) }} className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13px] ${on ? 'bg-white font-medium shadow-sm' : 'text-navy-soft hover:bg-white/60'}`}>
                      <span className={`grid size-4 place-items-center rounded border ${on ? 'border-navy bg-navy text-white' : 'border-mist bg-white'}`}>
                        {on && <svg viewBox="0 0 12 12" className="size-2.5" aria-hidden="true"><path d="M2.5 6.2 5 8.5l4.5-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}
                      </span>
                      {item === 'officials' ? t('coverage.layerOfficials') : t(`field.types.${item}`)}
                    </button>
                  )
                })}
              </div>
              <label className="mt-4 flex items-start justify-between gap-3">
                <span>
                  <span className="block text-[13px] font-semibold">{t('coverage.waitingToggle')}</span>
                  <span className="block text-[11px] text-muted">{t('coverage.waitingHint')}</span>
                </span>
                <button type="button" role="switch" aria-checked={waitingOnly} onClick={() => setWaitingOnly((value) => !value)} className={`relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors ${waitingOnly ? 'bg-success' : 'bg-mist'}`}>
                  <motion.span layout transition={{ type: 'spring', stiffness: 500, damping: 30 }} className={`absolute top-0.5 size-4 rounded-full bg-white shadow ${waitingOnly ? 'right-0.5' : 'left-0.5'}`} />
                </button>
              </label>
              <div className="mt-4 flex items-center gap-1.5 text-[10px] text-muted">
                {DARK.bands.slice().reverse().map((color) => (
                  <span key={color} className="h-2 flex-1 rounded-full" style={{ background: color }} />
                ))}
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-muted">
                <span>{t('coverage.less')}</span>
                <span>{t('coverage.more')}</span>
              </div>
            </motion.div>
            <div className="min-h-[360px]">
              <AreaMap areas={areas} bandOf={bandOf} palette={DARK} selected={selectedRegion} onPick={(name) => {
                const row = regions.find((item) => item.name === name)
                if (row) setScope({ region: row.id })
              }} label={t('coverage.mapLabel')} />
            </div>
          </div>
        </section>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
          {cards.map((card, index) => (
            <motion.div key={card.label} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + index * 0.07 }} className="rounded-xl border border-mist bg-white px-5 py-4">
              <p className="text-[13px] text-navy-soft">{card.label}</p>
              <p className={`mt-1 text-[28px] font-bold tracking-tight ${card.alert ? 'text-[#c2410c]' : 'text-navy'}`}>
                <Count value={card.value} />
                {card.suffix}
              </p>
              <p className="mt-0.5 text-[12px] text-muted">{card.note}</p>
            </motion.div>
          ))}
        </div>
      </div>

      <section className="mt-4 rounded-xl border border-mist bg-white px-5 py-5">
        <h2 className="text-[15px] font-semibold text-navy">{data ? t(`coverage.levels.${data.level}`) : ''}</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-mist text-[12px] text-muted">
                <th className="py-2 pr-3 font-medium">{t('coverage.columns.name')}</th>
                <th className="px-3 py-2 font-medium">{t('coverage.columns.localities')}</th>
                <th className="px-3 py-2 font-medium">{t('coverage.columns.covered')}</th>
                <th className="px-3 py-2 font-medium">{t('coverage.columns.officials')}</th>
                <th className="px-3 py-2 font-medium">{t('coverage.columns.waiting')}</th>
                <th className="px-3 py-2 font-medium">{t('coverage.columns.professionals')}</th>
                <th className="w-6" />
              </tr>
            </thead>
            <tbody>
              <AnimatePresence initial={false}>
                {rows
                  .filter((row) => !waitingOnly || row.waiting > 0)
                  .sort((a, b) => valueOf(b) - valueOf(a) || a.name.localeCompare(b.name))
                  .map((row, index) => (
                    <motion.tr
                      key={row.id}
                      initial={reduce ? false : { opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: Math.min(index, 14) * 0.03 }}
                      onClick={() => open(row)}
                      className={`border-b border-mist/60 last:border-b-0 ${data?.level !== 'locality' ? 'cursor-pointer hover:bg-paper/70' : ''}`}
                    >
                      <td className="py-3 pr-3 font-medium text-navy">{row.name}</td>
                      <td className="px-3 py-3 text-navy-soft tabular-nums">{row.localities}</td>
                      <td className="px-3 py-3">
                        <span className="flex items-center gap-2.5">
                          <span className="h-1.5 w-24 overflow-hidden rounded-full bg-paper">
                            <motion.span className="block h-full rounded-full bg-gold" initial={{ width: 0 }} animate={{ width: `${share(row)}%` }} transition={{ duration: 0.6, delay: 0.1 + Math.min(index, 14) * 0.03 }} />
                          </span>
                          <span className="text-navy-soft tabular-nums">{`${share(row)}%`}</span>
                        </span>
                      </td>
                      <td className="px-3 py-3 text-navy-soft tabular-nums">{row.officials}</td>
                      <td className="px-3 py-3 tabular-nums">{row.waiting > 0 ? <span className="rounded-full bg-[#fdf3e2] px-2 py-0.5 text-[11px] font-semibold text-[#b4640a]">{row.waiting}</span> : <span className="text-muted">0</span>}</td>
                      <td className="px-3 py-3 text-[12px] text-navy-soft">
                        {(['SURVEYOR', 'AFISA_MIPANGO_MIJI', 'PLANNER'] as ProfessionalType[]).map((type) => `${t(`coverage.short.${type}`)} ${row.professionals[type] ?? 0}`).join(' · ')}
                      </td>
                      <td>{data?.level !== 'locality' && <ChevronRightIcon className="size-4 text-muted" />}</td>
                    </motion.tr>
                  ))}
              </AnimatePresence>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-10 text-center text-muted">{t('coverage.empty')}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
