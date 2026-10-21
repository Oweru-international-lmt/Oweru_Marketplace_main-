import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, ArrowLeftIcon, CheckIcon, ClockIcon, DocumentIcon, SendIcon, TickIcon, UploadIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { dealsApi, type Deal, type DealStep } from '../../lib/dealsApi'
import { errorMessage } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem } from '../../lib/files'
import { formatDate, formatShortDate, formatTsh } from '../../lib/format'
import { openSigned } from '../../lib/openSigned'
import { DOCUMENT_ACCEPT, timelineItems } from './data'
import { CountUp, DetailRow, FilePick, FileRow, NumberedProgress, PaymentChip, TickTimeline, type SubEvent } from './ui'

// LEAD-04, LEAD-05: the lister's deal, from Closing to Won. After D8 (the
// amount box, deal rows and the breakdown box) beside D6's numbered progress
// on wide screens, and D7's tick timeline on phones.

type State = { key: string; deal: Deal } | { key: string; error: string }

export function DealPage() {
  const { dealId = '' } = useParams()
  const { t } = useTranslation()
  const [state, setState] = useState<State | null>(null)
  const [version, setVersion] = useState(0)
  const key = `${dealId}:${version}`
  useDocumentTitle(t('deals.deal.title'))

  useEffect(() => {
    let live = true
    dealsApi
      .get(dealId)
      .then((deal) => live && setState({ key, deal }))
      .catch((error) => live && setState({ key, error: errorMessage(t, error) }))
    return () => {
      live = false
    }
  }, [dealId, key, t])

  if (!state || state.key !== key) return <FullPageLoader inline />
  if ('error' in state) return <Alert tone="error">{state.error}</Alert>
  return <ListerDeal deal={state.deal} onChange={() => setVersion((value) => value + 1)} />
}

function ListerDeal({ deal, onChange }: { deal: Deal; onChange: () => void }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const agent = deal.lister_kind === 'AGENT'
  const items = timelineItems(deal.steps, (step) => ({ title: t(`deals.steps.${step}.title`), body: t(`deals.steps.${step}.lister`) }))
  const events: SubEvent[] = []
  if (deal.steps.agreement_uploaded_at) events.push({ at: deal.steps.agreement_uploaded_at, text: t('deals.deal.eventUploaded'), tone: 'sent' })
  if (deal.steps.owner_paid_at) events.push({ at: deal.steps.owner_paid_at, text: t('deals.deal.eventOwnerSlip'), tone: 'done' })
  if (deal.steps.oweru_paid_at) events.push({ at: deal.steps.oweru_paid_at, text: t('deals.deal.eventOweruSlip'), tone: 'done' })
  events.sort((a, b) => b.at.localeCompare(a.at))
  const banner = deal.state === 'COMPLETE' ? 'complete' : deal.state === 'CANCELLED' ? 'cancelled' : 'open'

  return (
    <div className="pb-10">
      <Link to="/lister/deals" className="mb-4 inline-flex items-center gap-2 text-[13px] text-muted hover:text-navy">
        <ArrowLeftIcon className="size-4" />
        {t('deals.deal.back')}
      </Link>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        {/* D8: the receipt-style column. */}
        <motion.section
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="overflow-hidden rounded-2xl border border-mist bg-white"
        >
          <div className="flex items-center justify-between gap-3 px-6 pt-5">
            <p className="font-display text-[18px] font-semibold text-navy">{t('deals.deal.title')}</p>
            <p className="text-right text-[12px] leading-tight text-muted">
              {t('deals.deal.opened')}
              <br />
              {formatShortDate(deal.created_at, i18n.language)}
            </p>
          </div>
          <div className="mt-4 h-[3px] bg-gold" />
          <div className={`flex items-center gap-3 border-l-4 px-5 py-4 ${banner === 'complete' ? 'border-success bg-success-soft' : banner === 'cancelled' ? 'border-muted bg-mist/40' : 'border-gold bg-[#fdf7ec]'}`}>
            <span className={`grid size-7 place-items-center rounded-full ${banner === 'complete' ? 'bg-success text-white' : banner === 'cancelled' ? 'bg-muted text-white' : 'bg-gold text-navy'}`}>
              {banner === 'complete' ? <CheckIcon className="size-4" /> : <ClockIcon className="size-4" />}
            </span>
            <div>
              <p className={`text-[16px] font-semibold ${banner === 'complete' ? 'text-success' : 'text-navy'}`}>{t(`deals.deal.banner.${banner}`)}</p>
              <p className="text-[13px] text-navy-soft">{t(`deals.deal.bannerNote.${banner}`)}</p>
            </div>
          </div>
          <div className="px-6 py-6">
            <div className="rounded-xl border border-mist px-4 py-5 text-center">
              <p className="text-[13px] text-muted">{t('deals.deal.finalPrice')}</p>
              <p className="mt-1">
                <CountUp value={Number(deal.final_selling_price)} className="text-[30px] font-bold tracking-tight text-navy" />
              </p>
            </div>
            <h2 className="mt-7 border-b-2 border-mist pb-3 text-[17px] font-semibold text-navy">{t('deals.deal.details')}</h2>
            <DetailRow label={t('deals.deal.buyer')}>{deal.buyer_name}</DetailRow>
            <DetailRow label={t('deals.deal.property')}>
              {t(`deals.categories.${deal.property.category}`)} · {deal.property.area}
              <span className="block text-[12px] font-normal text-muted">{deal.property.property_id}</span>
            </DetailRow>
            <DetailRow label={t('deals.purchase.reference')}>
              <span className="font-mono text-[12px] break-all">{deal.payment_reference}</span>
            </DetailRow>
            <DetailRow label={t('deals.deal.date')}>{formatDate(deal.created_at, i18n.language)}</DetailRow>
            <DetailRow label={t('deals.purchase.status')}>
              <PaymentChip status={deal.payment_status} />
            </DetailRow>
            <div className="mt-6 rounded-xl border border-gold/30 bg-[#fdf9f0] px-5 py-5">
              <h3 className="text-[15px] font-semibold text-navy">{t('deals.deal.breakdown')}</h3>
              <BreakdownRow label={t('deals.deal.toOwner')} value={deal.buyer_to_owner} />
              <BreakdownRow label={t('deals.deal.toOweru')} value={deal.buyer_to_oweru} />
              {agent && deal.oweru_keeps !== undefined && <BreakdownRow label={t('deals.deal.oweruKeeps')} value={deal.oweru_keeps} muted />}
              {agent && deal.agent_payout !== undefined && <BreakdownRow label={t('deals.deal.yourPayout')} value={deal.agent_payout} strong />}
            </div>
          </div>
        </motion.section>

        <div className="space-y-6">
          <div className="hidden lg:block">
            <NumberedProgress title={t('deals.deal.progress')} items={items} events={events} action={deal.state === 'OPEN' ? <p className="text-[13px] text-[#9a6c12]">{t(`deals.next.${nextFor(items)}`)}</p> : undefined} />
          </div>
          <div className="lg:hidden">
            <TickTimeline
              items={items}
              header={t('deals.deal.timeline')}
              status={deal.state === 'COMPLETE' ? <SuccessPill label={t('deals.deal.banner.complete')} /> : <PaymentChip status={deal.payment_status} />}
            />
          </div>
          {deal.state === 'OPEN' && <ListerActions deal={deal} onChange={onChange} />}
        </div>
      </div>
    </div>
  )
}

function nextFor(items: { key: DealStep; at: string | null }[]): DealStep {
  return items.find((item) => !item.at)?.key ?? 'completed'
}

function BreakdownRow({ label, value, strong = false, muted = false }: { label: string; value: string; strong?: boolean; muted?: boolean }) {
  const { i18n } = useTranslation()
  return (
    <div className={`mt-3 flex items-center justify-between gap-4 text-[14px] ${strong ? 'border-t border-gold/30 pt-3' : ''}`}>
      <span className={muted ? 'text-muted' : 'text-navy-soft'}>{label}</span>
      <span className={`tabular-nums ${strong ? 'text-[16px] font-bold text-navy' : 'font-semibold text-navy'}`}>{formatTsh(value, i18n.language)}</span>
    </div>
  )
}

function SuccessPill({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-3 py-1.5 text-[13px] font-medium text-success">
      <TickIcon className="size-3.5" />
      {label}
    </span>
  )
}

// What the lister can do now: share the payment page, get the owner's receipt
// confirmed, and upload and confirm the signed agreement (D7's buttons).
function ListerActions({ deal, onChange }: { deal: Deal; onChange: () => void }) {
  const { t, i18n } = useTranslation()
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [reference, setReference] = useState('')
  const [exact, setExact] = useState(false)
  const agent = deal.lister_kind === 'AGENT'

  async function run(name: string, action: () => Promise<unknown>, refresh = true) {
    setBusy(name)
    setError('')
    try {
      await action()
      if (refresh) onChange()
      else setDone(name)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy('')
    }
  }

  async function share() {
    const tab = window.open('', '_blank')
    if (tab) tab.opener = null
    try {
      const { whatsapp_link } = await dealsApi.shareInstructions(deal.id)
      if (tab) tab.location.href = whatsapp_link
      else window.location.assign(whatsapp_link)
    } catch (failure) {
      tab?.close()
      setError(errorMessage(t, failure))
    }
  }

  function upload(file: File) {
    const problem = firstFileProblem([file], EVIDENCE_TYPES)
    if (problem) {
      setError(t(problem.kind === 'size' ? 'deals.fileTooBig' : 'deals.fileType', { name: problem.name }))
      return
    }
    void run('agreement', () => dealsApi.uploadAgreement(deal.id, file))
  }

  return (
    <section className="rounded-2xl border border-mist bg-white p-5 sm:p-6">
      <h2 className="text-[16px] font-semibold text-navy">{t('deals.deal.actions')}</h2>
      <div className="mt-4 space-y-4">
        {!deal.steps.oweru_paid_at && (
          <ActionBlock icon={<WhatsAppIcon className="size-5" />} title={t('deals.deal.shareTitle')} body={t('deals.deal.shareBody')}>
            <button type="button" onClick={() => void share()} className="inline-flex h-11 items-center gap-2 rounded-xl bg-[#1f7a4d] px-5 text-[14px] font-medium text-white transition-colors hover:bg-[#186640]">
              <WhatsAppIcon className="size-4" />
              {t('deals.deal.shareButton')}
            </button>
          </ActionBlock>
        )}

        {!deal.steps.owner_confirmed_at && (
          <ActionBlock icon={<SendIcon className="size-5" />} title={t(agent ? 'deals.deal.ownerLinkTitle' : 'deals.deal.ownerReceiptTitle')} body={t(agent ? 'deals.deal.ownerLinkBody' : 'deals.deal.ownerReceiptBody')}>
            {agent ? (
              done === 'owner' ? (
                <p className="flex items-center gap-2 text-[13px] text-success">
                  <TickIcon className="size-4" />
                  {t('deals.deal.ownerLinkQueued')}
                </p>
              ) : (
                <button type="button" disabled={busy === 'owner'} onClick={() => void run('owner', () => dealsApi.requestOwnerReceipt(deal.id), false)} className="inline-flex h-11 items-center gap-2 rounded-xl border border-mist px-5 text-[14px] font-medium text-navy transition-colors hover:border-navy-soft/40 disabled:opacity-60">
                  {t('deals.deal.ownerLinkButton')}
                </button>
              )
            ) : (
              <form
                className="flex flex-wrap gap-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  if (reference.trim()) void run('receipt', () => dealsApi.confirmOwnerReceipt(deal.id, reference.trim()))
                }}
              >
                <label className="min-w-0 flex-1">
                  <span className="sr-only">{t('deals.bank.reference')}</span>
                  <input value={reference} onChange={(event) => setReference(event.target.value)} placeholder={t('deals.bank.reference')} className="h-11 w-full rounded-xl border border-mist px-3.5 text-[14px] outline-none focus:border-gold focus:ring-2 focus:ring-gold/20" />
                </label>
                <button type="submit" disabled={!reference.trim() || busy === 'receipt'} className="h-11 rounded-xl bg-gold px-5 text-[14px] font-semibold text-navy disabled:opacity-60">
                  {t('deals.deal.ownerReceiptButton')}
                </button>
              </form>
            )}
          </ActionBlock>
        )}

        <ActionBlock icon={<DocumentIcon className="size-5" />} title={t('deals.deal.agreementTitle')} body={t('deals.deal.agreementBody', { price: formatTsh(deal.final_selling_price, i18n.language) })}>
          {deal.agreement_media_id && (
            <FileRow
              name={t('deals.deal.agreementFile')}
              note={deal.steps.agreement_uploaded_at ? formatShortDate(deal.steps.agreement_uploaded_at, i18n.language) : undefined}
              onOpen={() => void openSigned(() => dealsApi.document(deal.id, deal.agreement_media_id!)).catch((failure) => setError(errorMessage(t, failure)))}
            />
          )}
          {deal.agreement_approved_at ? (
            <p className="mt-3 flex items-center gap-2 text-[13px] text-success">
              <TickIcon className="size-4" />
              {t('deals.deal.agreementApproved')}
            </p>
          ) : (
            <div className="mt-3 space-y-3">
              <FilePick accept={DOCUMENT_ACCEPT} onPick={upload} disabled={busy === 'agreement'} className="inline-flex h-11 items-center gap-2 rounded-xl border border-mist px-5 text-[14px] font-medium text-navy transition-colors hover:border-navy-soft/40 disabled:opacity-60">
                <UploadIcon className="size-4" />
                {busy === 'agreement' ? t('deals.uploading') : deal.agreement_media_id ? t('deals.deal.agreementReplace') : t('deals.deal.agreementUpload')}
              </FilePick>
              {deal.agreement_media_id && !deal.agreement_price_confirmed_at && (
                <div className="rounded-xl bg-paper p-4">
                  <label className="flex items-start gap-3 text-[13px] leading-relaxed text-navy">
                    <input type="checkbox" checked={exact} onChange={(event) => setExact(event.target.checked)} className="mt-0.5 size-4 accent-[#c89128]" />
                    {t('deals.deal.exactPrice', { price: formatTsh(deal.final_selling_price, i18n.language) })}
                  </label>
                  <button type="button" disabled={!exact || busy === 'exact'} onClick={() => void run('exact', () => dealsApi.confirmAgreement(deal.id))} className="mt-3 h-11 w-full rounded-xl bg-gold text-[14px] font-semibold text-navy disabled:opacity-50">
                    {t('deals.deal.exactButton')}
                  </button>
                </div>
              )}
              {deal.agreement_price_confirmed_at && (
                <p className="flex items-center gap-2 text-[13px] text-[#9a6c12]">
                  <ClockIcon className="size-4" />
                  {t('deals.deal.agreementWaiting')}
                </p>
              )}
            </div>
          )}
        </ActionBlock>
      </div>
      {error && (
        <p role="alert" className="mt-4 flex items-center gap-2 text-[13px] text-danger">
          <AlertIcon className="size-4" />
          {error}
        </p>
      )}
    </section>
  )
}

function ActionBlock({ icon, title, body, children }: { icon: ReactNode; title: string; body: string; children: ReactNode }) {
  return (
    <div className="flex gap-4 border-t border-mist pt-4 first:border-t-0 first:pt-0">
      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-paper text-navy-soft">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-medium text-navy">{title}</p>
        <p className="mt-0.5 mb-3 text-[13px] leading-relaxed text-muted">{body}</p>
        {children}
      </div>
    </div>
  )
}
