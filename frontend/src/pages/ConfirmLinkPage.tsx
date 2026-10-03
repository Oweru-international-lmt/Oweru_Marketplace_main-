import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { Alert } from '../components/Alert'
import { AuthHeading } from '../components/AuthHeading'
import { Button } from '../components/Button'
import { FullPageLoader } from '../components/FullPageLoader'
import { AlertIcon, CheckIcon, WhatsAppIcon } from '../components/icons'
import { ApiError } from '../lib/api'
import { authApi, type ConfirmationLink } from '../lib/authApi'
import { errorMessage } from '../lib/errors'

type View =
  | { kind: 'loading' }
  | { kind: 'ready'; link: ConfirmationLink }
  | { kind: 'done'; decision: 'confirmed' | 'declined' }
  | { kind: 'unusable'; state: 'used' | 'expired' | 'invalid' }

// SRD 20.3 WhatsApp confirmation page: shows exactly what is being confirmed,
// then stores Confirm or Decline once. Opened without signing in.
export function ConfirmLinkPage() {
  const { t, i18n } = useTranslation()
  const [params] = useSearchParams()
  const id = params.get('id') ?? ''
  const token = params.get('token') ?? ''
  const [view, setView] = useState<View>(id && token ? { kind: 'loading' } : { kind: 'unusable', state: 'invalid' })
  const [busy, setBusy] = useState<'confirmed' | 'declined' | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id || !token) return
    let cancelled = false
    authApi
      .confirmationLink(id, token)
      .then((link) => {
        if (cancelled) return
        setView(link.state === 'valid' ? { kind: 'ready', link } : { kind: 'unusable', state: link.state })
      })
      .catch(() => !cancelled && setView({ kind: 'unusable', state: 'invalid' }))
    return () => {
      cancelled = true
    }
  }, [id, token])

  async function decide(decision: 'confirmed' | 'declined') {
    setBusy(decision)
    setError(null)
    try {
      await authApi.decideConfirmationLink(id, token, decision)
      setView({ kind: 'done', decision })
    } catch (err) {
      const state = err instanceof ApiError && err.status === 400 ? 'used' : null
      if (state) setView({ kind: 'unusable', state })
      else setError(errorMessage(t, err))
    } finally {
      setBusy(null)
    }
  }

  if (view.kind === 'loading') return <FullPageLoader inline />

  if (view.kind === 'ready') {
    const expires = new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', {
      dateStyle: 'long',
      timeStyle: 'short',
    }).format(new Date(view.link.expires_at))
    return (
      <div className="space-y-6">
        <span className="grid size-14 place-items-center rounded-2xl bg-[#1f7a4d]/10 text-[#1f7a4d]">
          <WhatsAppIcon className="size-7" />
        </span>
        <AuthHeading
          title={t('confirmLink.phoneTitle')}
          subtitle={t('confirmLink.phoneBody', { phone: view.link.recipient, name: view.link.full_name })}
        />
        <p className="-mt-4 text-sm text-muted">{t('confirmLink.expires', { date: expires })}</p>
        {error && <Alert tone="error">{error}</Alert>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Button type="button" loading={busy === 'confirmed'} disabled={busy !== null} onClick={() => void decide('confirmed')}>
            {t('confirmLink.confirm')}
          </Button>
          <Button
            type="button"
            variant="secondary"
            loading={busy === 'declined'}
            disabled={busy !== null}
            onClick={() => void decide('declined')}
          >
            {t('confirmLink.decline')}
          </Button>
        </div>
      </div>
    )
  }

  const confirmed = view.kind === 'done' && view.decision === 'confirmed'
  const title =
    view.kind === 'done'
      ? confirmed
        ? t('confirmLink.confirmedTitle')
        : t('confirmLink.declinedTitle')
      : t(`confirmLink.${view.state}Title`)
  const body =
    view.kind === 'done' ? (confirmed ? t('confirmLink.confirmedBody') : t('confirmLink.declinedBody')) : t('confirmLink.askNew')

  return (
    <div className="space-y-6">
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 260, damping: 18 }}
        className={`grid size-14 place-items-center rounded-2xl ${confirmed ? 'bg-success-soft text-success' : 'bg-gold/15 text-navy'}`}
      >
        {confirmed ? <CheckIcon className="size-7" /> : <AlertIcon className="size-7" />}
      </motion.span>
      <AuthHeading title={title} subtitle={body} />
    </div>
  )
}
