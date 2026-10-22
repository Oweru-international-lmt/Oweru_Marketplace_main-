import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { CheckIcon, ClockIcon, ShieldIcon, UserIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatShortDate } from '../../lib/format'
import { scopeText, servicesApi, type OwnerRequest } from '../../lib/servicesApi'

// FUL-02 inside the account. The Owner reads what a buyer's full check will
// look at and confirms or declines; an Agent whose listing has no owner
// contact gives it, so the owner can consent themselves (an Agent never can).

function daysLeft(deadline: string) {
  return Math.max(0, Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000))
}

export function OwnerRequestsPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('ownerRequests.title'))
  const [rows, setRows] = useState<OwnerRequest[] | null>(null)
  const [done, setDone] = useState<Record<string, 'CONFIRM' | 'DECLINE' | 'CONTACT'>>({})
  const [error, setError] = useState('')

  useEffect(() => {
    servicesApi.ownerRequests().then(setRows, (failure) => {
      setError(errorMessage(t, failure))
      setRows([])
    })
  }, [t])

  if (!rows) return <FullPageLoader inline />
  return (
    <div className="mx-auto max-w-[760px] pb-10">
      <h1 className="text-[24px] font-semibold text-navy">{t('ownerRequests.title')}</h1>
      <p className="mt-1 text-[13px] text-muted">{t('ownerRequests.subtitle')}</p>
      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
      {rows.length === 0 && (
        <div className="mt-6 rounded-2xl border border-mist bg-white px-6 py-12 text-center">
          <span className="mx-auto grid size-12 place-items-center rounded-full bg-success-soft text-success"><CheckIcon className="size-6" /></span>
          <p className="mt-3 text-[15px] font-medium text-navy">{t('ownerRequests.empty')}</p>
          <Link to="/account" className="mt-2 inline-block text-[13px] text-[#9a6c12] hover:underline">{t('ownerRequests.back')}</Link>
        </div>
      )}
      <div className="mt-6 space-y-4">
        {rows.map((row, index) => (
          <RequestCard key={`${row.kind}-${row.job_id}`} row={row} index={index} done={done[row.job_id]} onDone={(value) => setDone((current) => ({ ...current, [row.job_id]: value }))} />
        ))}
      </div>
    </div>
  )
}

function RequestCard({ row, index, done, onDone }: { row: OwnerRequest; index: number; done?: 'CONFIRM' | 'DECLINE' | 'CONTACT'; onDone: (value: 'CONFIRM' | 'DECLINE' | 'CONTACT') => void }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [declining, setDeclining] = useState(false)
  const [owner, setOwner] = useState({ name: row.owner_name, phone: '' })
  const left = daysLeft(row.deadline)

  async function run(action: () => Promise<unknown>, value: 'CONFIRM' | 'DECLINE' | 'CONTACT') {
    setBusy(true)
    setError('')
    try {
      await action()
      onDone(value)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <motion.article initial={reduce ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.08 }} className="overflow-hidden rounded-2xl border border-mist bg-white">
      <header className="flex flex-wrap items-center gap-3 bg-navy px-5 py-4 text-white">
        <span className="grid size-10 place-items-center rounded-xl bg-gold text-navy">{row.kind === 'consent' ? <ShieldIcon className="size-5" /> : <UserIcon className="size-5" />}</span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold">{t(`ownerRequests.${row.kind}.title`)}</p>
          <p className="text-[12px] text-white/70">
            <span className="font-mono">{row.property_id}</span>
            {row.area && ` · ${row.area}`}
          </p>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium ${left <= 1 ? 'bg-[#c2410c] text-white' : 'bg-white/10 text-white'}`}>
          <ClockIcon className="size-3.5" />
          {t('ownerRequests.left', { count: left, date: formatShortDate(row.deadline, i18n.language) })}
        </span>
      </header>

      <div className="px-5 py-5">
        <AnimatePresence mode="wait" initial={false}>
          {done ? (
            <motion.div key="done" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="flex items-start gap-3 rounded-xl bg-paper px-4 py-4">
              <span className={`grid size-9 shrink-0 place-items-center rounded-full ${done === 'DECLINE' ? 'bg-danger-soft text-danger' : 'bg-success-soft text-success'}`}><CheckIcon className="size-5" /></span>
              <div>
                <p className="text-[14px] font-semibold text-navy">{t(`ownerRequests.done.${done}`)}</p>
                <p className="mt-0.5 text-[13px] text-muted">{t(`ownerRequests.doneBody.${done}`)}</p>
              </div>
            </motion.div>
          ) : row.kind === 'consent' ? (
            <motion.div key="consent" exit={{ opacity: 0 }}>
              <p className="text-[14px] text-navy-soft">{t('ownerRequests.consent.body')}</p>
              <div className="mt-3 rounded-xl border border-mist bg-paper/60 px-4 py-3">
                <p className="text-[12px] font-semibold tracking-wide text-muted uppercase">{t('ownerRequests.consent.scope')}</p>
                <p className="mt-1 text-[14px] leading-relaxed text-navy">{scopeText(row.scope, i18n.language)}</p>
              </div>
              <p className="mt-3 text-[12px] text-muted">{t('ownerRequests.consent.privacy')}</p>
              {error && <div className="mt-3"><Alert tone="error">{error}</Alert></div>}
              {declining ? (
                <div className="mt-4 rounded-xl border border-danger/30 bg-danger-soft/40 px-4 py-4">
                  <p className="text-[14px] text-navy">{t('ownerRequests.consent.declineBody')}</p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <button type="button" onClick={() => setDeclining(false)} className="h-11 rounded-full border border-mist bg-white text-[14px] font-medium text-navy">{t('ownerRequests.cancel')}</button>
                    <button type="button" disabled={busy} onClick={() => void run(() => servicesApi.ownerConsent(row.job_id, 'DECLINE'), 'DECLINE')} className="h-11 rounded-full bg-danger text-[14px] font-semibold text-white disabled:opacity-60">{t('ownerRequests.consent.declineConfirm')}</button>
                  </div>
                </div>
              ) : (
                <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto]">
                  <button type="button" disabled={busy} onClick={() => void run(() => servicesApi.ownerConsent(row.job_id, 'CONFIRM'), 'CONFIRM')} className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light disabled:opacity-60">
                    <CheckIcon className="size-4" />
                    {t('ownerRequests.consent.confirm')}
                  </button>
                  <button type="button" onClick={() => setDeclining(true)} className="h-12 rounded-full border border-mist px-6 text-[14px] font-medium text-danger hover:bg-danger-soft">{t('ownerRequests.consent.decline')}</button>
                </div>
              )}
            </motion.div>
          ) : (
            <motion.form
              key="contact"
              exit={{ opacity: 0 }}
              onSubmit={(event) => {
                event.preventDefault()
                void run(() => servicesApi.ownerContact(row.job_id, owner.name.trim(), owner.phone.trim()), 'CONTACT')
              }}
            >
              <p className="text-[14px] text-navy-soft">{t('ownerRequests.contact.body')}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-[13px] font-medium text-navy">{t('ownerRequests.contact.name')}</span>
                  <input className="h-11 w-full rounded-[6px] border border-mist px-3 text-[14px] text-navy outline-none focus:border-gold" value={owner.name} onChange={(event) => setOwner({ ...owner, name: event.target.value })} />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[13px] font-medium text-navy">{t('ownerRequests.contact.phone')}</span>
                  <input className="h-11 w-full rounded-[6px] border border-mist px-3 text-[14px] text-navy outline-none focus:border-gold" inputMode="tel" placeholder="+255 7xx xxx xxx" value={owner.phone} onChange={(event) => setOwner({ ...owner, phone: event.target.value })} />
                </label>
              </div>
              <p className="mt-2 text-[12px] text-muted">{t('ownerRequests.contact.note')}</p>
              {error && <div className="mt-3"><Alert tone="error">{error}</Alert></div>}
              <button type="submit" disabled={busy || !owner.name.trim() || owner.phone.trim().length < 9} className="mt-4 h-12 w-full rounded-full bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light disabled:opacity-50">
                {t('ownerRequests.contact.send')}
              </button>
            </motion.form>
          )}
        </AnimatePresence>
      </div>
    </motion.article>
  )
}

// Shown above every signed-in page while something waits on this person.
export function OwnerRequestsBanner() {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const [count, setCount] = useState(0)
  const here = pathname === '/full-checks/requests'
  useEffect(() => {
    if (here) return
    let live = true
    servicesApi.ownerRequests().then((rows) => live && setCount(rows.length), () => undefined)
    return () => {
      live = false
    }
  }, [pathname, here])
  return (
    <AnimatePresence>
      {count > 0 && !here && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-gold/40 bg-[#fdf6e7] px-4 py-3">
          <span className="grid size-8 place-items-center rounded-full bg-gold text-navy"><ShieldIcon className="size-4" /></span>
          <p className="min-w-0 flex-1 text-[14px] text-navy">{t('ownerRequests.banner', { count })}</p>
          <Link to="/full-checks/requests" className="rounded-full bg-navy px-4 py-2 text-[13px] font-semibold text-white">{t('ownerRequests.open')}</Link>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
