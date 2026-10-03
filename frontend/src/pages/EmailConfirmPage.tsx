import { motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { AuthHeading } from '../components/AuthHeading'
import { FullPageLoader } from '../components/FullPageLoader'
import { CheckIcon, MailIcon } from '../components/icons'
import { authApi } from '../lib/authApi'

// Opened from the ACC-05 email: EMAIL_CONFIRMATION_URL?id=...&token=...
export function EmailConfirmPage() {
  const { t } = useTranslation()
  const { status, setUser } = useAuth()
  const [params] = useSearchParams()
  const id = params.get('id')
  const token = params.get('token')
  const [result, setResult] = useState<'checking' | 'confirmed' | 'failed'>(id && token ? 'checking' : 'failed')
  // The link works once, so React's development double-run must not send it twice.
  const sent = useRef(false)

  useEffect(() => {
    if (!id || !token || sent.current) return
    sent.current = true
    authApi
      .confirmEmail(id, token)
      .then(() => {
        setResult('confirmed')
        if (status === 'authenticated') void authApi.me().then(setUser).catch(() => undefined)
      })
      .catch(() => setResult('failed'))
  }, [id, token, status, setUser])

  if (result === 'checking') return <FullPageLoader inline />

  const ok = result === 'confirmed'
  return (
    <div className="space-y-6">
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 260, damping: 18 }}
        className={`grid size-14 place-items-center rounded-2xl ${ok ? 'bg-success-soft text-success' : 'bg-gold/15 text-navy'}`}
      >
        {ok ? <CheckIcon className="size-7" /> : <MailIcon className="size-7" />}
      </motion.span>
      <AuthHeading
        title={ok ? t('emailConfirm.successTitle') : t('emailConfirm.failTitle')}
        subtitle={ok ? t('emailConfirm.successBody') : t('emailConfirm.failBody')}
      />
      <Link
        to={status === 'authenticated' ? '/account' : '/login'}
        className="inline-flex h-12 items-center justify-center rounded-xl bg-gold px-6 font-display text-[15px] font-semibold text-navy hover:bg-gold-light"
      >
        {t('emailConfirm.continue')}
      </Link>
    </div>
  )
}
