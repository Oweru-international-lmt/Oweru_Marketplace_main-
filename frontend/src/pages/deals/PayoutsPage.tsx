import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { BankIcon, CalendarIcon, ChevronRightIcon, ClockIcon, ListIcon, TickIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ApiError } from '../../lib/api'
import { dealsApi, type Bank, type Deal, type PayoutRow } from '../../lib/dealsApi'
import { errorMessage } from '../../lib/errors'
import { formatShortDate, formatTsh } from '../../lib/format'
import { CountUp, PayoutChip } from './ui'

// PAY-10: the agent's payouts. D12 on wide screens (three stat cards, the
// history table, the next payout explained, the payout account) and D13 on
// phones (all-time figure, a dark pending card, the activity list).

type Loaded = { payouts: PayoutRow[]; bank: Bank | null; next: Deal | null }

const OPEN = new Set(['PENDING', 'DUE', 'ON_HOLD'])

export function PayoutsPage() {
  const { t } = useTranslation()
  const [data, setData] = useState<Loaded | null>(null)
  const [error, setError] = useState('')
  useDocumentTitle(t('deals.payouts.title'))

  useEffect(() => {
    let live = true
    async function load() {
      const [payouts, bank] = await Promise.all([
        dealsApi.payouts(),
        dealsApi.bank().catch((failure) => {
          if (failure instanceof ApiError && failure.status === 404) return null
          throw failure
        }),
      ])
      const upcoming = payouts.filter((row) => OPEN.has(row.status)).sort((a, b) => a.due_at.localeCompare(b.due_at))[0]
      const next = upcoming ? await dealsApi.get(upcoming.deal_id).catch(() => null) : null
      return { payouts, bank, next }
    }
    load()
      .then((loaded) => live && setData(loaded))
      .catch((failure) => {
        if (!live) return
        setError(errorMessage(t, failure))
        setData({ payouts: [], bank: null, next: null })
      })
    return () => {
      live = false
    }
  }, [t])

  if (!data) return <FullPageLoader inline />
  return (
    <div className="pb-10">
      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <div className="hidden lg:block">
        <DesktopPayouts data={data} />
      </div>
      <div className="lg:hidden">
        <PhonePayouts data={data} />
      </div>
    </div>
  )
}

function useTotals(payouts: PayoutRow[]) {
  return useMemo(() => {
    const sum = (rows: PayoutRow[]) => rows.reduce((total, row) => total + Number(row.amount), 0)
    const open = payouts.filter((row) => OPEN.has(row.status))
    const paid = payouts.filter((row) => row.status === 'PAID')
    const next = [...open].sort((a, b) => a.due_at.localeCompare(b.due_at))[0] ?? null
    return { open: sum(open), openCount: open.length, paid: sum(paid), paidCount: paid.length, held: payouts.filter((row) => row.status === 'ON_HOLD').length, next }
  }, [payouts])
}

function DesktopPayouts({ data }: { data: Loaded }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const totals = useTotals(data.payouts)
  const [now] = useState(() => Date.now())
  const days = totals.next ? Math.max(0, Math.ceil((new Date(totals.next.due_at).getTime() - now) / 86_400_000)) : null
  const cards = [
    {
      icon: CalendarIcon,
      label: t('deals.payouts.nextPayout'),
      chip: totals.next ? formatShortDate(totals.next.due_at, i18n.language) : null,
      value: totals.next ? Number(totals.next.amount) : 0,
      note: totals.next ? t('deals.payouts.forProperty', { id: totals.next.property_id }) : t('deals.payouts.nothingDue'),
    },
    { icon: ClockIcon, label: t('deals.payouts.waiting'), chip: null, value: totals.open, note: t('deals.payouts.waitingNote', { count: totals.openCount }) },
    { icon: TickIcon, label: t('deals.payouts.paidOut'), chip: null, value: totals.paid, note: t('deals.payouts.paidNote', { count: totals.paidCount }) },
  ]
  return (
    <div>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-navy">{t('deals.payouts.title')}</h1>
          <p className="mt-1 text-[13px] text-muted">{days === null ? t('deals.payouts.subtitleNone') : t('deals.payouts.subtitle', { count: days })}</p>
        </div>
        <Link to="/lister/bank" className="inline-flex h-10 items-center gap-2 rounded-xl border border-mist bg-white px-4 text-[13px] font-medium text-navy hover:border-navy-soft/40">
          <BankIcon className="size-4" />
          {t('deals.payouts.settings')}
        </Link>
      </div>
      <div className="grid grid-cols-3 gap-4">
        {cards.map((card, index) => (
          <motion.div
            key={card.label}
            initial={reduce ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.08 }}
            className="rounded-2xl border border-mist bg-white px-5 py-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2.5 text-[14px] text-navy-soft">
                <span className="grid size-7 place-items-center rounded-md border border-mist">
                  <card.icon className="size-3.5" />
                </span>
                {card.label}
              </span>
              {card.chip && <span className="rounded-md bg-gold/15 px-2 py-0.5 text-[11px] font-medium text-[#7a5410]">{card.chip}</span>}
            </div>
            <p className="mt-4">
              <CountUp value={card.value} className="text-[28px] font-bold tracking-tight text-navy" />
            </p>
            <p className="mt-2 text-[12px] text-muted">{card.note}</p>
          </motion.div>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-[minmax(0,1fr)_320px] items-start gap-4">
        <section className="overflow-hidden rounded-2xl border border-mist bg-white">
          <div className="flex items-center justify-between border-b border-mist px-5 py-4">
            <h2 className="text-[15px] font-medium text-navy">{t('deals.payouts.history')}</h2>
            <Link to="/lister/deals" className="text-[13px] font-medium text-navy underline decoration-gold decoration-2 underline-offset-4">
              {t('deals.payouts.viewDeals')}
            </Link>
          </div>
          <table className="w-full text-left text-[13px]">
            <caption className="sr-only">{t('deals.payouts.history')}</caption>
            <thead>
              <tr className="border-b border-mist text-[11px] tracking-[0.06em] text-muted uppercase">
                <th scope="col" className="px-5 py-3 font-medium">{t('deals.payouts.columns.date')}</th>
                <th scope="col" className="px-3 py-3 font-medium">{t('deals.payouts.columns.property')}</th>
                <th scope="col" className="px-3 py-3 font-medium">{t('deals.payouts.columns.amount')}</th>
                <th scope="col" className="px-3 py-3 font-medium">{t('deals.payouts.columns.reference')}</th>
                <th scope="col" className="px-3 py-3 font-medium">{t('deals.payouts.columns.status')}</th>
                <th scope="col" className="w-10 px-3 py-3"><span className="sr-only">{t('deals.open')}</span></th>
              </tr>
            </thead>
            <tbody>
              {data.payouts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-muted">{t('deals.payouts.empty')}</td>
                </tr>
              ) : (
                data.payouts.map((row, index) => (
                  <motion.tr key={row.id} initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 + index * 0.04 }} className="border-b border-mist/70 last:border-b-0 hover:bg-paper">
                    <td className="px-5 py-3.5 font-medium text-navy">{formatShortDate(row.paid_at ?? row.due_at, i18n.language)}</td>
                    <td className="px-3 py-3.5 text-muted">{row.property_id}</td>
                    <td className="px-3 py-3.5 font-semibold text-navy tabular-nums">{formatTsh(row.amount, i18n.language)}</td>
                    <td className="px-3 py-3.5 text-muted">{row.bank_reference || '-'}</td>
                    <td className="px-3 py-3.5">
                      <PayoutChip status={row.status} />
                    </td>
                    <td className="px-3 py-3.5">
                      <Link to={`/lister/deals/${row.deal_id}`} aria-label={t('deals.open')} className="text-muted hover:text-navy">
                        <ChevronRightIcon className="size-4" />
                      </Link>
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </section>
        <div className="space-y-4">
          <NextPayoutCard next={totals.next} deal={data.next} />
          <AccountCard bank={data.bank} />
        </div>
      </div>
    </div>
  )
}

function NextPayoutCard({ next, deal }: { next: PayoutRow | null; deal: Deal | null }) {
  const { t, i18n } = useTranslation()
  if (!next) {
    return (
      <section className="rounded-2xl border border-mist bg-white px-5 py-5">
        <h2 className="text-[15px] font-medium text-navy">{t('deals.payouts.nextPayout')}</h2>
        <p className="mt-3 text-[13px] text-muted">{t('deals.payouts.nothingDue')}</p>
      </section>
    )
  }
  const owner = deal?.owner_price ? Number(deal.owner_price) : null
  const difference = owner !== null && deal ? Number(deal.final_selling_price) - owner : null
  const share = difference !== null ? Number(next.amount) - difference : null
  return (
    <section className="overflow-hidden rounded-2xl border border-mist bg-white">
      <div className="flex items-center justify-between border-b border-mist px-5 py-4">
        <h2 className="text-[15px] font-medium text-navy">{t('deals.payouts.nextPayout')}</h2>
        <PayoutChip status={next.status} />
      </div>
      <div className="px-5 py-5">
        <CountUp value={Number(next.amount)} className="text-[28px] font-bold tracking-tight text-navy" />
        <p className="mt-1 text-[12px] text-muted">{t('deals.payouts.dueOn', { date: formatShortDate(next.due_at, i18n.language) })}</p>
        {next.status === 'ON_HOLD' && next.hold_reason && <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-[12px] text-danger">{next.hold_reason}</p>}
        <dl className="mt-5 space-y-2.5 text-[13px]">
          <div className="flex justify-between gap-4">
            <dt className="text-muted">{t('deals.payouts.finalPrice')}</dt>
            <dd className="font-medium text-navy tabular-nums">{formatTsh(next.final_selling_price, i18n.language)}</dd>
          </div>
          {share !== null && (
            <div className="flex justify-between gap-4">
              <dt className="text-muted">{t('deals.payouts.commissionShare')}</dt>
              <dd className="font-medium text-success tabular-nums">+{formatTsh(share, i18n.language)}</dd>
            </div>
          )}
          {difference !== null && (
            <div className="flex justify-between gap-4">
              <dt className="text-muted">{t('deals.payouts.difference')}</dt>
              <dd className="font-medium text-success tabular-nums">+{formatTsh(difference, i18n.language)}</dd>
            </div>
          )}
          <div className="flex justify-between border-t border-mist pt-3">
            <dt className="font-medium text-navy">{t('deals.payouts.net')}</dt>
            <dd className="font-bold text-navy tabular-nums">{formatTsh(next.amount, i18n.language)}</dd>
          </div>
        </dl>
        <Link to={`/lister/deals/${next.deal_id}`} className="mt-5 flex h-11 items-center justify-center rounded-xl bg-gold text-[14px] font-semibold text-navy shadow-[0_8px_24px_-10px_rgba(200,145,40,0.7)] hover:bg-gold-light">
          {t('deals.payouts.viewDeal')}
        </Link>
      </div>
    </section>
  )
}

function AccountCard({ bank }: { bank: Bank | null }) {
  const { t } = useTranslation()
  return (
    <section className="overflow-hidden rounded-2xl border border-mist bg-white">
      <div className="flex items-center justify-between border-b border-mist bg-paper/60 px-5 py-4">
        <h2 className="text-[15px] font-medium text-navy">{t('deals.payouts.account')}</h2>
        <Link to="/lister/bank" className="text-[13px] font-medium text-navy underline decoration-gold decoration-2 underline-offset-4">
          {bank ? t('deals.payouts.change') : t('deals.payouts.add')}
        </Link>
      </div>
      <div className="p-4">
        {bank ? (
          <motion.div
            whileHover={{ y: -2, rotate: -0.6 }}
            className="relative overflow-hidden rounded-xl bg-gradient-to-br from-navy via-navy-soft to-[#9a6c12] px-5 py-5 text-white shadow-lift"
          >
            <span aria-hidden="true" className="absolute -top-10 -right-10 size-32 rounded-full bg-gold/25 blur-2xl" />
            <div className="flex items-center justify-between">
              <span className="text-[15px] font-semibold">{bank.bank_name}</span>
              <span className="rounded-full bg-white/15 px-2 py-0.5 text-[10px] tracking-[0.08em] uppercase">{t('deals.payouts.payoutAccount')}</span>
            </div>
            <span aria-hidden="true" className="mt-5 block h-6 w-9 rounded-md bg-gradient-to-br from-gold-light to-gold" />
            <p className="mt-3 font-mono text-[15px] tracking-[0.18em]">•••• {bank.account_number.slice(-4)}</p>
            <p className="mt-1 text-[12px] text-white/70">{bank.account_name}</p>
          </motion.div>
        ) : (
          <p className="text-[13px] text-muted">{t('deals.payouts.noAccount')}</p>
        )}
      </div>
    </section>
  )
}

// D13: the phone layout.
function PhonePayouts({ data }: { data: Loaded }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const totals = useTotals(data.payouts)
  return (
    <div>
      <h1 className="text-[30px] font-bold tracking-tight text-navy">{t('deals.payouts.title')}</h1>
      <p className="mt-5 text-[14px] text-muted">{t('deals.payouts.allTime')}</p>
      <CountUp value={totals.paid} className="text-[32px] font-bold tracking-tight text-navy" />
      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-white px-4 py-3.5">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">{t('deals.payouts.dealsPaid')}</p>
          <p className="mt-1 text-[16px] font-semibold text-navy">{totals.paidCount}</p>
        </div>
        <div className="rounded-2xl bg-white px-4 py-3.5">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">{t('deals.payouts.nextDue')}</p>
          <p className="mt-1 text-[16px] font-semibold text-navy">{totals.next ? formatShortDate(totals.next.due_at, i18n.language) : '-'}</p>
        </div>
      </div>
      <motion.div
        initial={reduce ? false : { opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.45 }}
        className="relative mt-4 overflow-hidden rounded-3xl bg-navy px-6 py-6 text-white"
      >
        <motion.span
          aria-hidden="true"
          className="absolute inset-y-0 -left-1/3 w-1/3 bg-gradient-to-r from-transparent via-white/10 to-transparent"
          animate={reduce ? undefined : { x: ['0%', '420%'] }}
          transition={{ duration: 2.8, repeat: Infinity, repeatDelay: 2.4, ease: 'easeInOut' }}
        />
        <p className="text-[14px] text-white/75">{t('deals.payouts.totalPending')}</p>
        <CountUp value={totals.open} className="text-[30px] font-bold tracking-tight" />
        <p className="mt-1 text-[13px] text-white/65">{totals.held > 0 ? t('deals.payouts.heldNote', { count: totals.held }) : t('deals.payouts.pendingNote')}</p>
      </motion.div>
      <p className="mt-7 text-[12px] font-semibold tracking-[0.1em] text-muted uppercase">{t('deals.payouts.activity')}</p>
      <ul className="mt-3 space-y-3">
        {data.payouts.length === 0 && <li className="rounded-2xl bg-white px-5 py-6 text-center text-[13px] text-muted">{t('deals.payouts.empty')}</li>}
        {data.payouts.map((row, index) => (
          <motion.li key={row.id} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + index * 0.06 }}>
            <Link to={`/lister/deals/${row.deal_id}`} className="flex items-center gap-4 rounded-2xl bg-white px-4 py-4">
              <span className={`grid size-11 shrink-0 place-items-center rounded-full ${row.status === 'PAID' ? 'bg-success-soft text-success' : 'bg-[#fdf3e2] text-[#c07a12]'}`}>
                {row.status === 'PAID' ? <TickIcon className="size-5" /> : <ClockIcon className="size-5" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-semibold text-navy">{formatShortDate(row.paid_at ?? row.due_at, i18n.language)}</span>
                <span className="block truncate text-[12px] text-muted">{row.property_id}</span>
              </span>
              <span className="text-right">
                <span className="block text-[15px] font-semibold text-navy tabular-nums">{formatTsh(row.amount, i18n.language)}</span>
                <span className={`block text-[12px] ${row.status === 'PAID' ? 'text-success' : row.status === 'ON_HOLD' ? 'text-danger' : 'text-[#c07a12]'}`}>{t(`deals.payoutStatus.${row.status}`)}</span>
              </span>
              <ChevronRightIcon className="size-4 text-muted" />
            </Link>
          </motion.li>
        ))}
      </ul>
      <Link to="/lister/bank" className="mt-6 flex items-center gap-3 rounded-2xl border border-mist bg-white px-4 py-4">
        <ListIcon className="size-5 text-navy-soft" />
        <span className="flex-1 text-[14px] text-navy">{data.bank ? `${data.bank.bank_name} •••• ${data.bank.account_number.slice(-4)}` : t('deals.payouts.noAccount')}</span>
        <ChevronRightIcon className="size-4 text-muted" />
      </Link>
    </div>
  )
}
