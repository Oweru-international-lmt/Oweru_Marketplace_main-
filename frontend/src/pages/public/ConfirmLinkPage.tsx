import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState, type ReactNode, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeftIcon, ArrowRightIcon, ChevronRightIcon, ClockIcon, CloseIcon, TickIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ApiError } from '../../lib/api'
import { whatsappLink } from '../../lib/config'
import { confirmApi, type Bank, type Confirmation, type Decision } from '../../lib/confirmApi'
import { errorMessage } from '../../lib/errors'
import { formatShortDate, formatTsh } from '../../lib/format'
import { scopeText, type ScopeSnapshot } from '../../lib/servicesApi'

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; confirmation: Confirmation }
  | { kind: 'done'; confirmation: Confirmation | null; decision: Decision; at: string }
  | { kind: 'invalid' }
  | { kind: 'error'; message: string }

type Answer = (decision: Decision, extra?: { bank?: Bank; bank_reference?: string }) => Promise<void>

// OWNER_CONFIRMATION_URL lands here with ?delivery=&token= (ACC-01, PAY-05,
// PAY-08, FUL-03). The phone link keeps its card; the owner's price (after K1,
// K2, K3), the money received (K5) and full check consent (K8) each get their
// own screen, and every answer ends on K11's success card.
export function ConfirmLinkPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const delivery = params.get('delivery') ?? ''
  const token = params.get('token') ?? ''
  const consent = params.get('purpose') === 'FULL_CHECK_CONSENT'
  const [state, setState] = useState<State>(() => (delivery && token ? { kind: 'loading' } : { kind: 'invalid' }))
  useDocumentTitle(t('confirmLink.title'))

  useEffect(() => {
    if (!delivery || !token) return
    let live = true
    confirmApi.open(delivery, token, consent).then(
      (confirmation) => live && setState({ kind: 'ready', confirmation }),
      (caught) => live && setState(failed(t, caught)),
    )
    return () => {
      live = false
    }
  }, [delivery, token, consent, t])

  const confirmation = state.kind === 'ready' ? state.confirmation : null
  const answer: Answer = async (decision, extra = {}) => {
    try {
      await confirmApi.decide(delivery, token, decision, extra, consent)
      setState({ kind: 'done', confirmation, decision, at: new Date().toISOString() })
    } catch (caught) {
      setState(failed(t, caught))
      throw caught
    }
  }

  if (state.kind === 'done') return <Screen><Done state={state} delivery={delivery} /></Screen>
  if (state.kind === 'ready' && state.confirmation.purpose === 'OWNER_PRICE') return <Screen><OwnerPrice confirmation={state.confirmation} onAnswer={answer} /></Screen>
  if (state.kind === 'ready' && state.confirmation.purpose === 'OWNER_RECEIPT') return <Screen><OwnerReceipt confirmation={state.confirmation} onAnswer={answer} /></Screen>
  if (state.kind === 'ready' && state.confirmation.purpose === 'FULL_CHECK_CONSENT') return <Screen><Consent confirmation={state.confirmation} onAnswer={answer} /></Screen>
  return <StatusCard state={state} onAnswer={answer} />
}

function Screen({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[440px] px-4 py-8 sm:py-12">
      <div className="flex min-h-[640px] flex-col overflow-hidden rounded-[28px] bg-white shadow-[0_20px_50px_-24px_rgba(15,23,42,0.35)] ring-1 ring-mist">{children}</div>
    </div>
  )
}

function failed(t: Parameters<typeof errorMessage>[0], caught: unknown): State {
  return caught instanceof ApiError && (caught.status === 403 || caught.status === 404) ? { kind: 'invalid' } : { kind: 'error', message: errorMessage(t, caught) }
}

const text = (value: unknown) => (typeof value === 'string' || typeof value === 'number' ? String(value) : '')

// ---------------------------------------------------------------- phone, loading and failures (unchanged card)

function StatusCard({ state, onAnswer }: { state: State; onAnswer: Answer }) {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)
  const phone = state.kind === 'ready' && state.confirmation.purpose === 'PHONE'
  const tone = state.kind === 'invalid' || state.kind === 'error' ? 'bg-danger-soft text-danger' : 'bg-gold/15 text-[#9a6c12]'

  async function confirm() {
    setBusy(true)
    await onAnswer('CONFIRM').catch(() => undefined)
    setBusy(false)
  }

  return (
    <div className="mx-auto w-full max-w-[420px] px-4 py-10 sm:py-16">
      <div className="flex min-h-[520px] flex-col items-center rounded-[28px] bg-white px-6 pt-14 pb-8 text-center shadow-[0_20px_50px_-24px_rgba(15,23,42,0.35)] ring-1 ring-mist">
        <span className={`grid size-20 place-items-center rounded-full ${tone}`}>
          {state.kind === 'invalid' || state.kind === 'error' ? (
            <CloseIcon className="size-9" />
          ) : state.kind === 'loading' ? (
            <span className="size-7 animate-spin rounded-full border-2 border-gold/25 border-t-gold" aria-label={t('common.loading')} />
          ) : phone ? (
            <WhatsAppIcon className="size-9" />
          ) : (
            <ClockIcon className="size-9" />
          )}
        </span>

        {state.kind === 'loading' && <h1 className="mt-7 text-[22px] font-bold text-navy">{t('confirmLink.checking')}</h1>}

        {state.kind === 'ready' && phone && (
          <>
            <h1 className="mt-7 text-[24px] leading-tight font-bold text-navy">{t('confirmLink.phoneTitle')}</h1>
            <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{t('confirmLink.phoneBody')}</p>
            {text(state.confirmation.context.phone) && (
              <p className="mt-6 mb-6 w-full rounded-xl border border-mist px-4 py-3 text-[18px] font-semibold tracking-wide text-navy tabular-nums">{text(state.confirmation.context.phone)}</p>
            )}
            <button
              type="button"
              onClick={() => void confirm()}
              disabled={busy}
              className="mt-auto inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light disabled:opacity-70"
            >
              {busy && <span className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" aria-hidden="true" />}
              {t('confirmLink.confirm')}
            </button>
            <p className="mt-3 text-[12.5px] text-muted">{t('confirmLink.notMine')}</p>
          </>
        )}

        {state.kind === 'invalid' && (
          <>
            <h1 className="mt-7 text-[22px] leading-tight font-bold text-navy">{t('confirmLink.invalidTitle')}</h1>
            <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{t('confirmLink.invalidBody')}</p>
            <Help />
            <Link to="/lister/identity" className="mt-4 text-[13px] text-[#9a6c12] hover:underline">{t('confirmLink.listerLink')}</Link>
          </>
        )}

        {state.kind === 'error' && (
          <>
            <h1 className="mt-7 text-[22px] leading-tight font-bold text-navy">{t('confirmLink.errorTitle')}</h1>
            <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{state.message}</p>
            <Help />
          </>
        )}
      </div>
    </div>
  )
}

function Help() {
  const { t } = useTranslation()
  return (
    <a
      href={whatsappLink(t('confirmLink.helpMessage'))}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-auto inline-flex h-11 items-center gap-2 rounded-xl border border-mist px-5 text-[14px] font-medium text-navy hover:border-navy-soft/40"
    >
      <WhatsAppIcon className="size-4" />
      {t('nav.helpAction')}
    </a>
  )
}

// ---------------------------------------------------------------- shared pieces

function TopBar({ title, onBack }: { title: string; onBack?: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="grid grid-cols-[40px_1fr_40px] items-center px-4 pt-5">
      {onBack ? (
        <button type="button" onClick={onBack} aria-label={t('confirmLink.owner.back')} className="grid size-10 place-items-center rounded-full text-navy hover:bg-paper">
          <ArrowLeftIcon className="size-5" />
        </button>
      ) : (
        <span />
      )}
      <p className="text-center text-[17px] font-semibold text-navy">{title}</p>
      <span />
    </div>
  )
}

function Rows({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="divide-y divide-mist/70">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between gap-4 px-4 py-3.5 text-[14.5px]">
          <dt className="text-navy-soft">{label}</dt>
          <dd className="text-right text-navy">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Busy() {
  return <span className="size-4 animate-spin rounded-full border-2 border-current/25 border-t-current" aria-hidden="true" />
}

function propertyRows(t: (key: string, options?: Record<string, unknown>) => string, confirmation: Confirmation, language: string): [string, ReactNode][] {
  const details = confirmation.details
  const rows: [string, ReactNode][] = []
  const property = details?.property_id ?? text(confirmation.context.property_id)
  if (property) rows.push([t('confirmLink.owner.rows.property'), <span key="property" className="font-mono text-[13.5px]">{property}</span>])
  if (details?.area) rows.push([t('confirmLink.owner.rows.area'), details.area])
  if (details?.category) rows.push([t('confirmLink.owner.rows.category'), <span key="category" className="rounded-full bg-gold/12 px-2.5 py-0.5 text-[12.5px] text-[#7a5410]">{t(`market.category.${details.category}`)}</span>])
  if (details?.agent_name) rows.push([t('confirmLink.owner.rows.agent'), details.agent_name])
  if (details?.expires_at) rows.push([t('confirmLink.owner.rows.expires'), formatShortDate(details.expires_at, language)])
  return rows
}

// ---------------------------------------------------------------- owner price (K1, K2, K3)

const BANKS = ['CRDB', 'NMB', 'NBC', 'Stanbic', 'Equity', 'Exim', 'Absa', 'Azania', 'DTB', 'KCB', 'I&M'] as const
const BANK_TONES = ['#0f172a', '#1e3a8a', '#9a6c12', '#334155', '#7a5410', '#0f766e', '#b91c1c', '#1d4ed8', '#4338ca', '#15803d', '#a16207']

function OwnerPrice({ confirmation, onAnswer }: { confirmation: Confirmation; onAnswer: Answer }) {
  const { t, i18n } = useTranslation()
  const [step, setStep] = useState<'price' | 'bank' | 'details' | 'review'>('price')
  const [declining, setDeclining] = useState(false)
  const [bank, setBank] = useState<Bank>({ bank_name: '', account_name: '', account_number: '', branch: '' })
  const [other, setOther] = useState(false)
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const price = text(confirmation.context.owner_price)
  const receives = Math.floor(Number(text(confirmation.context.owner_receives_unrounded)) || 0)
  const rate = Number(text(confirmation.context.total_rate)) * 100
  const money = (value: string | number) => formatTsh(value, i18n.language)
  const field = 'mt-1.5 h-12 w-full rounded-xl border border-mist px-3.5 text-[15px] text-navy outline-none focus:border-gold focus:ring-2 focus:ring-gold/20'
  // Each step starts at the top of the page.
  useEffect(() => window.scrollTo({ top: 0 }), [step])
  const detailsReady = Boolean(bank.bank_name.trim() && bank.account_name.trim() && bank.account_number.trim() && bank.branch.trim())

  async function send(decision: Decision) {
    setBusy(true)
    await onAnswer(decision, decision === 'CONFIRM' ? { bank: { ...bank, bank_name: bank.bank_name.trim(), account_name: bank.account_name.trim(), account_number: bank.account_number.trim(), branch: bank.branch.trim() } } : {}).catch(() => undefined)
    setBusy(false)
  }

  if (step === 'bank') {
    return (
      <>
        <TopBar title={t('confirmLink.owner.bankTitle')} onBack={() => setStep('price')} />
        <div className="flex flex-1 flex-col px-5 pt-6 pb-6">
          <p className="text-[15px] font-medium text-navy">{t('confirmLink.owner.selectBank')}</p>
          <ul className="mt-3 grid grid-cols-3 gap-3">
            {BANKS.map((name, index) => {
              const on = !other && bank.bank_name === name
              return (
                <li key={name}>
                  <button type="button" aria-pressed={on} onClick={() => { setOther(false); setBank({ ...bank, bank_name: name }) }} className="flex w-full flex-col items-center gap-1.5 text-center">
                    <span className={`grid h-[58px] w-full place-items-center rounded-lg border text-[13px] font-bold text-white ${on ? 'border-navy ring-2 ring-navy/20' : 'border-mist'}`}>
                      <span className="grid size-9 place-items-center rounded-full" style={{ backgroundColor: BANK_TONES[index] }}>{name.slice(0, 2).toUpperCase()}</span>
                    </span>
                    <span className="text-[12.5px] text-navy">{name}</span>
                  </button>
                </li>
              )
            })}
            <li>
              <button type="button" aria-pressed={other} onClick={() => { setOther(true); setBank({ ...bank, bank_name: '' }) }} className="flex w-full flex-col items-center gap-1.5 text-center">
                <span className={`grid h-[58px] w-full place-items-center rounded-lg border text-[22px] text-navy-soft ${other ? 'border-navy ring-2 ring-navy/20' : 'border-mist'}`}>+</span>
                <span className="text-[12.5px] text-navy">{t('confirmLink.owner.otherBank')}</span>
              </button>
            </li>
          </ul>
          {other && (
            <label className="mt-4 block text-[14px] font-medium text-navy">
              {t('confirmLink.owner.otherBankName')}
              <input value={bank.bank_name} onChange={(event) => setBank({ ...bank, bank_name: event.target.value })} maxLength={255} className={field} />
            </label>
          )}
          <button type="button" disabled={!bank.bank_name.trim()} onClick={() => setStep('details')} className="mt-auto h-12 rounded-xl bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light disabled:opacity-50">
            {t('confirmLink.owner.continue')}
          </button>
        </div>
      </>
    )
  }

  if (step === 'details') {
    return (
      <>
        <TopBar title={t('confirmLink.owner.detailsTitle')} onBack={() => setStep('bank')} />
        <form
          onSubmit={(event) => {
            event.preventDefault()
            if (detailsReady) setStep('review')
          }}
          className="flex flex-1 flex-col gap-4 px-5 pt-6 pb-6"
        >
          {(
            [
              ['account_name', t('confirmLink.owner.accountName'), 'text'],
              ['account_number', t('confirmLink.owner.accountNumber'), 'numeric'],
              ['branch', t('confirmLink.owner.branch'), 'text'],
            ] as const
          ).map(([key, label, mode]) => (
            <label key={key} className="block text-[14px] font-medium text-navy">
              {label}
              <input required inputMode={mode === 'numeric' ? 'numeric' : undefined} maxLength={key === 'account_number' ? 100 : 255} value={bank[key]} onChange={(event) => setBank({ ...bank, [key]: event.target.value })} placeholder={label} className={field} />
            </label>
          ))}
          <p className="text-[13px] text-navy-soft">{bank.bank_name}</p>
          <button type="submit" disabled={!detailsReady} className="mt-auto h-12 rounded-xl bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light disabled:opacity-50">
            {t('confirmLink.owner.continue')}
          </button>
        </form>
      </>
    )
  }

  if (step === 'review') {
    const masked = bank.account_number.length > 4 ? `${bank.account_number.slice(0, 3)} •••• ${bank.account_number.slice(-2)}` : bank.account_number
    return (
      <>
        <TopBar title={t('confirmLink.owner.reviewTitle')} onBack={() => setStep('details')} />
        <div className="flex flex-1 flex-col px-5 pt-5 pb-6">
          <div className="flex items-center justify-between text-[14px]">
            <span className="font-medium text-navy">{t('confirmLink.owner.reviewTitle')}</span>
            <span className="text-navy-soft">{t('confirmLink.owner.step', { step: 3 })}</span>
          </div>
          <span className="mt-2 block h-1 rounded-full bg-navy" />
          <p className="mt-6 text-center text-[13px] text-navy-soft">{t('confirmLink.owner.receives')}</p>
          <p className="text-center text-[38px] leading-tight font-bold text-navy tabular-nums">{money(receives)}</p>

          <div className="mt-5 rounded-2xl border border-mist bg-paper/50">
            <div className="flex items-center gap-3 px-4 py-3.5">
              <span className="grid size-11 shrink-0 place-items-center rounded-full border-2 border-gold/60 text-[#9a6c12]"><BuildingSvg className="size-5" /></span>
              <span className="min-w-0 flex-1">
                <span className="block text-[12.5px] text-navy-soft">{t('confirmLink.owner.from')}</span>
                <span className="block text-[15px] font-medium text-navy">{t('confirmLink.owner.fromName')}</span>
                <span className="block text-[12.5px] text-navy-soft">{t('confirmLink.owner.fromNote')}</span>
              </span>
            </div>
            <span className="-my-2 ml-[37px] grid size-5 place-items-center rounded-full border border-mist bg-white text-navy-soft">
              <ArrowRightIcon className="size-3 rotate-90" />
            </span>
            <div className="flex items-center gap-3 px-4 py-3.5">
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-navy text-[13px] font-bold text-gold-light">{bank.bank_name.slice(0, 2).toUpperCase()}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[12.5px] text-navy-soft">{t('confirmLink.owner.to')}</span>
                <span className="block truncate text-[15px] font-medium text-navy">{bank.account_name}</span>
                <span className="block text-[12.5px] text-navy-soft tabular-nums">{bank.bank_name} {masked} · {bank.branch}</span>
              </span>
              <button type="button" onClick={() => setStep('bank')} aria-label={t('confirmLink.owner.edit')} className="text-navy-soft hover:text-navy"><PencilSvg className="size-4" /></button>
            </div>
          </div>

          <div className="mt-3 rounded-2xl border border-mist bg-paper/50">
            <Rows
              rows={[
                [t('confirmLink.owner.ownerPrice'), <span key="price" className="tabular-nums">{money(price)}</span>],
                [t('confirmLink.owner.commission'), <span key="commission" className="text-[#9a6c12]">{t('confirmLink.owner.commissionValue', { rate: Number.isFinite(rate) ? rate.toFixed(rate % 1 ? 1 : 0) : '-' })}</span>],
                [t('confirmLink.owner.receivesRow'), <span key="receives" className="font-semibold tabular-nums">{money(receives)}</span>],
              ]}
            />
          </div>

          <label className="mt-5 flex items-start gap-3 text-[14.5px] text-navy">
            <input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} className="mt-1 size-[18px] shrink-0 accent-[#0f172a]" />
            {t('confirmLink.owner.agreeBox')}
          </label>

          <button type="button" disabled={!agreed || busy} onClick={() => void send('CONFIRM')} className="mt-auto inline-flex h-12 items-center justify-center gap-2 rounded-full bg-navy text-[15px] font-semibold text-white hover:bg-navy-soft disabled:opacity-45">
            {busy && <Busy />}
            {t('confirmLink.owner.send')}
            <ArrowRightIcon className="size-4" />
          </button>
        </div>
      </>
    )
  }

  // K1: a sheet with the title and close, the price large, today and status, detail rows, two buttons.
  return (
    <>
      <div className="relative flex items-center justify-center px-5 pt-5">
        <span aria-hidden="true" className="absolute top-2 h-1.5 w-11 rounded-full bg-mist" />
        <h1 className="mt-4 text-[19px] text-navy">{t('confirmLink.owner.priceTitle')}</h1>
      </div>
      <div className="flex flex-1 flex-col px-5 pt-4 pb-6">
        <p className="text-center text-[40px] leading-tight font-semibold text-navy tabular-nums">{money(price)}</p>
        <p className="mt-1 flex items-center justify-center gap-3 text-[14px]">
          <span className="text-navy-soft">{t('confirmLink.owner.today')}</span>
          <span className="inline-flex items-center gap-1.5 text-[#9a6c12]"><span className="size-2 rounded-full bg-gold" />{t('confirmLink.owner.waiting')}</span>
        </p>
        <div className="mt-6 overflow-hidden rounded-2xl border border-mist bg-paper/40">
          <Rows rows={propertyRows(t, confirmation, i18n.language)} />
        </div>
        <p className="mt-4 text-[13.5px] leading-relaxed text-navy-soft">{t('confirmLink.owner.priceNote')}</p>
        <div className="mt-auto grid grid-cols-2 gap-3 pt-6">
          <button type="button" onClick={() => setDeclining(true)} className="h-12 rounded-full bg-[#f1f2f4] text-[15px] font-medium text-navy hover:bg-mist">
            {t('confirmLink.owner.decline')}
          </button>
          <button type="button" onClick={() => setStep('bank')} className="h-12 rounded-full bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light">
            {t('confirmLink.owner.confirmPrice')}
          </button>
        </div>
      </div>
      <AnimatePresence>
        {declining && (
          <Sheet
            title={t('confirmLink.owner.declineTitle')}
            body={t('confirmLink.owner.declineBody')}
            confirm={t('confirmLink.owner.declineConfirm')}
            busy={busy}
            onCancel={() => setDeclining(false)}
            onConfirm={() => void send('DECLINE')}
          />
        )}
      </AnimatePresence>
    </>
  )
}

function Sheet({ title, body, confirm, busy, onCancel, onConfirm }: { title: string; body: string; confirm: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const { t } = useTranslation()
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-end justify-center bg-navy/40 sm:items-center" onClick={onCancel}>
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby="sheet-title"
        initial={{ y: 30 }}
        animate={{ y: 0 }}
        exit={{ y: 30 }}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-[440px] rounded-t-[28px] bg-white px-6 pt-3 pb-7 sm:rounded-[28px]"
      >
        <span aria-hidden="true" className="mx-auto block h-1.5 w-11 rounded-full bg-mist" />
        <h2 id="sheet-title" className="mt-5 text-[19px] font-semibold text-navy">{title}</h2>
        <p className="mt-2 text-[14.5px] leading-relaxed text-navy-soft">{body}</p>
        <div className="mt-6 grid grid-cols-2 gap-3">
          <button type="button" onClick={onCancel} className="h-12 rounded-full bg-[#f1f2f4] text-[15px] font-medium text-navy">{t('confirmLink.owner.cancel')}</button>
          <button type="button" disabled={busy} onClick={onConfirm} className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-danger text-[15px] font-semibold text-white disabled:opacity-60">
            {busy && <Busy />}
            {confirm}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ---------------------------------------------------------------- money received (K5)

function OwnerReceipt({ confirmation, onAnswer }: { confirmation: Confirmation; onAnswer: Answer }) {
  const { t, i18n } = useTranslation()
  const [reference, setReference] = useState('')
  const [declining, setDeclining] = useState(false)
  const [busy, setBusy] = useState(false)
  const money = (value: string) => formatTsh(value, i18n.language)
  const property = confirmation.details?.property_id ?? ''

  async function send(decision: Decision) {
    setBusy(true)
    await onAnswer(decision, decision === 'CONFIRM' ? { bank_reference: reference.trim() } : {}).catch(() => undefined)
    setBusy(false)
  }

  return (
    <div className="flex flex-1 flex-col bg-[#eef0f3] px-4 pt-5 pb-6">
      <span className="grid size-10 place-items-center rounded-full bg-white text-navy"><WhatsAppIcon className="size-5" /></span>
      <h1 className="mt-5 text-[28px] leading-tight font-medium text-navy">{t('confirmLink.owner.receiptTitle')}</h1>

      <section className="mt-5 rounded-2xl bg-white px-4 py-4">
        <h2 className="text-[16px] font-medium text-navy">{t('confirmLink.owner.receiptFrom')}</h2>
        <div className="mt-3 flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-full bg-navy text-[13px] font-bold text-gold-light">{(confirmation.details?.category ?? 'O').slice(0, 1)}</span>
          <span>
            <span className="block text-[15px] text-navy">{t('confirmLink.owner.receiptBuyer', { property: '' })}<span className="font-mono whitespace-nowrap">{property}</span></span>
            {confirmation.details?.agent_name && <span className="block text-[13px] text-navy-soft">{t('confirmLink.owner.receiptAgent', { name: confirmation.details.agent_name })}</span>}
          </span>
        </div>
        {confirmation.details?.area && <p className="mt-3 text-[13px] text-navy-soft">{confirmation.details.area}</p>}
      </section>

      <section className="mt-2 rounded-2xl bg-white px-4 py-4">
        <h2 className="border-b border-mist pb-3 text-[16px] font-medium text-navy">{t('confirmLink.owner.amountTitle')}</h2>
        <dl className="mt-3 space-y-3 text-[14.5px]">
          <div className="flex justify-between gap-3"><dt className="text-navy-soft">{t('confirmLink.owner.finalPrice')}</dt><dd className="whitespace-nowrap text-navy tabular-nums">{money(text(confirmation.context.final_selling_price))}</dd></div>
          <div className="flex justify-between gap-3 border-t border-mist pt-3"><dt className="text-navy">{t('confirmLink.owner.amountToOwner')}</dt><dd className="font-semibold whitespace-nowrap text-navy tabular-nums">{money(text(confirmation.context.amount))}</dd></div>
        </dl>
      </section>

      <label className="mt-4 block text-[14px] font-medium text-navy">
        {t('confirmLink.owner.reference')}
        <input value={reference} onChange={(event) => setReference(event.target.value)} maxLength={255} className="mt-1.5 h-12 w-full rounded-xl border border-mist bg-white px-3.5 font-mono text-[15px] text-navy outline-none focus:border-gold focus:ring-2 focus:ring-gold/20" />
        <span className="mt-1 block text-[12.5px] font-normal text-navy-soft">{t('confirmLink.owner.referenceHint')}</span>
      </label>

      <button type="button" disabled={!reference.trim() || busy} onClick={() => void send('CONFIRM')} className="mt-auto inline-flex h-[52px] items-center justify-center gap-2 rounded-xl bg-gold text-[16px] font-semibold text-navy hover:bg-gold-light disabled:opacity-50">
        {busy && <Busy />}
        {t('confirmLink.owner.confirmReceipt')}
      </button>
      <button type="button" onClick={() => setDeclining(true)} className="mt-3 text-[14px] text-navy-soft underline-offset-2 hover:underline">{t('confirmLink.owner.notReceived')}</button>

      <AnimatePresence>
        {declining && (
          <Sheet
            title={t('confirmLink.owner.notReceivedTitle')}
            body={t('confirmLink.owner.notReceivedBody')}
            confirm={t('confirmLink.owner.notReceived')}
            busy={busy}
            onCancel={() => setDeclining(false)}
            onConfirm={() => void send('DECLINE')}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

// ---------------------------------------------------------------- full check consent (K8)

function Consent({ confirmation, onAnswer }: { confirmation: Confirmation; onAnswer: Answer }) {
  const { t, i18n } = useTranslation()
  const [busy, setBusy] = useState<Decision | null>(null)
  const [open, setOpen] = useState(false)
  const scope = scopeText(confirmation.context.scope as ScopeSnapshot | undefined, i18n.language)
  const deadline = confirmation.details?.expires_at

  async function send(decision: Decision) {
    setBusy(decision)
    await onAnswer(decision).catch(() => undefined)
    setBusy(null)
  }

  const rows: [string, string][] = [
    [t('confirmLink.owner.rows.property'), confirmation.details?.property_id ?? text(confirmation.context.property_id)],
    [t('confirmLink.owner.rows.area'), confirmation.details?.area ?? ''],
  ].filter(([, value]) => value) as [string, string][]

  return (
    <div className="flex flex-1 flex-col px-6 pt-14 pb-6">
      <span className="mx-auto text-gold"><ReceiptSvg className="h-16 w-12" /></span>
      <h1 className="mt-6 text-center text-[26px] leading-tight font-semibold text-navy">{t('confirmLink.owner.consentTitle')}</h1>
      <p className="mt-3 text-center text-[15px] text-navy-soft">{deadline ? t('confirmLink.owner.consentSubtitle', { date: formatShortDate(deadline, i18n.language) }) : ''}</p>

      <ul className="mt-8 border-y border-mist">
        {rows.map(([label, value]) => (
          <li key={label} className="flex items-center justify-between gap-3 border-b border-mist py-4 text-[15.5px] last:border-b-0">
            <span className="text-navy">{label}</span>
            <span className="text-navy-soft">{value}</span>
          </li>
        ))}
        <li>
          <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex w-full items-center justify-between gap-3 py-4 text-left text-[15.5px] text-navy">
            {t('confirmLink.owner.consentScope')}
            <ChevronRightIcon className={`size-5 text-gold transition-transform ${open ? 'rotate-90' : ''}`} />
          </button>
          {open && (
            <ol className="space-y-1.5 pb-4 text-[14px] text-navy-soft">
              {scope.split(/,\s*|\.\s*/).filter(Boolean).map((item, index) => (
                <li key={item} className="flex gap-2"><span className="text-[#9a6c12] tabular-nums">{index + 1}.</span>{item.charAt(0).toUpperCase() + item.slice(1)}</li>
              ))}
            </ol>
          )}
        </li>
      </ul>

      <p className="mt-6 text-[14.5px] leading-relaxed text-[#9aa1ad]">{t('confirmLink.owner.consentNote')}</p>

      <div className="mt-auto space-y-3 pt-6">
        <button type="button" disabled={busy !== null} onClick={() => void send('CONFIRM')} className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-md bg-navy text-[14px] font-semibold tracking-[0.18em] text-white uppercase hover:bg-navy-soft disabled:opacity-60">
          {busy === 'CONFIRM' && <Busy />}
          {t('confirmLink.owner.agree')}
        </button>
        <button type="button" disabled={busy !== null} onClick={() => void send('DECLINE')} className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-md border border-navy text-[14px] font-semibold tracking-[0.18em] text-navy uppercase hover:bg-paper disabled:opacity-60">
          {busy === 'DECLINE' && <Busy />}
          {t('confirmLink.owner.disagree')}
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- the ending (K11)

function Done({ state, delivery }: { state: Extract<State, { kind: 'done' }>; delivery: string }) {
  const { t, i18n } = useTranslation()
  const purpose = state.confirmation?.purpose ?? 'PHONE'
  const confirmed = state.decision === 'CONFIRM'
  useEffect(() => window.scrollTo({ top: 0 }), [])
  const property = state.confirmation?.details?.property_id ?? text(state.confirmation?.context.property_id)
  return (
    <div className="flex flex-1 flex-col bg-[#f2f2f2] px-5 pt-10 pb-6">
      <h1 className="text-center text-[34px] leading-tight font-bold text-navy">{confirmed ? t('confirmLink.owner.doneTitle') : t('confirmLink.owner.declinedTitle')}</h1>
      <Illustration confirmed={confirmed} />
      <p className="text-center text-[15.5px] leading-relaxed text-navy">
        {confirmed ? t(`confirmLink.owner.doneBody.${purpose}`) : t(`confirmLink.owner.declinedBody.${purpose}`, { defaultValue: t('confirmLink.owner.declinedBody.OWNER_RECEIPT') })}
      </p>

      <section className="mt-6 rounded-[22px] bg-white px-6 py-5">
        <p className="flex justify-end">
          <span className="inline-flex items-center gap-2 text-[14px] text-navy-soft">
            <span className={`grid size-5 place-items-center rounded-full text-white ${confirmed ? 'bg-gold' : 'bg-navy-soft'}`}>
              {confirmed ? <TickIcon className="size-3" /> : <CloseIcon className="size-3" />}
            </span>
            {t(`confirmLink.owner.tags.${state.decision}`)}
          </span>
        </p>
        <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-4">
          {property && <Fact label={t('confirmLink.owner.card.property')} value={property} wide />}
          <Fact label={t('confirmLink.owner.card.reference')} value={delivery.slice(0, 8).toUpperCase()} />
          <Fact label={t('confirmLink.owner.card.date')} value={formatShortDate(state.at, i18n.language)} />
          <Fact label={t('confirmLink.owner.card.type')} value={t(`confirmLink.owner.types.${purpose}`)} wide />
          <Fact label={t('confirmLink.owner.card.answer')} value={t(`confirmLink.owner.answers.${state.decision}`)} wide />
        </dl>
      </section>
      <p className="mt-3 text-center text-[12.5px] text-navy-soft">{t('confirmLink.owner.keep')}</p>

      <Link to={purpose === 'PHONE' ? '/lister' : '/'} className="mt-auto inline-flex h-14 items-center justify-center rounded-full bg-navy text-[16px] font-medium text-white hover:bg-navy-soft">
        {purpose === 'PHONE' ? t('confirmLink.toListings') : t('confirmLink.owner.home')}
      </Link>
    </div>
  )
}

function Fact({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? 'col-span-2' : ''}>
      <dt className="text-[12px] tracking-[0.06em] text-navy-soft uppercase">{label}</dt>
      <dd className="mt-1 text-[17px] text-navy">{value}</dd>
    </div>
  )
}

// K11's document with a tick, in Oweru gold; a cross when declined.
function Illustration({ confirmed }: { confirmed: boolean }) {
  return (
    <svg viewBox="0 0 240 180" className="mx-auto my-6 h-[170px] w-auto" aria-hidden="true">
      <path d="M20 180a100 100 0 0 1 200 0Z" fill="#e7ebef" />
      <circle cx="78" cy="38" r="5" fill="none" stroke="#c89128" strokeWidth="3" />
      <circle cx="198" cy="110" r="6" fill="none" stroke="#c89128" strokeWidth="3" />
      <circle cx="192" cy="160" r="5" fill="none" stroke="#e5b972" strokeWidth="3" />
      <path d="M44 86l8 8m0-8l-8 8" stroke="#e5b972" strokeWidth="3" strokeLinecap="round" />
      <path d="M58 148l6 6m0-6l-6 6" stroke="#0f172a" strokeWidth="3" strokeLinecap="round" />
      <circle cx="44" cy="62" r="1.8" fill="#0f172a" />
      <circle cx="186" cy="132" r="1.8" fill="#0f172a" />
      <path d="M92 48h52a10 10 0 0 1 10 10v94l-8-6-8 6-8-6-8 6-8-6-8 6-8-6-8 6V58a10 10 0 0 1 10-10Z" fill="#fff" stroke="#c89128" strokeWidth="4" strokeLinejoin="round" />
      <path d="M86 48a10 10 0 0 0 0 20h10" fill="none" stroke="#c89128" strokeWidth="4" />
      <path d="M108 74h32M108 86h32M108 98h22" stroke="#0f172a" strokeWidth="4" strokeLinecap="round" />
      <text x="114" y="132" fontSize="22" fontWeight="700" fill="#0f172a">TSh</text>
      <circle cx="170" cy="44" r="26" fill={confirmed ? '#c89128' : '#475569'} />
      {confirmed ? (
        <path d="M158 44l8 8 16-16" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <path d="M161 35l18 18m0-18l-18 18" stroke="#fff" strokeWidth="5" strokeLinecap="round" />
      )}
    </svg>
  )
}

function ReceiptSvg(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 48 64" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true" {...props}>
      <path d="M4 4h40M8 4v56h32V4" />
      <path d="M15 18h6M25 18h8M15 28h18M15 38h18M15 48h12" strokeLinecap="round" />
    </svg>
  )
}

function BuildingSvg(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M4 21V8l8-5 8 5v13M9 21v-6h6v6M3 21h18" />
    </svg>
  )
}

function PencilSvg(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M4 20h4L19 9l-4-4L4 16v4ZM13.5 6.5l4 4" />
    </svg>
  )
}
