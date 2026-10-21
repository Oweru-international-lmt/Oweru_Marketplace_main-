import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, ArrowLeftIcon, BankIcon, ClockIcon, CopyIcon, InfoIcon, TickIcon, UploadIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { dealsApi, type Deal, type Instructions, type Transfer } from '../../lib/dealsApi'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatDate, formatShortDate, formatTsh } from '../../lib/format'
import { openSigned } from '../../lib/openSigned'
import { DOCUMENT_ACCEPT } from './data'
import { CopyValue, CountUp, DetailRow, FilePick, FileRow, PaymentChip, ThreeStepBar } from './ui'

// PAY-06, PAY-07: the buyer's purchase. After D3 (ticked steps over a receipt
// card) with each transfer as a D1 bank card, and D2's upload then
// pending-review states for the slips.

type State = { key: string; deal: Deal; instructions: Instructions | null } | { key: string; error: string }

export function PurchasePage() {
  const { dealId = '' } = useParams()
  const { t } = useTranslation()
  const [state, setState] = useState<State | null>(null)
  const [version, setVersion] = useState(0)
  const key = `${dealId}:${version}`
  useDocumentTitle(t('deals.purchase.title'))

  useEffect(() => {
    let live = true
    Promise.all([dealsApi.get(dealId), dealsApi.instructions(dealId).catch(() => null)])
      .then(([deal, instructions]) => live && setState({ key, deal, instructions }))
      .catch((error) => live && setState({ key, error: errorMessage(t, error) }))
    return () => {
      live = false
    }
  }, [dealId, key, t])

  if (!state || state.key !== key) return <FullPageLoader inline />
  if ('error' in state) return <Alert tone="error">{state.error}</Alert>
  return <Purchase deal={state.deal} instructions={state.instructions} onChange={() => setVersion((value) => value + 1)} />
}

function Purchase({ deal, instructions, onChange }: { deal: Deal; instructions: Instructions | null; onChange: () => void }) {
  const { t, i18n } = useTranslation()
  const steps = deal.steps
  const paid = steps.owner_paid_at && steps.oweru_paid_at ? [steps.owner_paid_at, steps.oweru_paid_at].sort().at(-1)! : null
  const confirmed = steps.owner_confirmed_at && steps.oweru_confirmed_at ? [steps.owner_confirmed_at, steps.oweru_confirmed_at].sort().at(-1)! : null
  const note = !paid ? t('deals.purchase.notePay') : !confirmed ? t('deals.purchase.noteConfirm') : !deal.completed_at ? t('deals.purchase.noteAgreement') : t('deals.purchase.noteDone')

  return (
    <div className="mx-auto max-w-[620px] pb-10">
      <Link to="/purchases" className="mb-4 inline-flex items-center gap-2 text-[13px] text-muted hover:text-navy">
        <ArrowLeftIcon className="size-4" />
        {t('deals.purchase.back')}
      </Link>
      <h1 className="text-center text-[22px] font-semibold text-navy">{t('deals.purchase.title')}</h1>

      {/* D3: the receipt card with the three steps on top. */}
      <section className="relative mt-6 overflow-hidden rounded-2xl bg-white shadow-card">
        <div className="px-5 pt-7 pb-5 sm:px-8">
          <ThreeStepBar
            steps={[
              { label: t('deals.purchase.stepPaid'), at: paid },
              { label: t('deals.purchase.stepConfirmed'), at: confirmed },
              { label: t('deals.purchase.stepDone'), at: deal.completed_at },
            ]}
            note={note}
          />
          <div className="mt-6 flex items-center gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-gold/15 text-[#9a6c12]">
              <BankIcon className="size-5" />
            </span>
            <span className="flex-1 text-[14px] whitespace-nowrap text-muted sm:text-[15px]">{t('deals.purchase.total')}</span>
            <CountUp value={Number(deal.final_selling_price)} className="text-[19px] font-semibold whitespace-nowrap text-navy sm:text-[22px]" />
          </div>
          <div className="mt-3">
            <DetailRow label={t('deals.purchase.toOwner')}>{formatTsh(deal.buyer_to_owner, i18n.language)}</DetailRow>
            <DetailRow label={t('deals.purchase.toOweru')}>{formatTsh(deal.buyer_to_oweru, i18n.language)}</DetailRow>
          </div>
        </div>
        <div className="relative border-t border-mist">
          <span className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full border border-mist bg-white px-5 py-1.5 text-[12px] text-muted">
            {formatDate(deal.created_at, i18n.language)}
          </span>
        </div>
        <div className="px-5 pt-7 pb-6 sm:px-8">
          <DetailRow label={t('deals.purchase.status')}>
            <PaymentChip status={deal.payment_status} />
          </DetailRow>
          <DetailRow label={t('deals.purchase.property')}>
            {t(`deals.categories.${deal.property.category}`)} · {deal.property.area}
          </DetailRow>
          <DetailRow label={t('deals.purchase.propertyId')}>{deal.property.property_id}</DetailRow>
          <DetailRow label={t('deals.purchase.lister')}>{deal.lister_name}</DetailRow>
        </div>
        {/* The torn receipt edge. */}
        <div aria-hidden="true" className="h-4 bg-[radial-gradient(circle_at_10px_16px,var(--color-paper)_9px,transparent_10px)] bg-[length:20px_16px] bg-repeat-x" />
      </section>
      <div className="mt-5 px-2 text-[14px]">
        <span className="block text-muted">{t('deals.purchase.reference')}</span>
        <CopyValue value={deal.payment_reference} label={t('deals.purchase.reference')} mono />
      </div>

      {deal.state === 'OPEN' && instructions ? (
        <div className="mt-8 space-y-6">
          <h2 className="text-[17px] font-semibold text-navy">{t('deals.purchase.howToPay')}</h2>
          <p className="-mt-3 text-[14px] leading-relaxed text-muted">{t('deals.purchase.howToPayNote')}</p>
          <TransferCard deal={deal} transfer="OWNER" amount={instructions.owner.amount} bank={instructions.owner.bank} onChange={onChange} />
          <TransferCard deal={deal} transfer="OWERU" amount={instructions.oweru.amount} bank={instructions.oweru.bank} reference={instructions.oweru.reference} onChange={onChange} />
          <p className="text-center text-[12px] text-muted">{t('deals.purchase.notTax')}</p>
        </div>
      ) : (
        deal.state === 'OPEN' && <p className="mt-8 rounded-xl bg-[#fdf7ec] px-4 py-3 text-[13px] text-[#7a5410]">{t('deals.purchase.noInstructions')}</p>
      )}
    </div>
  )
}

// D1 + D2: one transfer's bank card, then its slip and review state.
function TransferCard({ deal, transfer, amount, bank, reference, onChange }: {
  deal: Deal
  transfer: Transfer
  amount: string
  bank: Instructions['owner']['bank']
  reference?: string
  onChange: () => void
}) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const proofs = (deal.proofs ?? []).filter((proof) => proof.transfer === transfer)
  const confirmedAt = transfer === 'OWNER' ? deal.steps.owner_confirmed_at : deal.steps.oweru_confirmed_at
  const name = t(`deals.purchase.transfer.${transfer}`)

  async function send(file: File) {
    const problem = firstFileProblem([file], EVIDENCE_TYPES)
    if (problem) {
      setError(t(problem.kind === 'size' ? 'deals.fileTooBig' : 'deals.fileType', { name: problem.name }))
      return
    }
    setBusy(true)
    setError('')
    try {
      await dealsApi.submitProof(deal.id, transfer, file)
      onChange()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  async function copyAll() {
    const text = [name, formatTsh(amount, i18n.language), bank.bank_name, bank.account_name, bank.account_number, bank.branch, reference].filter(Boolean).join('\n')
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Ignore: each value still has its own copy button.
    }
  }

  return (
    <motion.section
      initial={reduce ? false : { opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="overflow-hidden rounded-2xl border border-mist bg-white"
    >
      <div className="flex items-center justify-between gap-4 border-b border-mist px-5 py-4">
        <span className="grid size-11 place-items-center rounded-full bg-gradient-to-br from-gold/25 to-[#e8eefb] text-navy">
          <BankIcon className="size-5" />
        </span>
        <div className="text-right">
          <p className="text-[13px] text-muted">{name}</p>
          <p className="text-[18px] font-semibold text-navy tabular-nums">{formatTsh(amount, i18n.language)}</p>
        </div>
      </div>
      <div className="px-5 py-5">
        <h3 className="text-[16px] font-semibold text-navy">{t('deals.purchase.bankTransfer')}</h3>
        <p className="mt-1 text-[13px] text-muted">{t(`deals.purchase.bankNote.${transfer}`)}</p>
        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-4 rounded-xl bg-paper px-4 py-4">
          <div>
            <p className="text-[12px] text-muted">{t('deals.bank.number')}</p>
            <CopyValue value={bank.account_number ?? ''} label={t('deals.bank.number')} />
          </div>
          <div className="text-right">
            <p className="text-[12px] text-muted">{t('deals.bank.bank')}</p>
            <p className="pt-1 text-[15px] font-semibold text-navy uppercase">{bank.bank_name}</p>
          </div>
          <div>
            <p className="text-[12px] text-muted">{t('deals.bank.name')}</p>
            <p className="pt-1 text-[15px] font-semibold text-navy">{bank.account_name}</p>
          </div>
          <div className="text-right">
            <p className="text-[12px] text-muted">{t('deals.bank.branch')}</p>
            <p className="pt-1 text-[15px] font-semibold text-navy">{bank.branch}</p>
          </div>
          {reference && (
            <div className="col-span-2 border-t border-mist pt-3">
              <p className="text-[12px] text-muted">{t('deals.purchase.reference')}</p>
              <CopyValue value={reference} label={t('deals.purchase.reference')} mono />
            </div>
          )}
        </div>

        <AnimatePresence mode="wait" initial={false}>
          {confirmedAt ? (
            <motion.div key="confirmed" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="mt-5 flex items-center gap-3 rounded-xl bg-success-soft px-4 py-3 text-[13px] text-success">
              <TickIcon className="size-4 shrink-0" />
              {t(`deals.purchase.confirmed.${transfer}`, { date: formatShortDate(confirmedAt, i18n.language) })}
            </motion.div>
          ) : proofs.length > 0 ? (
            <motion.div key="pending" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-5 space-y-3">
              <p className="flex items-center gap-2 text-[13px] text-muted">
                {t('deals.purchase.statusLabel')}
                <span className="rounded-md bg-[#fdf3d8] px-2 py-0.5 text-[12px] font-medium text-[#7a5410]">{t('deals.purchase.pendingReview')}</span>
              </p>
              <p className="text-[13px] font-medium text-navy">{t('deals.purchase.proofUploaded')}</p>
              {proofs.map((proof, index) => (
                <FileRow
                  key={proof.media_id}
                  name={t('deals.purchase.slipName', { number: index + 1 })}
                  note={formatShortDate(proof.uploaded_at, i18n.language)}
                  onOpen={() => void openSigned(() => dealsApi.document(deal.id, proof.media_id)).catch((failure) => setError(errorMessage(t, failure)))}
                />
              ))}
              <div className="flex items-center gap-2.5 rounded-lg bg-[#fdf7ec] px-3.5 py-2.5 text-[13px] text-[#9a6c12]">
                <ClockIcon className="size-4 shrink-0" />
                {t(`deals.purchase.reviewing.${transfer}`)}
              </div>
              <FilePick accept={DOCUMENT_ACCEPT} onPick={(file) => void send(file)} disabled={busy} className="text-[13px] font-medium text-navy underline decoration-gold decoration-2 underline-offset-4">
                {busy ? t('deals.uploading') : t('deals.purchase.uploadAnother')}
              </FilePick>
            </motion.div>
          ) : (
            <motion.div key="pay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-5">
              <p className="flex items-center justify-center gap-1.5 text-[12px] text-[#9a6c12]">
                <InfoIcon className="size-3.5" />
                {t('deals.purchase.onlyAfter')}
              </p>
              <FilePick
                accept={DOCUMENT_ACCEPT}
                onPick={(file) => void send(file)}
                disabled={busy}
                className="mt-3 inline-flex h-12 w-full items-center justify-center gap-2.5 rounded-xl bg-navy px-6 font-display text-[15px] font-semibold tracking-wide text-white transition-colors hover:bg-navy-soft disabled:opacity-70"
              >
                {busy ? <span className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden="true" /> : <UploadIcon className="size-4" />}
                {busy ? t('deals.uploading') : t('deals.purchase.uploadSlip', { amount: formatTsh(amount, i18n.language) })}
              </FilePick>
              <button type="button" onClick={() => void copyAll()} className="mt-3 inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-mist text-[14px] font-medium text-navy transition-colors hover:border-navy-soft/40">
                <CopyIcon className="size-4" />
                {t('deals.purchase.copyAll')}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
        {error && (
          <p role="alert" className="mt-3 flex items-center gap-2 text-[13px] text-danger">
            <AlertIcon className="size-4" />
            {error}
          </p>
        )}
      </div>
    </motion.section>
  )
}
