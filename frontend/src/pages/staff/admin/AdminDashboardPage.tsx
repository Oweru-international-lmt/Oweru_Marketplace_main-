import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { BanknoteIcon, ChatIcon, ChevronRightIcon, ClockIcon, EyeIcon, IdCardIcon, MapPinIcon, ShieldIcon, UsersIcon, WhatsAppIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { adminApi, type Dashboard } from '../../../lib/adminApi'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'
import { Count } from '../partners/ui'

// ADM-01. After R16: five stat cards, then the complaints by status as a
// donut beside every queue with its count, then the oldest waiting items.

const COMPLAINT_ORDER = ['RECEIVED', 'IN_REVIEW', 'WAITING_INFORMATION', 'RESOLVED', 'UNDER_FINAL_REVIEW', 'CLOSED'] as const
const COMPLAINT_COLOURS: Record<string, string> = { RECEIVED: '#c89128', IN_REVIEW: '#0f172a', WAITING_INFORMATION: '#8a6a2f', RESOLVED: '#1f7a4d', UNDER_FINAL_REVIEW: '#475569', CLOSED: '#cbd5e1' }

export function AdminDashboardPage() {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const navigate = useNavigate()
  useDocumentTitle(t('admin.dashboard.title'))
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi.dashboard().then(setData, (failure) => setError(errorMessage(t, failure)))
  }, [t])

  if (error) return <Alert tone="error">{error}</Alert>
  if (!data) return <FullPageLoader inline />

  const openComplaints = Object.entries(data.complaints_by_status).filter(([status]) => status !== 'RESOLVED' && status !== 'CLOSED').reduce((sum, [, count]) => sum + count, 0)
  const cards = [
    { key: 'identities', value: data.identities_to_approve, icon: IdCardIcon, tone: 'bg-navy text-gold', to: '/staff/identities' },
    { key: 'duplicates', value: data.duplicates, icon: ShieldIcon, tone: 'bg-[#c2410c] text-white', to: '/staff/approvals?tab=duplicates', note: t('admin.dashboard.flagged', { count: data.flagged_listings }) },
    { key: 'partners', value: data.partner_approvals.count, icon: UsersIcon, tone: 'bg-gold text-navy', to: '/staff/partners' },
    { key: 'payments', value: data.full_check_payments_to_confirm + data.deal_payments_to_confirm, icon: BanknoteIcon, tone: 'bg-success text-white', to: '/staff/deals', note: t('admin.dashboard.paymentsNote', { checks: data.full_check_payments_to_confirm, deals: data.deal_payments_to_confirm }) },
    { key: 'complaints', value: openComplaints, icon: ChatIcon, tone: 'bg-[#3552a8] text-white', to: '/staff/complaints', note: t('admin.dashboard.overdue', { count: data.overdue_complaints }) },
  ]
  const queues = [
    { key: 'identities', count: data.identities_to_approve, to: '/staff/identities', icon: IdCardIcon },
    { key: 'localities', count: data.localities_to_approve, to: '/staff/approvals', icon: MapPinIcon },
    { key: 'duplicates', count: data.duplicates, to: '/staff/approvals?tab=duplicates', icon: ShieldIcon },
    { key: 'partners', count: data.partner_approvals.count, to: '/staff/partners', icon: UsersIcon },
    { key: 'needsOfficial', count: data.tasks_needing_official, to: '/staff/coverage', icon: MapPinIcon },
    { key: 'checkPayments', count: data.full_check_payments_to_confirm, to: '/staff/full-checks', icon: BanknoteIcon },
    { key: 'dealPayments', count: data.deal_payments_to_confirm, to: '/staff/deals', icon: BanknoteIcon },
    { key: 'payoutsDue', count: data.payouts_due, to: '/staff/payouts', icon: ClockIcon, extra: data.payouts_on_hold ? t('admin.dashboard.onHold', { count: data.payouts_on_hold }) : '' },
    { key: 'outbox', count: data.outbox_waiting, to: '/staff/outbox', icon: WhatsAppIcon },
  ]
  const complaintTotal = COMPLAINT_ORDER.reduce((sum, status) => sum + (data.complaints_by_status[status] ?? 0), 0)

  return (
    <div className="pb-10">
      <div className="mb-5">
        <h1 className="text-[24px] font-semibold text-navy">{t('admin.dashboard.title')}</h1>
        <p className="mt-1 text-[13px] text-muted">{t('admin.dashboard.subtitle')}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5">
        {cards.map((card, index) => (
          <motion.div key={card.key} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06 }}>
            <Link to={card.to} className="flex h-full flex-col rounded-xl border border-mist bg-white px-4 py-4 transition-shadow hover:shadow-sm">
              <span className="flex items-center gap-2.5">
                <span className={`grid size-8 place-items-center rounded-lg ${card.tone}`}><card.icon className="size-4" /></span>
                <span className="text-[13px] text-navy-soft">{t(`admin.dashboard.cards.${card.key}`)}</span>
              </span>
              <span className="mt-3 text-[26px] font-bold tracking-tight text-navy"><Count value={card.value} /></span>
              <span className="mt-0.5 text-[12px] text-muted">{card.note ?? t('admin.dashboard.waiting')}</span>
            </Link>
          </motion.div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="min-w-0 rounded-xl border border-mist bg-white px-5 py-5">
          <h2 className="text-[15px] font-semibold text-navy">{t('admin.dashboard.queuesTitle')}</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {queues.map((queue, index) => (
              <motion.li key={queue.key} className="min-w-0" initial={reduce ? false : { opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + index * 0.04 }}>
                <Link to={queue.to} className="flex items-center gap-3 rounded-lg bg-[#f3f5f9] px-3 py-3 transition-colors hover:bg-[#e9edf4]">
                  <queue.icon className="size-4 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] text-navy">{t(`admin.dashboard.queues.${queue.key}`)}</span>
                    {queue.extra && <span className="block text-[11px] text-[#b4640a]">{queue.extra}</span>}
                  </span>
                  <span className={`min-w-8 rounded-full px-2 py-0.5 text-center text-[12px] font-semibold tabular-nums ${queue.count > 0 ? 'bg-gold text-navy' : 'bg-white text-muted'}`}>{queue.count}</span>
                  <ChevronRightIcon className="size-4 text-muted" />
                </Link>
              </motion.li>
            ))}
          </ul>
        </section>

        <section className="min-w-0 rounded-xl border border-mist bg-white px-5 py-5">
          <h2 className="text-[15px] font-semibold text-navy">{t('admin.dashboard.complaintsTitle')}</h2>
          <div className="mt-4 flex items-center gap-4">
            <Donut values={COMPLAINT_ORDER.map((status) => ({ key: status, value: data.complaints_by_status[status] ?? 0, colour: COMPLAINT_COLOURS[status] }))} total={complaintTotal} label={t('admin.dashboard.total')} />
            <ul className="min-w-0 flex-1 space-y-2 text-[12px]">
              {COMPLAINT_ORDER.map((status) => (
                <li key={status} className="flex items-center gap-2">
                  <span className="size-2.5 shrink-0 rounded-full" style={{ background: COMPLAINT_COLOURS[status] }} />
                  <span className="min-w-0 flex-1 truncate text-navy-soft">{t(`staff.statuses.${status}`)}</span>
                  <span className="font-semibold text-navy tabular-nums">{data.complaints_by_status[status] ?? 0}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <section className="mt-4 rounded-xl border border-mist bg-white">
        <h2 className="px-5 pt-5 text-[15px] font-semibold text-navy">{t('admin.dashboard.oldestTitle')}</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-[13px]">
            <thead>
              <tr className="bg-[#f6f1e6] text-[12px] text-navy-soft">
                <th className="px-5 py-2.5 font-medium">{t('admin.dashboard.columns.queue')}</th>
                <th className="px-3 py-2.5 font-medium">{t('admin.dashboard.columns.reference')}</th>
                <th className="px-3 py-2.5 font-medium">{t('admin.dashboard.columns.since')}</th>
                <th className="px-5 py-2.5 text-right font-medium">{t('admin.dashboard.columns.open')}</th>
              </tr>
            </thead>
            <tbody>
              {data.oldest.length === 0 && (
                <tr><td colSpan={4} className="px-5 py-10 text-center text-muted">{t('admin.dashboard.nothing')}</td></tr>
              )}
              {data.oldest.map((item, index) => (
                <motion.tr key={`${item.queue}-${item.link}`} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + index * 0.04 }} onClick={() => navigate(item.link)} className="cursor-pointer border-b border-mist/60 last:border-b-0 hover:bg-paper/70">
                  <td className="px-5 py-3"><span className="rounded-full bg-gold/12 px-2.5 py-0.5 text-[11px] font-medium text-[#7a5410]">{t(`admin.dashboard.oldestQueues.${item.queue}`)}</span></td>
                  <td className="max-w-[320px] truncate px-3 py-3 font-medium text-navy">{item.reference}</td>
                  <td className="px-3 py-3 text-navy-soft tabular-nums">{formatShortDate(item.since, i18n.language)}</td>
                  <td className="px-5 py-3 text-right"><EyeIcon className="ml-auto size-4 text-gold" /></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

// A ring split by value, drawn with stroke dashes; 2px gaps between parts.
function Donut({ values, total, label }: { values: { key: string; value: number; colour: string }[]; total: number; label: string }) {
  const reduce = useReducedMotion()
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const parts = values.filter((item) => item.value > 0)
  const offsets = parts.map((_, index) => parts.slice(0, index).reduce((sum, item) => sum + (item.value / total) * circumference, 0))
  return (
    <svg viewBox="0 0 110 110" className="size-[104px] shrink-0 sm:size-[120px]" role="img" aria-label={`${label}: ${total}`}>
      <circle cx="55" cy="55" r={radius} fill="none" stroke="#eef1f5" strokeWidth="14" />
      {total > 0 &&
        parts.map((item, index) => {
          const length = Math.max(0, (item.value / total) * circumference - (parts.length > 1 ? 2 : 0))
          return (
            <motion.circle
              key={item.key}
              cx="55"
              cy="55"
              r={radius}
              fill="none"
              stroke={item.colour}
              strokeWidth="14"
              strokeDasharray={`${length} ${circumference}`}
              strokeDashoffset={-offsets[index]}
              transform="rotate(-90 55 55)"
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 + index * 0.08 }}
            />
          )
        })}
      <text x="55" y="53" textAnchor="middle" className="fill-navy text-[20px] font-bold">{total}</text>
      <text x="55" y="68" textAnchor="middle" className="fill-[#64748b] text-[9px]">{label}</text>
    </svg>
  )
}
