import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { ApiError } from '../lib/api'
import { authApi } from '../lib/authApi'
import { errorMessage, fieldErrorsFrom } from '../lib/errors'
import { passwordError } from '../lib/validation'
import type { LoginNotice } from '../pages/LoginPage'
import { Alert } from './Alert'
import { Button } from './Button'
import { TextField } from './TextField'

type Errors = { current?: string; next?: string; confirm?: string }

// The server ends every session, this one included, so a successful change
// signs out here and asks for the new password.
export function ChangePasswordForm({ submitLabel }: { submitLabel: string }) {
  const { t } = useTranslation()
  const { signOut, user } = useAuth()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const validation: Errors = {
      current: current ? undefined : t('validation.required'),
      next: passwordError(t, next),
      confirm: !confirm ? t('validation.required') : confirm !== next ? t('validation.passwordMismatch') : undefined,
    }
    setErrors(validation)
    setFormError(null)
    if (Object.values(validation).some(Boolean)) return

    setSubmitting(true)
    try {
      await authApi.changePassword(current, next)
      signOut()
      navigate('/login', { replace: true, state: { notice: 'passwordChanged' satisfies LoginNotice } })
    } catch (error) {
      const fields = error instanceof ApiError ? fieldErrorsFrom(t, error.fieldErrors) : {}
      setErrors({ current: fields.current_password, next: fields.new_password, confirm: fields.new_password_confirm })
      if (!fields.current_password && !fields.new_password && !fields.new_password_confirm) {
        setFormError(errorMessage(t, error))
      }
      setSubmitting(false)
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit} className="space-y-5">
      {/* Lets password managers file the new password under the right account. */}
      <input type="email" name="username" autoComplete="username" value={user?.email ?? ''} readOnly hidden />
      {formError && <Alert tone="error">{formError}</Alert>}
      <TextField
        label={t('security.currentPassword')}
        type="password"
        autoComplete="current-password"
        value={current}
        onChange={(event) => setCurrent(event.target.value)}
        error={errors.current}
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField
          label={t('fields.newPassword')}
          type="password"
          autoComplete="new-password"
          hint={t('fields.passwordHint')}
          value={next}
          onChange={(event) => setNext(event.target.value)}
          error={errors.next}
        />
        <TextField
          label={t('fields.confirmPassword')}
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          error={errors.confirm}
        />
      </div>
      <Button type="submit" loading={submitting} loadingLabel={t('security.submitting')} className="sm:w-auto">
        {submitLabel}
      </Button>
    </form>
  )
}
