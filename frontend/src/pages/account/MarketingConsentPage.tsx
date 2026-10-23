import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { MailIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { peopleApi } from '../../lib/peopleApi'

// MAR-03: the page campaign emails link to. Marketing is off until the
// person turns it on; turning it off stops future campaigns at once.

export function MarketingConsentPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('consentPage.title'))
  const [state, setState] = useState<{ agreed: boolean; version: number } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    peopleApi.consent().then(setState, (failure) => setError(errorMessage(t, failure)))
  }, [t])

  async function toggle() {
    if (!state) return
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      setState(await peopleApi.saveConsent(!state.agreed, state.version))
      setSaved(true)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  if (!state) return error ? <Alert tone="error">{error}</Alert> : <FullPageLoader inline />
  return (
    <div className="mx-auto max-w-[620px] pb-10">
      <h1 className="text-[24px] font-semibold text-navy">{t('consentPage.title')}</h1>
      <p className="mt-1 text-[13px] text-muted">{t('consentPage.subtitle')}</p>
      <div className="mt-5 rounded-2xl border border-mist bg-white p-5">
        <div className="flex items-start gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-gold/15 text-[#9a6c12]"><MailIcon className="size-5" /></span>
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-semibold text-navy">{t('consentPage.label')}</p>
            <p className="mt-1 text-[13px] text-navy-soft">{t('consentPage.body')}</p>
          </div>
          <button type="button" role="switch" aria-checked={state.agreed} aria-label={t('consentPage.label')} disabled={busy} onClick={() => void toggle()} className={`relative mt-1 h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-60 ${state.agreed ? 'bg-success' : 'bg-mist'}`}>
            <motion.span layout transition={{ type: 'spring', stiffness: 500, damping: 30 }} className={`absolute top-0.5 size-5 rounded-full bg-white shadow ${state.agreed ? 'right-0.5' : 'left-0.5'}`} />
          </button>
        </div>
        <p className="mt-4 rounded-lg bg-paper px-4 py-3 text-[12px] text-muted">{state.agreed ? t('consentPage.on') : t('consentPage.off')}</p>
        {error && <div className="mt-3"><Alert tone="error">{error}</Alert></div>}
        {saved && <div className="mt-3"><Alert tone="success">{t('consentPage.saved')}</Alert></div>}
      </div>
      <p className="mt-4 text-[12px] text-muted">{t('consentPage.serviceNote')}</p>
    </div>
  )
}
