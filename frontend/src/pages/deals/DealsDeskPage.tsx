import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, ArrowRightIcon, ChevronRightIcon, ClockIcon, LockIcon, TickIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { dealsApi, type Deal, type PayoutRow } from '../../lib/dealsApi'
import { errorMessage } from '../../lib/errors'
import { formatShortDate, formatTsh } from '../../lib/format'
import { pipelineStage, reviewFor, type PipelineStage, type ReviewKind } from './data'
import { CountUp } from './ui'

// PAY-09 to PAY-12, LEAD-05: management's deals desk. After D18: four stat
// cards, "needs your review" first, the pipeline as four boxes with arrows,
// then payout status with the next payment date.

const REVIEW_CHIP: Record<ReviewKind, string> = {
  oweruSlip: 'bg-[#fdf3e2] text-[#b4640a]',
  agreement: 'bg-[#fdf3e2] text-[#b4640a]',
  taxReceipt: 'bg-[#e8eefb] text-[#3552a8]',
  complete: 'bg-success-soft text-success',
}

const STAGES: PipelineStage[] = ['waiting', 'slips', 'confirmed', 'complete']

export function DealsDeskPage() {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const navigate = useNavigate()
  const [data, setData] = useState<{ deals: Deal[]; payouts: PayoutRow[] } | null>(null)
  const [error, setError] = useState('')
  useDocumentTitle(t('deals.desk.title'))

  useEffect(() => {
    let live = true
    Promise.all([dealsApi.list(), dealsApi.payouts().catch(() => [] as PayoutRow[])])
      .then(([deals, payouts]) => live && setData({ deals, payouts }))
      .catch((failure) => {
        if (!live) return
        setError(errorMessage(t, failure))
        setData({ deals: [], payouts: [] })
      })
    return () => {
      live = false
    }
  }, [t])

  const view = useMemo(() => {
    if (!data) return null
    const open = data.deals.filter((deal) => deal.state === 'OPEN')
    const reviews = open.flatMap((deal) => reviewFor(deal).map((kind) => ({ deal, kind })))
    const stages = Object.fromEntries(STAGES.map((stage) => [stage, data.deals.filter((deal) => pipelineStage(deal) === stage).length])) as Record<PipelineStage, number>
    const waitingMoney = open.filter((deal) => deal.steps.oweru_paid_at && !deal.steps.oweru_confirmed_at).reduce((sum, deal) => sum + Number(deal.buyer_to_oweru), 0)
    const kept = data.deals.filter((deal) => deal.state === 'COMPLETE').reduce((sum, deal) => sum + Number(deal.oweru_keeps ?? 0), 0)
    const payoutSum = (status: PayoutRow['status'][]) => data.payouts.filter((row) => status.includes(row.status))
    const nextPayout = data.payouts.filter((row) => row.status === 'PENDING' || row.status === 'DUE').sort((a, b) => a.due_at.localeCompare(b.due_at))[0]
    return { open, reviews, stages, waitingMoney, kept, paid: payoutSum(['PAID']), queued: payoutSum(['PENDING', 'DUE']), held: payoutSum(['ON_HOLD']), nextPayout }
  }, [data])

  if (!data || !view) return <FullPageLoader inline />
  const total = (rows: PayoutRow[]) => rows.reduce((sum, row) => sum + Number(row.amount), 0)
  const cards = [
    { label: t('deals.desk.openDeals'), value: <span>{view.open.length} <span className="text-muted">/ {data.deals.length}</span></span>, note: t('deals.desk.openNote', { count: view.stages.complete }) },
    { label: t('deals.desk.toConfirm'), value: <CountUp value={view.waitingMoney} />, note: t('deals.desk.toConfirmNote') },
    { label: t('deals.desk.kept'), value: <CountUp value={view.kept} className="text-success" />, note: t('deals.desk.keptNote') },
    { label: t('deals.desk.needsReview'), value: <span className="text-[#c2410c]">{view.reviews.length}</span>, note: t('deals.desk.needsReviewNote') },
  ]

  return (
    <div className="pb-10">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-navy">{t('deals.desk.title')}</h1>
          <p className="mt-1 text-[13px] text-muted">{t('deals.desk.subtitle', { open: view.open.length, review: view.reviews.length })}</p>
        </div>
        <div className="flex items-center gap-3">
          {view.reviews.length > 0 && <span className="text-[12px] font-medium text-[#c2410c]">{t('deals.desk.resolve', { count: view.reviews.length })}</span>}
          <Link to="/staff/payouts" className="inline-flex h-10 items-center gap-2 rounded-xl border border-mist bg-white px-4 text-[13px] font-medium text-navy hover:border-navy-soft/40">
            <LockIcon className="size-4" />
            {t('deals.desk.payouts')}
          </Link>
        </div>
      </div>
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card, index) => (
          <motion.div key={card.label} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.07 }} className="rounded-xl border border-mist bg-white px-5 py-4">
            <p className="text-[13px] text-navy-soft">{card.label}</p>
            <p className="mt-1.5 text-[26px] font-bold tracking-tight text-navy tabular-nums">{card.value}</p>
            <p className="mt-0.5 text-[12px] text-muted">{card.note}</p>
          </motion.div>
        ))}
      </div>

      <section className="mt-4 rounded-xl border border-mist bg-white px-5 py-5">
        <h2 className="text-[15px] font-semibold text-navy">
          {t('deals.desk.reviewTitle')} <span className="text-muted">· {view.reviews.length}</span>
        </h2>
        <div className="mt-3 hidden grid-cols-[150px_minmax(0,1fr)_140px_150px_24px] px-3 text-[11px] text-muted sm:grid">
          <span>{t('deals.desk.columns.reference')}</span>
          <span>{t('deals.desk.columns.issue')}</span>
          <span className="text-right">{t('deals.desk.columns.amount')}</span>
          <span className="pl-4">{t('deals.desk.columns.status')}</span>
        </div>
        <ul className="mt-2 space-y-1.5">
          {view.reviews.length === 0 && <li className="rounded-lg bg-paper px-4 py-6 text-center text-[13px] text-muted">{t('deals.desk.nothing')}</li>}
          {view.reviews.map(({ deal, kind }, index) => (
            <motion.li key={`${deal.id}-${kind}`} initial={reduce ? false : { opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + index * 0.05 }}>
              <button
                type="button"
                onClick={() => navigate(`/staff/deals/${deal.id}`)}
                className="grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 rounded-lg bg-[#f3f5f9] px-3 py-3 text-left text-[13px] transition-colors hover:bg-[#e9edf4] sm:grid-cols-[150px_minmax(0,1fr)_140px_150px_24px]"
              >
                <span className="truncate font-semibold text-navy" title={deal.payment_reference}>{deal.property.property_id}</span>
                <span className="col-span-2 truncate text-navy-soft sm:col-span-1">{t(`deals.desk.issue.${kind}`, { area: deal.property.area })}</span>
                <span className="text-right font-semibold text-navy tabular-nums">{formatTsh(kind === 'oweruSlip' ? deal.buyer_to_oweru : deal.final_selling_price, i18n.language)}</span>
                <span className="sm:pl-4">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${REVIEW_CHIP[kind]}`}>
                    {kind === 'complete' ? <TickIcon className="size-3" /> : <ClockIcon className="size-3" />}
                    {t(`deals.desk.chip.${kind}`)}
                  </span>
                </span>
                <ChevronRightIcon className="hidden size-4 text-muted sm:block" />
              </button>
            </motion.li>
          ))}
        </ul>
      </section>

      <section className="mt-4 rounded-xl border border-mist bg-white px-5 py-5">
        <h2 className="text-[15px] font-semibold text-navy">{t('deals.desk.pipeline')}</h2>
        <ol className="mt-4 grid items-stretch gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr]">
          {STAGES.map((stage, index) => (
            <li key={stage} className="contents">
              {index > 0 && (
                <motion.span aria-hidden="true" initial={reduce ? false : { opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + index * 0.15 }} className="hidden place-items-center text-success md:grid">
                  <ArrowRightIcon className="size-5" />
                </motion.span>
              )}
              <motion.div initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 + index * 0.15 }} className="rounded-lg bg-[#f3f5f9] px-4 py-3.5">
                <p className="text-[12px] text-navy-soft">
                  {index + 1} · {t(`deals.desk.stage.${stage}`)}
                </p>
                <p className="mt-1 text-[22px] font-bold text-navy tabular-nums">{view.stages[stage]}</p>
                <span className={`mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${stage === 'complete' ? 'bg-success-soft text-success' : 'bg-[#e8eefb] text-[#3552a8]'}`}>
                  {stage === 'complete' ? <TickIcon className="size-3" /> : <ClockIcon className="size-3" />}
                  {t(`deals.desk.stageNote.${stage}`)}
                </span>
              </motion.div>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-4 rounded-xl border border-mist bg-white px-5 py-5">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-navy">{t('deals.desk.payoutStatus')}</h2>
          <Link to="/staff/payouts" className="text-[13px] font-medium text-navy underline decoration-gold decoration-2 underline-offset-4">
            {t('deals.desk.openPayouts')}
          </Link>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {[
            { rows: view.paid, chip: 'bg-success-soft text-success', icon: TickIcon, label: t('deals.payoutStatus.PAID') },
            { rows: view.queued, chip: 'bg-[#e8eefb] text-[#3552a8]', icon: ClockIcon, label: t('deals.desk.queued') },
            { rows: view.held, chip: 'bg-[#fdf3e2] text-[#b4640a]', icon: AlertIcon, label: t('deals.payoutStatus.ON_HOLD') },
          ].map((tile) => (
            <div key={tile.label} className="rounded-lg bg-[#f3f5f9] px-4 py-3.5">
              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${tile.chip}`}>
                <tile.icon className="size-3" />
                {tile.label}
              </span>
              <p className="mt-2 text-[20px] font-bold text-navy tabular-nums">{formatTsh(total(tile.rows), i18n.language)}</p>
              <p className="text-[12px] text-muted">{t('deals.desk.agents', { count: tile.rows.length })}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 rounded-lg bg-[#f3f5f9] px-4 py-3.5">
          <p className="text-[12px] text-navy-soft">{t('deals.desk.nextPayment')}</p>
          <p className="mt-0.5 text-[22px] font-bold text-navy">{view.nextPayout ? formatShortDate(view.nextPayout.due_at, i18n.language) : '-'}</p>
          {view.nextPayout && (
            <p className="text-[12px] text-muted">
              {formatTsh(view.nextPayout.amount, i18n.language)} · {view.nextPayout.agent_name}
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
