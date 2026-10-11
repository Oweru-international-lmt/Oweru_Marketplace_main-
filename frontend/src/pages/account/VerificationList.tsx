import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckIcon, MailIcon, WhatsAppIcon } from '../../components/icons'
import { authApi, type User } from '../../lib/authApi'
import { errorMessage } from '../../lib/errors'

function Status({ ok }: { ok: boolean }) {
  const { t } = useTranslation()
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        ok ? 'bg-success-soft text-success' : 'bg-gold/15 text-navy'
      }`}
    >
      {ok && <CheckIcon className="size-3.5" />}
      {ok ? t('profile.verified') : t('profile.notVerified')}
    </span>
  )
}

// ACC-05 email confirmation (with resend) and ACC-01 phone confirmation status.
export function VerificationList({ user }: { user: User }) {
  const { t } = useTranslation()
  const [sending, setSending] = useState(false)
  const [note, setNote] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)

  async function resend() {
    setSending(true)
    setNote(null)
    try {
      await authApi.resendEmailConfirmation()
      setNote({ tone: 'ok', text: t('profile.resent') })
    } catch (error) {
      setNote({ tone: 'error', text: errorMessage(t, error) })
    } finally {
      setSending(false)
    }
  }

  return (
    <ul className="space-y-4">
      <li className="flex gap-3">
        <MailIcon className="mt-0.5 size-5 shrink-0 text-muted" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-navy">{t('fields.email')}</span>
            <Status ok={user.email_verified} />
          </div>
          {!user.email_verified && (
            <>
              <p className="mt-1 text-xs leading-relaxed text-muted">{t('profile.emailNote')}</p>
              <button type="button" onClick={() => void resend()} disabled={sending} className="text-link mt-2 text-xs disabled:opacity-60">
                {sending ? t('profile.resending') : t('profile.resend')}
              </button>
            </>
          )}
          {note && <p className={`mt-2 text-xs ${note.tone === 'ok' ? 'text-success' : 'text-danger'}`}>{note.text}</p>}
        </div>
      </li>
      <li className="flex gap-3">
        <WhatsAppIcon className="mt-0.5 size-5 shrink-0 text-muted" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-navy">{t('fields.phone')}</span>
            <Status ok={user.phone_verified} />
          </div>
          {!user.phone_verified && <p className="mt-1 text-xs leading-relaxed text-muted">{t('profile.phoneNote')}</p>}
        </div>
      </li>
    </ul>
  )
}
