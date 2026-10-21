import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, BanknoteIcon, ClockIcon, LockIcon, SearchIcon, TickIcon, UploadIcon, UsersIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { dealsApi, type Bank, type PayoutRow, type PayoutStatus } from '../../lib/dealsApi'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatShortDate, formatTsh } from '../../lib/format'
import { RowMenu } from '../lister/ui'
import { DOCUMENT_ACCEPT } from './data'
import { CountUp, DetailRow, FilePick, PayoutChip, SidePanel } from './ui'

// PAY-10, PAY-12, CMP-06: management pays agents. After D21: stat cards by
// status over one table of agents with amount, deal, dates and status, and
// row actions to hold, release or record a payment.

type Filter = 'ALL' | PayoutStatus

export function PayoutsDeskPage() {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const [rows, setRows] = useState<PayoutRow[] | null>(null)
  const [version, setVersion] = useState(0)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<Filter>('ALL')
  const [query, setQuery] = useState('')
  const [paying, setPaying] = useState<PayoutRow | null>(null)
  const [holding, setHolding] = useState<PayoutRow | null>(null)
  useDocumentTitle(t('deals.payoutDesk.title'))

  useEffect(() => {
    let live = true
    dealsApi
      .payouts()
      .then((list) => live && setRows(list))
      .catch((failure) => {
        if (!live) return
        setError(errorMessage(t, failure))
        setRows([])
      })
    return () => {
      live = false
    }
  }, [t, version])

  const totals = useMemo(() => {
    const all = rows ?? []
    const sum = (status: PayoutStatus[]) => all.filter((row) => status.includes(row.status)).reduce((total, row) => total + Number(row.amount), 0)
    return { all: sum(['PENDING', 'DUE', 'ON_HOLD', 'PAID']), pending: sum(['PENDING']), due: sum(['DUE']), held: sum(['ON_HOLD']), paid: sum(['PAID']), agents: new Set(all.map((row) => row.agent_name)).size }
  }, [rows])

  if (!rows) return <FullPageLoader inline />
  const shown = rows.filter((row) => (filter === 'ALL' || row.status === filter) && `${row.agent_name} ${row.property_id} ${row.listing_id}`.toLowerCase().includes(query.trim().toLowerCase()))
  const refresh = () => setVersion((value) => value + 1)

  async function release(row: PayoutRow) {
    setError('')
    try {
      await dealsApi.releasePayout(row.deal_id)
      refresh()
    } catch (failure) {
      setError(errorMessage(t, failure))
    }
  }

  const cards = [
    { label: t('deals.payoutDesk.total'), value: totals.all, icon: BanknoteIcon, tone: 'bg-[#e8eefb] text-[#3552a8]' },
    { label: t('deals.payoutStatus.PENDING'), value: totals.pending, icon: ClockIcon, tone: 'bg-[#fdf3d8] text-[#9a6c12]' },
    { label: t('deals.payoutStatus.DUE'), value: totals.due, icon: AlertIcon, tone: 'bg-[#fdecea] text-danger' },
    { label: t('deals.payoutStatus.ON_HOLD'), value: totals.held, icon: LockIcon, tone: 'bg-[#f1e9fa] text-[#6b3fa0]' },
    { label: t('deals.payoutStatus.PAID'), value: totals.paid, icon: TickIcon, tone: 'bg-success-soft text-success' },
  ]

  return (
    <div className="pb-10">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-navy">{t('deals.payoutDesk.title')}</h1>
          <p className="mt-1 text-[13px] text-muted">{t('deals.payoutDesk.subtitle', { count: totals.agents })}</p>
        </div>
        <Link to="/staff/deals" className="inline-flex h-10 items-center rounded-xl border border-mist bg-white px-4 text-[13px] font-medium text-navy hover:border-navy-soft/40">
          {t('deals.payoutDesk.toDeals')}
        </Link>
      </div>
      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {cards.map((card, index) => (
          <motion.div key={card.label} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06 }} className="rounded-xl border border-mist bg-white px-4 py-4">
            <span className={`grid size-8 place-items-center rounded-lg ${card.tone}`}>
              <card.icon className="size-4" />
            </span>
            <p className="mt-3 text-[12px] text-muted">{card.label}</p>
            <CountUp value={card.value} className="text-[19px] font-bold text-navy" />
          </motion.div>
        ))}
      </div>

      <section className="mt-4 rounded-xl border border-mist bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-mist px-5 py-4">
          <div role="radiogroup" aria-label={t('deals.payoutDesk.filter')} className="flex flex-wrap gap-1.5">
            {(['ALL', 'DUE', 'PENDING', 'ON_HOLD', 'PAID'] as Filter[]).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={filter === value}
                onClick={() => setFilter(value)}
                className={`relative rounded-lg px-3 py-1.5 text-[13px] ${filter === value ? 'font-medium text-white' : 'text-navy-soft hover:bg-paper'}`}
              >
                {filter === value && <motion.span layoutId="payout-filter" className="absolute inset-0 rounded-lg bg-navy" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
                <span className="relative">{value === 'ALL' ? t('deals.payoutDesk.all') : t(`deals.payoutStatus.${value}`)}</span>
              </button>
            ))}
          </div>
          <label className="relative block w-full sm:w-64">
            <span className="sr-only">{t('deals.payoutDesk.search')}</span>
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('deals.payoutDesk.search')} className="h-10 w-full rounded-lg border border-mist pr-9 pl-3 text-[13px] outline-none focus:border-gold" />
            <SearchIcon className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted" />
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-left text-[13px]">
            <caption className="sr-only">{t('deals.payoutDesk.title')}</caption>
            <thead>
              <tr className="border-b border-mist text-[11px] text-muted">
                {['payout', 'agent', 'amount', 'property', 'due', 'paid', 'status'].map((column) => (
                  <th key={column} scope="col" className="px-5 py-3 font-medium first:pl-5">
                    {t(`deals.payoutDesk.columns.${column}`)}
                  </th>
                ))}
                <th scope="col" className="w-12 px-3 py-3">
                  <span className="sr-only">{t('deals.payoutDesk.actions')}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-12 text-center text-muted">{t('deals.payoutDesk.empty')}</td>
                </tr>
              ) : (
                shown.map((row, index) => (
                  <motion.tr key={row.id} initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: index * 0.03 }} className="border-b border-mist/70 last:border-b-0 hover:bg-paper">
                    <td className="px-5 py-3.5">
                      <Link to={`/staff/deals/${row.deal_id}`} className="font-mono text-[12px] font-medium text-[#3552a8] hover:underline">
                        {row.id.slice(0, 8).toUpperCase()}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="flex items-center gap-2 font-medium text-navy">
                        <UsersIcon className="size-4 text-muted" />
                        {row.agent_name}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 font-semibold text-navy tabular-nums">{formatTsh(row.amount, i18n.language)}</td>
                    <td className="px-5 py-3.5 text-muted">{row.property_id}</td>
                    <td className="px-5 py-3.5 text-muted tabular-nums">{formatShortDate(row.due_at, i18n.language)}</td>
                    <td className="px-5 py-3.5 text-muted tabular-nums">{row.paid_at ? formatShortDate(row.paid_at, i18n.language) : '-'}</td>
                    <td className="px-5 py-3.5">
                      <PayoutChip status={row.status} />
                      {row.status === 'ON_HOLD' && row.hold_reason && <span className="mt-1 block max-w-[180px] truncate text-[11px] text-muted">{row.hold_reason}</span>}
                    </td>
                    <td className="px-3 py-3.5">
                      <RowMenu
                        label={t('deals.payoutDesk.actions')}
                        items={[
                          ...(row.status === 'PENDING' || row.status === 'DUE' ? [{ label: t('deals.payoutDesk.recordPaid'), onSelect: () => setPaying(row) }, { label: t('deals.payoutDesk.hold'), onSelect: () => setHolding(row), tone: 'danger' as const }] : []),
                          ...(row.status === 'ON_HOLD' ? [{ label: t('deals.payoutDesk.release'), onSelect: () => void release(row) }] : []),
                        ]}
                      />
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <SidePanel open={paying !== null} title={t('deals.payoutDesk.payTitle')} onClose={() => setPaying(null)}>
        {paying && (
          <PayForm
            row={paying}
            onDone={() => {
              setPaying(null)
              refresh()
            }}
          />
        )}
      </SidePanel>
      <SidePanel open={holding !== null} title={t('deals.payoutDesk.holdTitle')} onClose={() => setHolding(null)}>
        {holding && (
          <HoldForm
            row={holding}
            onDone={() => {
              setHolding(null)
              refresh()
            }}
          />
        )}
      </SidePanel>
    </div>
  )
}

function PayForm({ row, onDone }: { row: PayoutRow; onDone: () => void }) {
  const { t, i18n } = useTranslation()
  const [bank, setBank] = useState<Bank | null | undefined>(row.agent_bank_id ? undefined : null)
  const [reference, setReference] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!row.agent_bank_id) return
    let live = true
    dealsApi
      .agentBank(row.agent_bank_id)
      .then((value) => live && setBank(value))
      .catch(() => live && setBank(null))
    return () => {
      live = false
    }
  }, [row.agent_bank_id])

  async function submit() {
    if (!reference.trim() || !file) return
    setBusy(true)
    setError('')
    try {
      await dealsApi.payPayout(row.deal_id, reference.trim(), file)
      onDone()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="rounded-xl bg-paper px-4 py-4">
        <p className="text-[12px] text-muted">{t('deals.payoutDesk.amount')}</p>
        <CountUp value={Number(row.amount)} className="text-[26px] font-bold text-navy" />
        <p className="mt-1 text-[12px] text-muted">{t('deals.payoutDesk.frozen')}</p>
      </div>
      <p className="mt-5 text-[14px] font-semibold text-navy">{t('deals.payoutDesk.summary')}</p>
      <DetailRow label={t('deals.payoutDesk.columns.agent')}>{row.agent_name}</DetailRow>
      <DetailRow label={t('deals.payoutDesk.columns.property')}>{row.property_id}</DetailRow>
      <DetailRow label={t('deals.payouts.finalPrice')}>{formatTsh(row.final_selling_price, i18n.language)}</DetailRow>
      <DetailRow label={t('deals.payoutDesk.columns.due')}>{formatShortDate(row.due_at, i18n.language)}</DetailRow>
      <p className="mt-5 text-[14px] font-semibold text-navy">{t('deals.payoutDesk.agentBank')}</p>
      {bank === undefined ? (
        <p className="py-3 text-[13px] text-muted">{t('deals.loading')}</p>
      ) : bank ? (
        <>
          <DetailRow label={t('deals.bank.bank')}>{bank.bank_name}</DetailRow>
          <DetailRow label={t('deals.bank.name')}>{bank.account_name}</DetailRow>
          <DetailRow label={t('deals.bank.number')}>
            <span className="font-mono">{bank.account_number}</span>
          </DetailRow>
          <DetailRow label={t('deals.bank.branch')}>{bank.branch}</DetailRow>
        </>
      ) : (
        <p className="mt-2 rounded-lg bg-danger-soft px-3 py-2.5 text-[13px] text-danger">{t('deals.payoutDesk.noBank')}</p>
      )}
      <div className="mt-6 space-y-3 rounded-xl border border-mist p-4">
        <label className="block text-[13px] font-medium text-navy">
          {t('deals.bank.reference')}
          <input value={reference} onChange={(event) => setReference(event.target.value)} className="mt-1.5 h-11 w-full rounded-lg border border-mist px-3 text-[14px] outline-none focus:border-gold focus:ring-2 focus:ring-gold/20" />
        </label>
        <FilePick
          accept={DOCUMENT_ACCEPT}
          onPick={(picked) => {
            const problem = firstFileProblem([picked], EVIDENCE_TYPES)
            if (problem) setError(t(problem.kind === 'size' ? 'deals.fileTooBig' : 'deals.fileType', { name: problem.name }))
            else setFile(picked)
          }}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-dashed border-mist text-[13px] text-navy-soft"
        >
          <UploadIcon className="size-4" />
          {file ? file.name : t('deals.payoutDesk.proof')}
        </FilePick>
        {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
        <button type="button" onClick={() => void submit()} disabled={!reference.trim() || !file || busy || !bank} className="h-11 w-full rounded-xl bg-gold text-[14px] font-semibold text-navy disabled:opacity-50">
          {busy ? t('deals.saving') : t('deals.payoutDesk.recordPaid')}
        </button>
      </div>
    </div>
  )
}

function HoldForm({ row, onDone }: { row: PayoutRow; onDone: () => void }) {
  const { t, i18n } = useTranslation()
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit() {
    if (!reason.trim()) return
    setBusy(true)
    setError('')
    try {
      await dealsApi.holdPayout(row.deal_id, reason.trim())
      onDone()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      <p className="text-[14px] text-navy-soft">{t('deals.payoutDesk.holdLead', { name: row.agent_name, amount: formatTsh(row.amount, i18n.language) })}</p>
      <label className="mt-4 block text-[13px] font-medium text-navy">
        {t('deals.payoutDesk.reason')}
        <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={4} className="mt-1.5 w-full rounded-lg border border-mist px-3 py-2.5 text-[14px] outline-none focus:border-gold focus:ring-2 focus:ring-gold/20" />
      </label>
      {error && <p role="alert" className="mt-2 text-[13px] text-danger">{error}</p>}
      <button type="button" onClick={() => void submit()} disabled={!reason.trim() || busy} className="mt-4 h-11 w-full rounded-xl bg-danger text-[14px] font-semibold text-white disabled:opacity-50">
        {busy ? t('deals.saving') : t('deals.payoutDesk.hold')}
      </button>
    </div>
  )
}
