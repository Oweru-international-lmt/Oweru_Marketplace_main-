import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { ArrowLeftIcon, CheckIcon, CloseIcon, HomeIcon, MapPinIcon, RulerIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { adminApi, type Duplicate, type DuplicateSide } from '../../../lib/adminApi'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'

// LST-12. After R20: the two records side by side with photo, place and
// size, a "Show differences only" switch, then the attribute rows, and
// Confirm duplicate or Not a duplicate.

export function DuplicateComparePage() {
  const { duplicateId = '' } = useParams()
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  useDocumentTitle(t('admin.duplicate.title'))
  const [row, setRow] = useState<Duplicate | null>(null)
  const [error, setError] = useState('')
  const [onlyDifferences, setOnlyDifferences] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    adminApi.duplicate(duplicateId).then(setRow, (failure) => setError(errorMessage(t, failure)))
  }, [duplicateId, t])

  async function decide(action: 'confirm' | 'dismiss') {
    setBusy(true)
    setError('')
    try {
      setRow(await adminApi.decideDuplicate(duplicateId, action))
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  if (!row) return error ? <Alert tone="error">{error}</Alert> : <FullPageLoader inline />
  const sides = [row.property_a, row.property_b]
  const attributes: { key: string; value: (side: DuplicateSide) => string }[] = [
    { key: 'category', value: (side) => t(`market.category.${side.category}`, { defaultValue: side.category }) },
    { key: 'place', value: (side) => [side.locality, side.ward, side.district, side.region].filter(Boolean).join(', ') },
    { key: 'size', value: (side) => `${Number(side.stated_size).toLocaleString(i18n.language)} ${t(`admin.duplicate.units.${side.size_unit}`, { defaultValue: side.size_unit })}` },
    { key: 'title', value: (side) => t(`admin.duplicate.titles.${side.title_type}`, { defaultValue: side.title_type }) },
    { key: 'lister', value: (side) => side.listings.map((item) => `${item.lister} (${t(`admin.duplicate.kinds.${item.lister_kind}`)})`).join(', ') || side.created_by || '·' },
    { key: 'listing', value: (side) => side.listings.map((item) => `${item.listing_id} · ${t(`admin.duplicate.statuses.${item.status}`, { defaultValue: item.status })}`).join(', ') || '·' },
    { key: 'created', value: (side) => formatShortDate(side.created_at, i18n.language) },
  ]
  const shown = attributes.filter((item) => !onlyDifferences || item.value(sides[0]) !== item.value(sides[1]))

  return (
    <div className="pb-10">
      <Link to="/staff/approvals?tab=duplicates" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-navy">
        <ArrowLeftIcon className="size-4" />
        {t('admin.duplicate.back')}
      </Link>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-bold tracking-tight text-navy">{t('admin.duplicate.title')}</h1>
          <p className="mt-1 max-w-xl text-[13px] text-muted">{t('admin.duplicate.subtitle', { distance: row.distance_meters !== null ? Math.round(Number(row.distance_meters)) : '·', size: row.size_difference_percent !== null ? Number(row.size_difference_percent).toFixed(0) : '·' })}</p>
        </div>
        {row.status === 'PENDING' ? (
          <div className="flex gap-2">
            <button type="button" disabled={busy} onClick={() => void decide('dismiss')} className="inline-flex h-10 items-center gap-2 rounded-xl border border-mist bg-white px-4 text-[13px] font-medium text-navy hover:border-navy-soft/40 disabled:opacity-50">
              <CloseIcon className="size-4" />
              {t('admin.duplicate.dismiss')}
            </button>
            <button type="button" disabled={busy} onClick={() => void decide('confirm')} className="inline-flex h-10 items-center gap-2 rounded-xl bg-[#c2410c] px-4 text-[13px] font-semibold text-white disabled:opacity-50">
              <CheckIcon className="size-4" />
              {t('admin.duplicate.confirm')}
            </button>
          </div>
        ) : (
          <span className={`rounded-full px-3 py-1.5 text-[13px] font-medium ${row.status === 'CONFIRMED_DUPLICATE' ? 'bg-danger-soft text-danger' : 'bg-success-soft text-success'}`}>{t(`admin.duplicate.decided.${row.status}`)}</span>
        )}
      </div>
      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <button type="button" role="switch" aria-checked={onlyDifferences} onClick={() => setOnlyDifferences((value) => !value)} className="inline-flex items-center gap-2.5 rounded-xl border border-mist bg-white px-3.5 py-2 text-[13px] text-navy">
          {t('admin.duplicate.onlyDifferences')}
          <span className={`relative h-5 w-9 rounded-full transition-colors ${onlyDifferences ? 'bg-gold' : 'bg-mist'}`}>
            <motion.span layout transition={{ type: 'spring', stiffness: 500, damping: 30 }} className={`absolute top-0.5 size-4 rounded-full bg-white shadow ${onlyDifferences ? 'right-0.5' : 'left-0.5'}`} />
          </span>
        </button>
        {row.signals.map((signal) => (
          <span key={signal} className="rounded-xl border border-[#f3d3a6] bg-[#fdf3e2] px-3 py-2 text-[12px] font-medium text-[#b4640a]">{t(`admin.duplicate.signals.${signal}`)}</span>
        ))}
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {sides.map((side, index) => {
          const photo = side.listings.flatMap((item) => item.photos)[0]
          return (
            <motion.article key={side.property_id} initial={reduce ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.1 }} className="overflow-hidden rounded-2xl border border-mist bg-white shadow-[0_8px_24px_-18px_rgba(15,23,42,0.4)]">
              <div className="relative aspect-[16/9] bg-paper">
                {photo ? <img src={photo} alt={side.property_id} className="size-full object-cover" /> : <span className="grid size-full place-items-center text-muted"><HomeIcon className="size-8" /></span>}
                <span className="absolute bottom-3 left-3 rounded-full bg-navy px-2.5 py-1 text-[11px] font-semibold text-gold">{index === 0 ? t('admin.duplicate.first') : t('admin.duplicate.second')}</span>
              </div>
              <div className="px-5 py-4">
                <p className="font-mono text-[17px] font-bold text-navy">{side.property_id}</p>
                <p className="mt-1 flex items-center gap-1.5 text-[13px] text-navy-soft"><MapPinIcon className="size-4 shrink-0 text-muted" />{[side.locality, side.ward, side.district].filter(Boolean).join(', ') || t('admin.approvals.noPlace')}</p>
                <p className="mt-2 flex items-center gap-1.5 text-[13px] text-navy-soft"><RulerIcon className="size-4 shrink-0 text-muted" />{`${Number(side.stated_size).toLocaleString(i18n.language)} ${t(`admin.duplicate.units.${side.size_unit}`, { defaultValue: side.size_unit })}`}</p>
                {side.listings.flatMap((item) => item.photos).length > 1 && (
                  <div className="mt-3 flex gap-2">
                    {side.listings.flatMap((item) => item.photos).slice(1, 4).map((url) => (
                      <img key={url} src={url} alt="" className="h-14 w-20 rounded-lg object-cover" />
                    ))}
                  </div>
                )}
              </div>
            </motion.article>
          )
        })}
      </div>

      <section className="mt-6 overflow-hidden rounded-2xl border border-mist bg-white">
        <h2 className="flex items-center gap-2 px-5 py-4 text-[16px] font-semibold text-navy"><HomeIcon className="size-5 text-[#c2410c]" />{t('admin.duplicate.attributes')}</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] table-fixed text-left text-[13px]">
            <thead>
              <tr className="bg-[#f3f5f9] text-[12px] text-navy-soft">
                <th className="w-40 px-5 py-2.5 font-medium">{t('admin.duplicate.attribute')}</th>
                {sides.map((side) => <th key={side.property_id} className="px-4 py-2.5 font-mono font-medium">{side.property_id}</th>)}
              </tr>
            </thead>
            <tbody>
              <AnimatePresence initial={false}>
                {shown.map((item) => {
                  const differs = item.value(sides[0]) !== item.value(sides[1])
                  return (
                    <motion.tr key={item.key} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="border-t border-mist/70">
                      <td className="px-5 py-3 text-muted">{t(`admin.duplicate.rows.${item.key}`)}</td>
                      {sides.map((side) => (
                        <td key={side.property_id} className={`px-4 py-3 ${differs ? 'font-medium text-[#9a6c12]' : 'text-navy'}`}>{item.value(side)}</td>
                      ))}
                    </motion.tr>
                  )
                })}
              </AnimatePresence>
              {shown.length === 0 && (
                <tr><td colSpan={3} className="px-5 py-8 text-center text-muted">{t('admin.duplicate.noDifferences')}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
