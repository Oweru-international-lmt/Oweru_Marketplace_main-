import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { CheckIcon, ChevronDownIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { adminApi, type Duplicate, type PendingLocality } from '../../../lib/adminApi'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'

// LST-03, ADM-03, LST-12. After R17: an approval queue with tabs; each row
// has Approve, and Reject opens a small menu (merge into the right street).

type Tab = 'localities' | 'duplicates'

export function ApprovalsPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('admin.approvals.title'))
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'duplicates' ? 'duplicates' : 'localities'
  const [localities, setLocalities] = useState<PendingLocality[] | null>(null)
  const [duplicates, setDuplicates] = useState<Duplicate[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi.pendingLocalities().then(setLocalities, (failure) => setError(errorMessage(t, failure)))
    adminApi.duplicates().then(setDuplicates, (failure) => setError(errorMessage(t, failure)))
  }, [t])

  const tabs: { key: Tab; count: number | undefined }[] = [
    { key: 'localities', count: localities?.length },
    { key: 'duplicates', count: duplicates?.length },
  ]

  return (
    <div className="pb-10">
      <div role="tablist" aria-label={t('admin.approvals.title')} className="flex gap-6 border-b border-mist">
        {tabs.map((item) => (
          <button key={item.key} type="button" role="tab" aria-selected={tab === item.key} onClick={() => setParams(item.key === 'duplicates' ? { tab: 'duplicates' } : {})} className={`relative pb-3 text-[14px] font-medium ${tab === item.key ? 'text-[#9a6c12]' : 'text-muted hover:text-navy'}`}>
            {t(`admin.approvals.tabs.${item.key}`)}
            {item.count !== undefined && <span className="ml-1.5 rounded-full bg-paper px-1.5 text-[11px] text-navy-soft">{item.count}</span>}
            {tab === item.key && <motion.span layoutId="approvals-tab" className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-gold" />}
          </button>
        ))}
      </div>
      <h1 className="mt-6 text-[22px] font-semibold text-navy">{t('admin.approvals.heading')}</h1>
      <p className="mt-1 text-[13px] text-muted">{t(`admin.approvals.note.${tab}`)}</p>
      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
      <div className="mt-4">
        {tab === 'localities' ? (
          localities ? <LocalityQueue rows={localities} onDone={(id) => setLocalities((rows) => rows?.filter((row) => row.id !== id) ?? null)} /> : <FullPageLoader inline />
        ) : duplicates ? (
          <DuplicateQueue rows={duplicates} />
        ) : (
          <FullPageLoader inline />
        )}
      </div>
    </div>
  )
}

function LocalityQueue({ rows, onDone }: { rows: PendingLocality[]; onDone: (id: string) => void }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const [open, setOpen] = useState<string | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState<Record<string, string>>({})

  async function act(row: PendingLocality, action: () => Promise<unknown>, message: string) {
    setBusy(row.id)
    setError('')
    try {
      await action()
      setDone((current) => ({ ...current, [row.id]: message }))
      setOpen(null)
      window.setTimeout(() => onDone(row.id), 1200)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy('')
    }
  }

  if (rows.length === 0) return <Empty text={t('admin.approvals.emptyLocalities')} />
  return (
    <div className="rounded-xl border border-mist bg-white">
      {error && <div className="px-4 pt-4"><Alert tone="error">{error}</Alert></div>}
      <div className="hidden grid-cols-[minmax(0,1.3fr)_minmax(0,1.3fr)_90px_120px_210px] gap-3 bg-[#f3f5f9] px-5 py-3 text-[12px] font-medium text-navy-soft md:grid">
        <span>{t('admin.approvals.columns.name')}</span>
        <span>{t('admin.approvals.columns.place')}</span>
        <span>{t('admin.approvals.columns.properties')}</span>
        <span>{t('admin.approvals.columns.added')}</span>
        <span />
      </div>
      <ul>
        <AnimatePresence initial={false}>
          {rows.map((row, index) => (
            <motion.li key={row.id} layout initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }} transition={{ delay: Math.min(index, 10) * 0.03 }} className="border-b border-mist/70 last:border-b-0">
              <div className="grid gap-3 px-5 py-3.5 text-[13px] md:grid-cols-[minmax(0,1.3fr)_minmax(0,1.3fr)_90px_120px_210px] md:items-center">
                <span>
                  <span className="block font-medium text-[#9a6c12]">{row.name}</span>
                  <span className="block text-[11px] text-muted">{t(`partners.place.kinds.${row.kind}`)}{row.created_by && ` · ${row.created_by}`}</span>
                </span>
                <span className="text-navy-soft">{`${row.ward}, ${row.district}, ${row.region}`}</span>
                <span className="text-navy-soft tabular-nums">{row.properties}</span>
                <span className="text-navy-soft tabular-nums">{formatShortDate(row.created_at, i18n.language)}</span>
                {done[row.id] ? (
                  <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-success md:justify-end"><CheckIcon className="size-4" />{done[row.id]}</span>
                ) : (
                  <span className="relative flex gap-2 md:justify-end">
                    <button type="button" disabled={busy === row.id} onClick={() => void act(row, () => adminApi.approveLocality(row.id), t('admin.approvals.approved'))} className="rounded-full border border-mist px-4 py-1.5 text-[12px] font-medium text-navy hover:border-gold hover:bg-gold/10 disabled:opacity-50">
                      {t('admin.approvals.approve')}
                    </button>
                    <button type="button" aria-expanded={open === row.id} onClick={() => setOpen(open === row.id ? null : row.id)} className="inline-flex items-center gap-1 rounded-full border border-mist px-3 py-1.5 text-[12px] font-medium text-navy hover:border-danger/40">
                      {t('admin.approvals.reject')}
                      <ChevronDownIcon className={`size-3.5 transition-transform ${open === row.id ? 'rotate-180' : ''}`} />
                    </button>
                    <AnimatePresence>
                      {open === row.id && (
                        <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} className="absolute top-full right-0 z-20 mt-2 w-72 rounded-xl border border-mist bg-white p-3 text-left shadow-lift">
                          <p className="text-[12px] text-navy-soft">{t('admin.approvals.mergeNote', { count: row.properties })}</p>
                          {row.approved_in_ward.length === 0 ? (
                            <p className="mt-2 text-[12px] text-muted">{t('admin.approvals.noApproved')}</p>
                          ) : (
                            <ul className="mt-2 max-h-56 space-y-1 overflow-y-auto">
                              {row.approved_in_ward.map((target) => (
                                <li key={target.id}>
                                  <button type="button" disabled={busy === row.id} onClick={() => void act(row, () => adminApi.mergeLocality(row.id, target.id), t('admin.approvals.merged', { name: target.name }))} className="w-full rounded-lg px-2.5 py-2 text-left text-[13px] text-navy hover:bg-paper">
                                    {t('admin.approvals.mergeInto', { name: target.name })}
                                  </button>
                                </li>
                              ))}
                            </ul>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </span>
                )}
              </div>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  )
}

function DuplicateQueue({ rows }: { rows: Duplicate[] }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  if (rows.length === 0) return <Empty text={t('admin.approvals.emptyDuplicates')} />
  return (
    <div className="rounded-xl border border-mist bg-white">
      <div className="hidden grid-cols-[minmax(0,1.6fr)_minmax(0,1.4fr)_110px_120px_120px] gap-3 bg-[#f3f5f9] px-5 py-3 text-[12px] font-medium text-navy-soft md:grid">
        <span>{t('admin.approvals.columns.pair')}</span>
        <span>{t('admin.approvals.columns.signals')}</span>
        <span>{t('admin.approvals.columns.distance')}</span>
        <span>{t('admin.approvals.columns.added')}</span>
        <span />
      </div>
      <ul>
        {rows.map((row, index) => (
          <motion.li key={row.id} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index, 10) * 0.03 }} className="grid gap-3 border-b border-mist/70 px-5 py-3.5 text-[13px] last:border-b-0 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1.4fr)_110px_120px_120px] md:items-center">
            <span>
              <span className="block font-mono text-[12px] font-medium text-[#9a6c12]">{`${row.property_a.property_id} · ${row.property_b.property_id}`}</span>
              <span className="block text-[11px] text-muted">{[row.property_a.locality || row.property_a.ward, row.property_a.district].filter(Boolean).join(', ') || t('admin.approvals.noPlace')}</span>
            </span>
            <span className="flex flex-wrap gap-1">
              {row.signals.map((signal) => (
                <span key={signal} className="rounded-full bg-[#fdf3e2] px-2 py-0.5 text-[11px] text-[#b4640a]">{t(`admin.duplicate.signals.${signal}`)}</span>
              ))}
            </span>
            <span className="text-navy-soft tabular-nums">{row.distance_meters !== null ? t('admin.duplicate.metres', { value: Math.round(Number(row.distance_meters)) }) : '·'}</span>
            <span className="text-navy-soft tabular-nums">{formatShortDate(row.created_at, i18n.language)}</span>
            <span className="md:text-right">
              <Link to={`/staff/duplicates/${row.id}`} className="inline-flex rounded-full bg-gold px-4 py-1.5 text-[12px] font-semibold text-navy hover:bg-gold-light">{t('admin.approvals.compare')}</Link>
            </span>
          </motion.li>
        ))}
      </ul>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-mist bg-white px-6 py-14 text-center">
      <span className="mx-auto grid size-11 place-items-center rounded-full bg-success-soft text-success"><CheckIcon className="size-5" /></span>
      <p className="mt-3 text-[14px] text-navy-soft">{text}</p>
    </div>
  )
}
