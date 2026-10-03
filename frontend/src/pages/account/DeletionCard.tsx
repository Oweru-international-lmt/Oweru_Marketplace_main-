import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/Alert'
import { Card } from '../../components/Card'
import { authApi, type DeletionRequest } from '../../lib/authApi'
import { errorMessage } from '../../lib/errors'

// ACC-08: request deletion; Management decides and keeps records the law requires.
export function DeletionCard() {
  const { t, i18n } = useTranslation()
  const [latest, setLatest] = useState<DeletionRequest | null | undefined>(undefined)
  const [reason, setReason] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ tone: 'error' | 'success'; text: string } | null>(null)

  useEffect(() => {
    let cancelled = false
    authApi
      .deletionRequest()
      .then((data) => !cancelled && setLatest(data.request))
      .catch(() => !cancelled && setLatest(null))
    return () => {
      cancelled = true
    }
  }, [])

  async function submit() {
    setBusy(true)
    setMessage(null)
    try {
      setLatest((await authApi.requestDeletion(reason.trim())).request)
      setConfirming(false)
      setReason('')
      setMessage({ tone: 'success', text: t('deletion.sent') })
    } catch (error) {
      setMessage({ tone: 'error', text: errorMessage(t, error) })
    } finally {
      setBusy(false)
    }
  }

  async function cancel() {
    setBusy(true)
    setMessage(null)
    try {
      await authApi.cancelDeletion()
      setLatest((await authApi.deletionRequest()).request)
      setMessage({ tone: 'success', text: t('deletion.cancelled') })
    } catch (error) {
      setMessage({ tone: 'error', text: errorMessage(t, error) })
    } finally {
      setBusy(false)
    }
  }

  if (latest === undefined) return null
  const pending = latest?.status === 'pending'
  const formatDate = (value: string) =>
    new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { dateStyle: 'long' }).format(new Date(value))

  return (
    <Card title={t('deletion.title')} titleId="account-deletion" description={t('deletion.description')} delay={0.2} className="ring-danger/20">
      <div className="space-y-4">
        {message && <Alert tone={message.tone}>{message.text}</Alert>}
        {latest?.status === 'declined' && latest.resolution_note && (
          <p className="rounded-xl bg-paper px-4 py-3 text-sm text-muted">{t('deletion.declined', { note: latest.resolution_note })}</p>
        )}
        {pending ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-gold/10 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-navy">{t('deletion.pending')}</p>
              <p className="text-xs text-muted">{t('deletion.requestedOn', { date: formatDate(latest.requested_at) })}</p>
            </div>
            <button
              type="button"
              onClick={() => void cancel()}
              disabled={busy}
              className="h-9 rounded-lg px-3 text-sm font-medium text-navy ring-1 ring-mist hover:bg-white disabled:opacity-60"
            >
              {t('deletion.cancel')}
            </button>
          </div>
        ) : (
          <>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-navy">{t('deletion.reason')}</span>
              <textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                rows={3}
                maxLength={2000}
                className="block w-full rounded-xl border border-mist bg-white px-4 py-3 text-[15px] text-navy outline-none focus:border-gold focus:ring-4 focus:ring-gold/20"
              />
            </label>
            {confirming ? (
              <div className="flex flex-wrap items-center gap-3 rounded-xl bg-danger-soft px-4 py-3">
                <p className="flex-1 text-sm text-danger">{t('deletion.confirm')}</p>
                <button
                  type="button"
                  onClick={() => void submit()}
                  disabled={busy}
                  className="h-9 rounded-lg bg-danger px-3 text-sm font-semibold text-white hover:bg-danger/90 disabled:opacity-60"
                >
                  {t('deletion.confirmYes')}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="h-9 rounded-lg px-3 text-sm font-medium text-navy ring-1 ring-mist hover:bg-white"
                >
                  {t('profile.cancel')}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="h-10 rounded-lg px-4 text-sm font-medium text-danger ring-1 ring-danger/30 hover:bg-danger-soft"
              >
                {t('deletion.submit')}
              </button>
            )}
          </>
        )}
      </div>
    </Card>
  )
}
