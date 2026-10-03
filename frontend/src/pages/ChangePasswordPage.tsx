import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { AuthHeading } from '../components/AuthHeading'
import { ChangePasswordForm } from '../components/ChangePasswordForm'

// ACC-06: staff and partners replace their temporary password at first sign-in.
export function ChangePasswordPage() {
  const { t } = useTranslation()
  const { signOut } = useAuth()
  const navigate = useNavigate()

  return (
    <>
      <AuthHeading title={t('security.forcedTitle')} subtitle={t('security.forcedSubtitle')} />
      <ChangePasswordForm submitLabel={t('security.forcedSubmit')} onChanged={() => navigate('/account', { replace: true })} />
      <button
        type="button"
        onClick={() => {
          signOut()
          navigate('/login', { replace: true })
        }}
        className="text-link mt-6 text-sm"
      >
        {t('account.signOut')}
      </button>
    </>
  )
}
