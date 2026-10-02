import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Alert } from '../components/Alert'
import { AuthHeading } from '../components/AuthHeading'
import { Button } from '../components/Button'
import { StaggerGroup, StaggerItem } from '../components/Stagger'
import { TextField } from '../components/TextField'
import { ApiError } from '../lib/api'
import { authApi } from '../lib/authApi'
import { errorMessage, fieldErrorsFrom } from '../lib/errors'
import { passwordError } from '../lib/validation'

type Errors = { password?: string; confirm?: string }

function InvalidLink() {
  const { t } = useTranslation()
  return (
    <StaggerGroup className="space-y-6">
      <StaggerItem>
        <AuthHeading title={t('reset.invalidTitle')} subtitle={t('reset.invalidBody')} />
      </StaggerItem>
      <StaggerItem>
        <Link
          to="/forgot-password"
          className="inline-flex h-12 w-full items-center justify-center rounded-xl bg-gold px-6 font-display text-[15px] font-semibold text-navy transition-colors hover:bg-gold-light"
        >
          {t('reset.requestNew')}
        </Link>
      </StaggerItem>
      <StaggerItem className="text-center">
        <Link to="/login" className="text-link text-sm">
          {t('common.backToSignIn')}
        </Link>
      </StaggerItem>
    </StaggerGroup>
  )
}

// Opened from the emailed link: PASSWORD_RESET_URL?uid=...&token=...
export function ResetPasswordPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const uid = params.get('uid')
  const token = params.get('token')

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [linkRejected, setLinkRejected] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (!uid || !token || linkRejected) return <InvalidLink />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next: Errors = {
      password: passwordError(t, password),
      confirm: !confirm ? t('validation.required') : confirm !== password ? t('validation.passwordMismatch') : undefined,
    }
    setErrors(next)
    setFormError(null)
    if (next.password || next.confirm || !uid || !token) return

    setSubmitting(true)
    try {
      await authApi.confirmPasswordReset(uid, token, password)
      navigate('/login', { replace: true, state: { notice: 'resetDone' } })
    } catch (error) {
      if (error instanceof ApiError && error.status === 400 && error.detail) {
        setLinkRejected(true)
        return
      }
      const fields = error instanceof ApiError ? fieldErrorsFrom(t, error.fieldErrors) : {}
      if (fields.new_password) setErrors({ password: fields.new_password })
      else setFormError(errorMessage(t, error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <AuthHeading title={t('reset.title')} subtitle={t('reset.subtitle')} />

      <form noValidate onSubmit={handleSubmit}>
        <StaggerGroup className="space-y-5">
          {formError && (
            <StaggerItem>
              <Alert tone="error">{formError}</Alert>
            </StaggerItem>
          )}
          <StaggerItem>
            <TextField
              label={t('fields.newPassword')}
              type="password"
              autoComplete="new-password"
              hint={t('fields.passwordHint')}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              error={errors.password}
            />
          </StaggerItem>
          <StaggerItem>
            <TextField
              label={t('fields.confirmPassword')}
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              error={errors.confirm}
            />
          </StaggerItem>
          <StaggerItem>
            <Button type="submit" loading={submitting} loadingLabel={t('reset.submitting')}>
              {t('reset.submit')}
            </Button>
          </StaggerItem>
          <StaggerItem className="text-center">
            <Link to="/login" className="text-link text-sm">
              {t('common.backToSignIn')}
            </Link>
          </StaggerItem>
        </StaggerGroup>
      </form>
    </>
  )
}
