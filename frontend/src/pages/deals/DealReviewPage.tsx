import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, ArrowLeftIcon, ArrowRightIcon, BankIcon, ChevronLeftIcon, ChevronRightIcon, ClockIcon, DocumentIcon, TickIcon, UploadIcon, UserIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { dealsApi, type Deal, type Transfer } from '../../lib/dealsApi'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatShortDate, formatTsh } from '../../lib/format'
import { initials } from '../../lib/initials'
import { openSigned } from '../../lib/openSigned'
import { DOCUMENT_ACCEPT, reviewFor } from './data'
import { DetailRow, FilePick, FileRow, PaymentChip, SidePanel } from './ui'

// PAY-09, PAY-11, LEAD-05: management reviews one deal. After D20 (title with
// status chips, a step bar, the money in the main column, people on the side)
// and D19 (each transfer opens a details panel with its slips, the receiving
// bank and the confirm action).

type State = { key: string; deal: Deal; ids: string[] } | { key: string; error: string }

export function DealReviewPage() {
  const { dealId = '' } = useParams()
  const { t } = useTranslation()
  const [state, setState] = useState<State | null>(null)
  const [version, setVersion] = useState(0)
  const key = `${dealId}:${version}`
  useDocumentTitle(t('deals.review.title'))

  useEffect(() => {
    let live = true
    Promise.all([dealsApi.get(dealId), dealsApi.list()])
      .then(([deal, all]) => live && setState({ key, deal, ids: all.map((row) => row.id) }))
      .catch((error) => live && setState({ key, error: errorMessage(t, error) }))
    return () => {
      live = false
    }
  }, [dealId, key, t])

  if (!state || state.key !== key) return <FullPageLoader inline />
  if ('error' in state) return <Alert tone="error">{state.error}</Alert>
  return <Review deal={state.deal} ids={state.ids} onChange={() => setVersion((value) => value + 1)} />
}

const STEPS = ['payment', 'confirmation', 'agreement', 'completed'] as const

function stepIndex(deal: Deal) {
  const s = deal.steps
  if (deal.completed_at) return 4
  if (s.agreement_approved_at && s.owner_confirmed_at && s.oweru_confirmed_at) return 3
  if (s.owner_confirmed_at && s.oweru_confirmed_at) return 2
  if (s.owner_paid_at && s.oweru_paid_at) return 1
  return 0
}

function Review({ deal, ids, onChange }: { deal: Deal; ids: string[]; onChange: () => void }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const reduce = useReducedMotion()
  const [panel, setPanel] = useState<Transfer | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const current = stepIndex(deal)
  const reviews = reviewFor(deal)
  const position = ids.indexOf(deal.id)
  const agent = deal.lister_kind === 'AGENT'

  async function run(name: string, action: () => Promise<unknown>): Promise<boolean> {
    setBusy(name)
    setError('')
    try {
      await action()
      onChange()
      return true
    } catch (failure) {
      setError(errorMessage(t, failure))
      return false
    } finally {
      setBusy('')
    }
  }
  const open = (mediaId: string) => void openSigned(() => dealsApi.document(deal.id, mediaId)).catch((failure) => setError(errorMessage(t, failure)))

  return (
    <div className="pb-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <Link to="/staff/deals" aria-label={t('deals.review.back')} className="mt-1 grid size-9 shrink-0 place-items-center rounded-full border border-mist bg-white text-navy hover:border-navy-soft/40">
            <ArrowLeftIcon className="size-4" />
          </Link>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="font-mono text-[18px] font-semibold break-all text-navy sm:text-[22px]">{deal.payment_reference}</h1>
              <PaymentChip status={deal.payment_status} />
              <span className="inline-flex items-center gap-1 rounded-md border border-mist px-2 py-0.5 text-[12px] text-navy-soft">
                <DocumentIcon className="size-3.5" />
                {deal.agreement_approved_at ? t('deals.review.agreementOk') : t('deals.review.agreementOpen')}
              </span>
            </div>
            <p className="mt-1 text-[13px] text-muted">
              {t('deals.review.openedOn', { date: formatShortDate(deal.created_at, i18n.language) })} · {t(`deals.categories.${deal.property.category}`)} {deal.property.area} · {t(`deals.kinds.${deal.lister_kind}`)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-[13px]">
          <span className="text-muted">{t('deals.review.position', { index: position + 1, total: ids.length })}</span>
          <div className="flex overflow-hidden rounded-lg border border-mist bg-white">
            <button type="button" disabled={position <= 0} onClick={() => navigate(`/staff/deals/${ids[position - 1]}`)} aria-label={t('deals.review.previous')} className="grid size-8 place-items-center text-navy disabled:opacity-30">
              <ChevronLeftIcon className="size-4" />
            </button>
            <button type="button" disabled={position < 0 || position >= ids.length - 1} onClick={() => navigate(`/staff/deals/${ids[position + 1]}`)} aria-label={t('deals.review.next')} className="grid size-8 place-items-center border-l border-mist text-navy disabled:opacity-30">
              <ChevronRightIcon className="size-4" />
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          {/* D20's step bar. */}
          <div className="overflow-hidden rounded-xl border border-mist bg-white">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-mist bg-paper px-4 py-2 text-[12px] text-muted">
              <span>{t('deals.review.lister', { name: deal.lister_name })}</span>
              <span>{t('deals.review.buyer', { name: deal.buyer_name })}</span>
            </div>
            <ol className="grid grid-cols-4">
              {STEPS.map((step, index) => {
                const done = index < current
                const here = index === current
                return (
                  <li key={step} className="px-4 pt-3 pb-0">
                    <span className={`flex items-center gap-2 text-[13px] ${done || here ? 'font-medium text-navy' : 'text-muted'}`}>
                      {done ? <TickIcon className="size-3.5 text-success" /> : here ? <motion.span animate={reduce ? undefined : { rotate: 360 }} transition={{ duration: 2.4, repeat: Infinity, ease: 'linear' }} className="block size-3.5 rounded-full border-2 border-dashed border-gold" /> : null}
                      {t(`deals.review.steps.${step}`)}
                    </span>
                    <span className="mt-3 block h-[3px] overflow-hidden bg-mist">
                      <motion.span className="block h-full origin-left bg-navy" initial={reduce ? false : { scaleX: 0 }} animate={{ scaleX: done ? 1 : here ? 0.5 : 0 }} transition={{ duration: 0.6, delay: index * 0.15 }} />
                    </span>
                  </li>
                )
              })}
            </ol>
          </div>

          {deal.state === 'OPEN' && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-[13px] text-muted">{reviews.length > 0 ? t('deals.review.waitingOn', { count: reviews.length }) : t('deals.review.nothingYet')}</span>
              {reviews.includes('complete') && (
                <motion.button
                  type="button"
                  whileTap={{ scale: 0.97 }}
                  disabled={busy === 'complete'}
                  onClick={() => void run('complete', () => dealsApi.complete(deal.id))}
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-gold px-5 text-[14px] font-semibold text-navy shadow-[0_8px_24px_-10px_rgba(200,145,40,0.7)] hover:bg-gold-light disabled:opacity-60"
                >
                  {t('deals.review.complete')}
                  <ArrowRightIcon className="size-4" />
                </motion.button>
              )}
            </div>
          )}

          <section className="border-t border-mist pt-5">
            <div className="flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-navy">{t('deals.review.transfers')}</h2>
              <span className="text-[12px] text-muted">{t('deals.review.transfersNote')}</span>
            </div>
            <div className="mt-4 space-y-3">
              {(['OWNER', 'OWERU'] as const).map((transfer) => {
                const slips = (deal.proofs ?? []).filter((proof) => proof.transfer === transfer)
                const confirmed = transfer === 'OWNER' ? deal.steps.owner_confirmed_at : deal.steps.oweru_confirmed_at
                return (
                  <motion.button
                    key={transfer}
                    type="button"
                    whileHover={{ y: -1 }}
                    onClick={() => setPanel(transfer)}
                    className="flex w-full items-center gap-4 rounded-xl border border-mist bg-white px-4 py-4 text-left transition-shadow hover:shadow-card"
                  >
                    <span className={`grid size-12 shrink-0 place-items-center rounded-lg ${transfer === 'OWERU' ? 'bg-gold/15 text-[#9a6c12]' : 'bg-[#e8eefb] text-[#3552a8]'}`}>
                      <BankIcon className="size-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[14px] font-medium text-navy">{t(`deals.review.transfer.${transfer}`)}</span>
                      <span className="block text-[12px] text-muted">{t('deals.review.slips', { count: slips.length })}</span>
                    </span>
                    <span className="text-right">
                      <span className="block text-[15px] font-semibold text-navy tabular-nums">{formatTsh(transfer === 'OWNER' ? deal.buyer_to_owner : deal.buyer_to_oweru, i18n.language)}</span>
                      <span className={`mt-1 inline-flex items-center gap-1 text-[12px] ${confirmed ? 'text-success' : slips.length ? 'text-[#b4640a]' : 'text-muted'}`}>
                        {confirmed ? <TickIcon className="size-3.5" /> : <ClockIcon className="size-3.5" />}
                        {confirmed ? t('deals.review.confirmed') : slips.length ? t('deals.review.toCheck') : t('deals.review.notPaid')}
                      </span>
                    </span>
                    <ChevronRightIcon className="size-4 text-muted" />
                  </motion.button>
                )
              })}
            </div>
          </section>

          <section className="border-t border-mist pt-5">
            <div className="flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-navy">{t('deals.review.agreement')}</h2>
              {deal.agreement_approved_at && (
                <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-success">
                  <TickIcon className="size-4" />
                  {t('deals.review.approved')}
                </span>
              )}
            </div>
            <div className="mt-4 space-y-3">
              {deal.agreement_media_id ? (
                <FileRow name={t('deals.deal.agreementFile')} note={deal.agreement_price_confirmed_at ? t('deals.review.listerConfirmed') : t('deals.review.listerNotConfirmed')} onOpen={() => open(deal.agreement_media_id!)} />
              ) : (
                <p className="rounded-lg bg-paper px-4 py-3 text-[13px] text-muted">{t('deals.review.noAgreement')}</p>
              )}
              {reviews.includes('agreement') && <ApproveAgreement price={deal.final_selling_price} busy={busy === 'approve'} onApprove={() => void run('approve', () => dealsApi.approveAgreement(deal.id))} />}
            </div>
          </section>

          <section className="border-t border-mist pt-5">
            <div className="flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-navy">{t('deals.review.payment')}</h2>
              {deal.state === 'COMPLETE' && (
                <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-success">
                  <TickIcon className="size-4" />
                  {t('deals.paymentStatus.COMPLETE')}
                </span>
              )}
            </div>
            <div className="mt-2">
              <DetailRow label={t('deals.deal.finalPrice')} strong>{formatTsh(deal.final_selling_price, i18n.language)}</DetailRow>
              {agent && deal.owner_price && <DetailRow label={t('deals.review.ownerPrice')}>{formatTsh(deal.owner_price, i18n.language)}</DetailRow>}
              <DetailRow label={t('deals.deal.toOwner')}>{formatTsh(deal.buyer_to_owner, i18n.language)}</DetailRow>
              <DetailRow label={t('deals.deal.toOweru')}>{formatTsh(deal.buyer_to_oweru, i18n.language)}</DetailRow>
              {deal.oweru_keeps && <DetailRow label={t('deals.deal.oweruKeeps')}>{formatTsh(deal.oweru_keeps, i18n.language)}</DetailRow>}
              {agent && deal.agent_payout && <DetailRow label={t('deals.review.agentPayout')}>{formatTsh(deal.agent_payout, i18n.language)}</DetailRow>}
            </div>
          </section>

          <section className="border-t border-mist pt-5">
            <h2 className="text-[16px] font-semibold text-navy">{t('deals.review.taxReceipt')}</h2>
            {deal.tax_receipt ? (
              <div className="mt-3">
                <FileRow name={`${deal.tax_receipt.kind} ${deal.tax_receipt.number}`} note={formatShortDate(deal.tax_receipt.recorded_at, i18n.language)} onOpen={() => open(deal.tax_receipt!.media_id)} />
              </div>
            ) : deal.steps.oweru_confirmed_at ? (
              <TaxReceiptForm busy={busy === 'tax'} onSave={(number, kind, file) => void run('tax', () => dealsApi.recordTaxReceipt(deal.id, number, kind, file))} onProblem={setError} />
            ) : (
              <p className="mt-3 text-[13px] text-muted">{t('deals.review.taxLater')}</p>
            )}
          </section>
        </div>

        {/* D20's side cards. */}
        <aside className="space-y-4">
          <div className="rounded-xl border border-gold/30 bg-[#fdf7ec] px-5 py-4">
            <p className="text-[14px] font-semibold text-navy">{t('deals.review.noteTitle')}</p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-navy-soft">{reviews.length ? t(`deals.review.note.${reviews[0]}`) : deal.state === 'COMPLETE' ? t('deals.review.note.done') : t('deals.review.note.waiting')}</p>
          </div>
          <div className="overflow-hidden rounded-xl border-t-4 border-navy bg-white shadow-[0_1px_2px_rgba(15,23,42,0.06)]">
            <SideBlock title={t('deals.review.buyerCard')}>
              <Person name={deal.buyer_name} note={deal.buyer_whatsapp} whatsapp={deal.buyer_whatsapp} />
            </SideBlock>
            <SideBlock title={t('deals.review.listerCard')}>
              <Person name={deal.lister_name} note={t(`deals.kinds.${deal.lister_kind}`)} />
            </SideBlock>
            <SideBlock title={t('deals.review.property')}>
              {deal.property.cover_url && <img src={deal.property.cover_url} alt="" className="mb-3 h-28 w-full rounded-lg object-cover" />}
              <p className="text-[13px] text-navy">{deal.property.property_id}</p>
              <p className="text-[12px] text-muted">{deal.property.area}</p>
            </SideBlock>
            {deal.payout && (
              <SideBlock title={t('deals.review.payout')}>
                <p className="text-[15px] font-semibold text-navy tabular-nums">{formatTsh(deal.payout.amount, i18n.language)}</p>
                <p className="text-[12px] text-muted">{t(`deals.payoutStatus.${deal.payout.status}`)} · {formatShortDate(deal.payout.paid_at ?? deal.payout.due_at, i18n.language)}</p>
                <Link to="/staff/payouts" className="mt-2 inline-block text-[12px] font-medium text-navy underline decoration-gold decoration-2 underline-offset-4">
                  {t('deals.desk.openPayouts')}
                </Link>
              </SideBlock>
            )}
          </div>
        </aside>
      </div>

      <SidePanel open={panel !== null} title={t('deals.review.panelTitle')} onClose={() => setPanel(null)}>
        {panel && <TransferPanel deal={deal} transfer={panel} busy={busy === `confirm-${panel}`} onOpen={open} onConfirm={(reference) => void run(`confirm-${panel}`, () => dealsApi.confirmOweruReceipt(deal.id, reference)).then((ok) => ok && setPanel(null))} />}
      </SidePanel>
    </div>
  )
}

function SideBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-b border-mist px-5 py-4 last:border-b-0">
      <p className="mb-2.5 text-[13px] font-semibold text-navy">{title}</p>
      {children}
    </div>
  )
}

function Person({ name, note, whatsapp }: { name: string; note?: string; whatsapp?: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid size-10 place-items-center rounded-full bg-gold/15 text-[13px] font-semibold text-[#8a5f0e]">{initials(name) || <UserIcon className="size-4" />}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14px] font-medium text-navy">{name}</span>
        {note && <span className="block truncate text-[12px] text-muted">{note}</span>}
      </span>
      {whatsapp && (
        <a href={`https://wa.me/${whatsapp.replace(/[^\d]/g, '')}`} target="_blank" rel="noopener noreferrer" aria-label="WhatsApp" className="grid size-9 place-items-center rounded-full border border-mist text-[#1f7a4d] hover:bg-success-soft">
          <WhatsAppIcon className="size-4" />
        </a>
      )}
    </div>
  )
}

function ApproveAgreement({ price, busy, onApprove }: { price: string; busy: boolean; onApprove: () => void }) {
  const { t, i18n } = useTranslation()
  const [exact, setExact] = useState(false)
  return (
    <div className="rounded-xl border border-gold/30 bg-[#fdf9f0] p-4">
      <label className="flex items-start gap-3 text-[13px] leading-relaxed text-navy">
        <input type="checkbox" checked={exact} onChange={(event) => setExact(event.target.checked)} className="mt-0.5 size-4 accent-[#c89128]" />
        {t('deals.review.approveCheck', { price: formatTsh(price, i18n.language) })}
      </label>
      <button type="button" disabled={!exact || busy} onClick={onApprove} className="mt-3 h-10 rounded-lg bg-navy px-5 text-[13px] font-semibold text-white disabled:opacity-50">
        {t('deals.review.approve')}
      </button>
    </div>
  )
}

function TaxReceiptForm({ busy, onSave, onProblem }: { busy: boolean; onSave: (number: string, kind: 'EFD' | 'VFD', file: File) => void; onProblem: (message: string) => void }) {
  const { t } = useTranslation()
  const [number, setNumber] = useState('')
  const [kind, setKind] = useState<'EFD' | 'VFD'>('EFD')
  const [file, setFile] = useState<File | null>(null)
  function submit(event: FormEvent) {
    event.preventDefault()
    if (number.trim() && file) onSave(number.trim(), kind, file)
  }
  return (
    <form onSubmit={submit} className="mt-3 grid gap-3 rounded-xl border border-mist bg-white p-4 sm:grid-cols-[110px_minmax(0,1fr)]">
      <select value={kind} onChange={(event) => setKind(event.target.value as 'EFD' | 'VFD')} aria-label={t('deals.review.taxKind')} className="h-10 rounded-lg border border-mist px-3 text-[13px] text-navy">
        <option value="EFD">EFD</option>
        <option value="VFD">VFD</option>
      </select>
      <input value={number} onChange={(event) => setNumber(event.target.value)} placeholder={t('deals.review.taxNumber')} className="h-10 rounded-lg border border-mist px-3 text-[13px] outline-none focus:border-gold" />
      <FilePick
        accept={DOCUMENT_ACCEPT}
        onPick={(picked) => {
          const problem = firstFileProblem([picked], EVIDENCE_TYPES)
          if (problem) onProblem(t(problem.kind === 'size' ? 'deals.fileTooBig' : 'deals.fileType', { name: problem.name }))
          else setFile(picked)
        }}
        className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-dashed border-mist px-3 text-[13px] text-navy-soft sm:col-span-2"
      >
        <UploadIcon className="size-4" />
        {file ? file.name : t('deals.review.taxFile')}
      </FilePick>
      <button type="submit" disabled={!number.trim() || !file || busy} className="h-10 rounded-lg bg-navy text-[13px] font-semibold text-white disabled:opacity-50 sm:col-span-2">
        {busy ? t('deals.saving') : t('deals.review.taxSave')}
      </button>
    </form>
  )
}

// D19: the transfer, its slips, the receiving bank, then the confirm action.
function TransferPanel({ deal, transfer, busy, onOpen, onConfirm }: { deal: Deal; transfer: Transfer; busy: boolean; onOpen: (mediaId: string) => void; onConfirm: (reference: string) => void }) {
  const { t, i18n } = useTranslation()
  const [tab, setTab] = useState<'details' | 'updates'>('details')
  const [reference, setReference] = useState('')
  const slips = (deal.proofs ?? []).filter((proof) => proof.transfer === transfer)
  const confirmation = deal.confirmations?.find((row) => row.transfer === transfer)
  const bank = transfer === 'OWNER' ? deal.banks?.owner : deal.banks?.oweru
  const amount = transfer === 'OWNER' ? deal.buyer_to_owner : deal.buyer_to_oweru
  const updates = [
    ...slips.map((slip, index) => ({ at: slip.uploaded_at, text: t('deals.review.updateSlip', { number: index + 1 }) })),
    ...(confirmation ? [{ at: confirmation.confirmed_at, text: confirmation.by_owner_link ? t('deals.review.updateOwnerLink') : t('deals.review.updateConfirmed') }] : []),
  ].sort((a, b) => b.at.localeCompare(a.at))

  return (
    <div>
      <div className="flex items-center gap-4 rounded-xl border border-mist px-4 py-4">
        <span className="grid size-11 place-items-center rounded-full bg-gold/15 text-[#9a6c12]">
          <ArrowRightIcon className="size-5 -rotate-45" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-medium text-navy">{t(`deals.review.transfer.${transfer}`)}</p>
          <p className="text-[12px] text-muted">{confirmation ? t('deals.review.confirmed') : t('deals.review.toCheck')}</p>
        </div>
        <p className="text-[18px] font-bold text-navy tabular-nums">{formatTsh(amount, i18n.language)}</p>
      </div>

      <div role="tablist" className="mt-5 flex gap-6 border-b border-mist">
        {(['details', 'updates'] as const).map((name) => (
          <button key={name} type="button" role="tab" aria-selected={tab === name} onClick={() => setTab(name)} className={`relative pb-2.5 text-[14px] ${tab === name ? 'font-medium text-navy' : 'text-muted'}`}>
            {t(`deals.review.tab.${name}`)}
            {tab === name && <motion.span layoutId="transfer-tab" className="absolute inset-x-0 -bottom-px h-0.5 bg-navy" />}
          </button>
        ))}
      </div>

      {tab === 'details' ? (
        <div className="mt-4">
          <p className="text-[14px] font-semibold text-navy">{t('deals.review.transferDetails')}</p>
          <DetailRow label={t('deals.purchase.reference')}>
            <span className="font-mono text-[12px] break-all">{deal.payment_reference}</span>
          </DetailRow>
          <DetailRow label={t('deals.purchase.status')}>
            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium ${confirmation ? 'bg-success-soft text-success' : 'bg-[#fdf3e2] text-[#b4640a]'}`}>
              {confirmation ? <TickIcon className="size-3" /> : <ClockIcon className="size-3" />}
              {confirmation ? t('deals.review.confirmed') : t('deals.review.toCheck')}
            </span>
          </DetailRow>
          <DetailRow label={t('deals.review.from')}>{deal.buyer_name}</DetailRow>
          {confirmation && <DetailRow label={t('deals.bank.reference')}>{confirmation.bank_reference}</DetailRow>}
          {confirmation && <DetailRow label={t('deals.review.confirmedOn')}>{formatShortDate(confirmation.confirmed_at, i18n.language)}</DetailRow>}

          <p className="mt-5 text-[14px] font-semibold text-navy">{t('deals.review.bankDetails')}</p>
          <DetailRow label={t('deals.bank.bank')}>{bank?.bank_name ?? '-'}</DetailRow>
          <DetailRow label={t('deals.bank.name')}>{bank?.account_name ?? '-'}</DetailRow>
          <DetailRow label={t('deals.bank.number')}>{bank?.account_number ?? '-'}</DetailRow>

          <p className="mt-5 mb-2 text-[14px] font-semibold text-navy">{t('deals.review.slipsTitle')}</p>
          {slips.length === 0 ? <p className="text-[13px] text-muted">{t('deals.review.noSlip')}</p> : <div className="space-y-2">{slips.map((slip, index) => <FileRow key={slip.media_id} name={t('deals.purchase.slipName', { number: index + 1 })} note={formatShortDate(slip.uploaded_at, i18n.language)} onOpen={() => onOpen(slip.media_id)} />)}</div>}

          {!confirmation && transfer === 'OWERU' && slips.length > 0 && (
            <form
              className="mt-6 rounded-xl bg-paper p-4"
              onSubmit={(event) => {
                event.preventDefault()
                if (reference.trim()) onConfirm(reference.trim())
              }}
            >
              <label className="block text-[13px] font-medium text-navy">
                {t('deals.review.statementReference')}
                <input value={reference} onChange={(event) => setReference(event.target.value)} className="mt-1.5 h-11 w-full rounded-lg border border-mist bg-white px-3 text-[14px] outline-none focus:border-gold focus:ring-2 focus:ring-gold/20" />
              </label>
              <p className="mt-2 text-[12px] text-muted">{t('deals.review.statementNote', { amount: formatTsh(amount, i18n.language) })}</p>
              <button type="submit" disabled={!reference.trim() || busy} className="mt-3 h-11 w-full rounded-xl bg-gold text-[14px] font-semibold text-navy disabled:opacity-50">
                {busy ? t('deals.saving') : t('deals.review.confirmMoney')}
              </button>
            </form>
          )}
          {!confirmation && transfer === 'OWNER' && (
            <p className="mt-6 flex items-start gap-2 rounded-xl bg-[#e8eefb] px-4 py-3 text-[13px] text-[#3552a8]">
              <AlertIcon className="mt-0.5 size-4 shrink-0" />
              {t(deal.lister_kind === 'AGENT' ? 'deals.review.ownerByLink' : 'deals.review.ownerInAccount')}
            </p>
          )}
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {updates.length === 0 && <li className="text-[13px] text-muted">{t('deals.review.noUpdates')}</li>}
          {updates.map((update) => (
            <li key={`${update.at}-${update.text}`} className="flex items-start gap-3 text-[13px]">
              <span className="mt-1 size-2 shrink-0 rounded-full bg-gold" />
              <span className="flex-1 text-navy">{update.text}</span>
              <span className="text-muted tabular-nums">{formatShortDate(update.at, i18n.language)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
