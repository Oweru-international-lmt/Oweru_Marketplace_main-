import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { FullPageLoader } from '../../components/FullPageLoader'
import { AlertIcon, BankIcon, CheckIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ApiError } from '../../lib/api'
import { dealsApi, type Bank } from '../../lib/dealsApi'
import { errorMessage } from '../../lib/errors'
import { TANZANIAN_BANKS } from './data'

// PAY-04: where the lister's money goes. After D14: one focused form under a
// progress bar, an icon, a title and one line on what the account is for,
// with a tinted panel beside it (here a live preview of the payout card).

const EMPTY: Bank = { bank_name: '', account_name: '', account_number: '', branch: '' }

export function BankPage() {
  const { t } = useTranslation()
  const [initial, setInitial] = useState<Bank | null | undefined>(undefined)
  useDocumentTitle(t('deals.bank.title'))

  useEffect(() => {
    let live = true
    dealsApi
      .bank()
      .then((bank) => live && setInitial(bank))
      .catch((failure) => live && setInitial(failure instanceof ApiError && failure.status === 404 ? null : EMPTY))
    return () => {
      live = false
    }
  }, [])

  if (initial === undefined) return <FullPageLoader inline />
  return <BankForm initial={initial ?? EMPTY} existing={Boolean(initial)} />
}

function BankForm({ initial, existing }: { initial: Bank; existing: boolean }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const reduce = useReducedMotion()
  const known = TANZANIAN_BANKS.includes(initial.bank_name as (typeof TANZANIAN_BANKS)[number])
  const [bank, setBank] = useState<Bank>(initial)
  const [choice, setChoice] = useState(initial.bank_name ? (known ? initial.bank_name : 'OTHER') : '')
  const [agree, setAgree] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const filled = [bank.bank_name, bank.account_name, bank.account_number, bank.branch].filter((value) => value.trim()).length + (agree ? 1 : 0)
  const ready = filled === 5

  function update(field: keyof Bank, value: string) {
    setBank((current) => ({ ...current, [field]: value }))
    setSaved(false)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!ready) return
    setBusy(true)
    setError('')
    try {
      await dealsApi.saveBank({ bank_name: bank.bank_name.trim(), account_name: bank.account_name.trim(), account_number: bank.account_number.replace(/\s+/g, ''), branch: bank.branch.trim() })
      setSaved(true)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  const field = 'h-12 w-full rounded-lg border border-navy/25 bg-white px-3.5 text-[15px] text-navy outline-none transition-colors placeholder:text-muted/60 focus:border-gold focus:ring-2 focus:ring-gold/25'
  return (
    <div className="-mx-4 -my-6 grid min-h-[calc(100dvh-58px)] bg-white sm:-mx-6 lg:-my-7 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <form onSubmit={(event) => void submit(event)} className="mx-auto w-full max-w-[440px] px-5 py-10" noValidate>
        <div className="h-1.5 overflow-hidden rounded-full bg-mist">
          <motion.div className="h-full rounded-full bg-navy" initial={false} animate={{ width: `${(filled / 5) * 100}%` }} transition={{ type: 'spring', stiffness: 160, damping: 24 }} />
        </div>
        <motion.span
          initial={reduce ? false : { scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 300, damping: 18, delay: 0.1 }}
          className="mx-auto mt-8 grid size-16 place-items-center rounded-full bg-[#fbeee0] text-[#9a6c12]"
        >
          <BankIcon className="size-7" />
        </motion.span>
        <h1 className="mt-5 text-center text-[24px] font-semibold text-navy">{t(existing ? 'deals.bank.titleEdit' : 'deals.bank.title')}</h1>
        <p className="mt-2 text-center text-[14px] text-navy-soft">{t('deals.bank.lead')}</p>

        <div className="mt-8 space-y-5">
          <label className="block">
            <span className="mb-1.5 block text-[14px] font-medium text-navy">
              <span className="mr-1 text-danger">*</span>
              {t('deals.bank.bank')}
            </span>
            <select
              value={choice}
              onChange={(event) => {
                setChoice(event.target.value)
                update('bank_name', event.target.value === 'OTHER' ? '' : event.target.value)
              }}
              className={field}
            >
              <option value="" disabled>
                {t('deals.bank.choose')}
              </option>
              {TANZANIAN_BANKS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
              <option value="OTHER">{t('deals.bank.other')}</option>
            </select>
          </label>
          <AnimatePresence initial={false}>
            {choice === 'OTHER' && (
              <motion.label initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="block overflow-hidden">
                <span className="mb-1.5 block text-[14px] font-medium text-navy">{t('deals.bank.otherName')}</span>
                <input value={bank.bank_name} onChange={(event) => update('bank_name', event.target.value)} className={field} />
              </motion.label>
            )}
          </AnimatePresence>
          <label className="block">
            <span className="mb-1.5 block text-[14px] font-medium text-navy">
              <span className="mr-1 text-danger">*</span>
              {t('deals.bank.name')}
            </span>
            <input value={bank.account_name} onChange={(event) => update('account_name', event.target.value)} autoComplete="name" className={field} />
            <span className="mt-1.5 block text-[12px] text-muted">{t('deals.bank.nameHint')}</span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[14px] font-medium text-navy">
              <span className="mr-1 text-danger">*</span>
              {t('deals.bank.number')}
            </span>
            <input value={bank.account_number} onChange={(event) => update('account_number', event.target.value)} inputMode="numeric" className={`${field} font-mono tracking-wider`} />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[14px] font-medium text-navy">
              <span className="mr-1 text-danger">*</span>
              {t('deals.bank.branch')}
            </span>
            <input value={bank.branch} onChange={(event) => update('branch', event.target.value)} className={field} />
          </label>
        </div>

        <p className="mt-7 text-[14px] text-navy">{t('deals.bank.privacy')}</p>
        <label className="mt-3 flex items-start gap-3 text-[13px] leading-relaxed text-navy-soft">
          <input type="checkbox" checked={agree} onChange={(event) => setAgree(event.target.checked)} className="mt-0.5 size-4 shrink-0 accent-[#0f172a]" />
          {t('deals.bank.confirm')}
        </label>

        {error && (
          <p role="alert" className="mt-4 flex items-center gap-2 text-[13px] text-danger">
            <AlertIcon className="size-4" />
            {error}
          </p>
        )}
        <AnimatePresence>
          {saved && (
            <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} role="status" className="mt-4 flex items-center gap-2 rounded-lg bg-success-soft px-3.5 py-2.5 text-[13px] text-success">
              <CheckIcon className="size-4" />
              {t('deals.bank.saved')}
            </motion.p>
          )}
        </AnimatePresence>
        <button type="submit" disabled={!ready || busy} className="mt-7 h-11 w-full rounded-full bg-navy text-[15px] font-semibold text-white transition-colors hover:bg-navy-soft disabled:opacity-50">
          {busy ? t('deals.saving') : t('deals.bank.finish')}
        </button>
        <button type="button" onClick={() => navigate(-1)} className="mt-3 h-11 w-full rounded-full border border-navy text-[15px] font-medium text-navy transition-colors hover:bg-paper">
          {t('deals.bank.back')}
        </button>
      </form>

      <aside aria-hidden="true" className="relative hidden overflow-hidden bg-[#fbeee0] lg:grid lg:place-items-center">
        <span className="absolute -top-10 -left-10 size-56 rounded-full bg-[radial-gradient(#9a6c12_1.6px,transparent_1.7px)] bg-[length:9px_9px] opacity-40" />
        <span className="absolute -right-12 -bottom-12 size-56 rounded-full bg-[radial-gradient(#9a6c12_1.6px,transparent_1.7px)] bg-[length:9px_9px] opacity-40" />
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 24, rotate: -6 }}
          animate={{ opacity: 1, y: 0, rotate: -4 }}
          transition={{ type: 'spring', stiffness: 120, damping: 16, delay: 0.2 }}
          className="relative w-[340px] overflow-hidden rounded-2xl bg-gradient-to-br from-navy via-navy-soft to-[#9a6c12] px-7 py-7 text-white shadow-lift"
        >
          <span className="absolute -top-14 -right-14 size-44 rounded-full bg-gold/30 blur-2xl" />
          <div className="flex items-center justify-between">
            <span className="text-[17px] font-semibold">{bank.bank_name || t('deals.bank.bank')}</span>
            <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-[10px] tracking-[0.08em] uppercase">Oweru</span>
          </div>
          <span className="mt-7 block h-7 w-10 rounded-md bg-gradient-to-br from-gold-light to-gold" />
          <motion.p key={bank.account_number.length} initial={{ opacity: 0.4 }} animate={{ opacity: 1 }} className="mt-4 font-mono text-[18px] tracking-[0.2em]">
            {bank.account_number ? bank.account_number.replace(/\s+/g, '').replace(/(.{4})/g, '$1 ').trim() : '•••• •••• ••••'}
          </motion.p>
          <div className="mt-4 flex items-end justify-between text-[12px] text-white/75">
            <span className="max-w-[60%] truncate">{bank.account_name || t('deals.bank.name')}</span>
            <span className="truncate">{bank.branch || t('deals.bank.branch')}</span>
          </div>
        </motion.div>
      </aside>
    </div>
  )
}
