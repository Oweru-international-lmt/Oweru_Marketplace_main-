import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/Alert'
import { Card } from '../../components/Card'
import { authApi, type DeletionRequest } from '../../lib/authApi'
import { errorMessage } from '../../lib/errors'

// ACC-08: request deletion; Management decides and keeps records the law requires.
// The API can't list or withdraw a request yet. Sending again is safe: it
// returns the request that is already pending.
export function DeletionCard() {
  const { t, i18n } = useTranslation()
  const [sent, setSent] = useState<DeletionRequest | null>(null)
  const [reason, setReason] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      setSent(await authApi.requestDeletion(reason.trim()))
      setConfirming(false)
      setReason('')
    } catch (err) {
      setError(errorMessage(t, err))
    } finally {
      setBusy(false)
    }
  }

  const formatDate = (value: string) =>
    new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { dateStyle: 'long' }).format(new Date(value))

  return (
    <Card title={t('deletion.title')} titleId="account-deletion" description={t('deletion.description')} delay={0.2} className="ring-danger/20">
      <div className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {sent ? (
          <div className="rounded-xl bg-gold/10 px-4 py-3">
            <p className="text-sm font-medium text-navy">{t('deletion.pending')}</p>
            <p className="text-xs text-muted">{t('deletion.requestedOn', { date: formatDate(sent.requested_at) })}</p>
            <p className="mt-2 text-xs text-muted">{t('deletion.withdrawNote')}</p>
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
