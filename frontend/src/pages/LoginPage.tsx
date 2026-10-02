import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { AuthHeading } from '../components/AuthHeading'
import { Button } from '../components/Button'
import { StaggerGroup, StaggerItem } from '../components/Stagger'
import { TextField } from '../components/TextField'
import { ApiError } from '../lib/api'
import { errorMessage, fieldErrorsFrom } from '../lib/errors'
import { emailError } from '../lib/validation'

export type LoginNotice = 'resetDone' | 'registered' | 'sessionExpired'
type LoginState = { from?: string; notice?: LoginNotice } | null

type Errors = { email?: string; password?: string }

export function LoginPage() {
  const { t } = useTranslation()
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const state = useLocation().state as LoginState

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [showLockoutNote, setShowLockoutNote] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next: Errors = {
      email: emailError(t, email),
      password: password ? undefined : t('validation.required'),
    }
    setErrors(next)
    setFormError(null)
    setShowLockoutNote(false)
    if (next.email || next.password) return

    setSubmitting(true)
    try {
      await signIn(email.trim(), password)
      navigate(state?.from ?? '/account', { replace: true })
    } catch (error) {
      const fields = error instanceof ApiError ? fieldErrorsFrom(t, error.fieldErrors) : {}
      setErrors(fields)
      if (Object.keys(fields).length === 0) setFormError(errorMessage(t, error))
      // The backend gives the same answer for a wrong password and a locked
      // account, so explain the lockout rule whenever sign-in is refused.
      setShowLockoutNote(error instanceof ApiError && error.status === 400 && error.detail !== null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <AuthHeading title={t('login.title')} subtitle={t('login.subtitle')} />

      <form noValidate onSubmit={handleSubmit}>
        <StaggerGroup className="space-y-5">
          {state?.notice && !formError && (
            <StaggerItem>
              <Alert tone={state.notice === 'sessionExpired' ? 'error' : 'success'}>{t(`login.${state.notice}`)}</Alert>
            </StaggerItem>
          )}
          {formError && (
            <StaggerItem>
              <Alert tone="error">
                <p>{formError}</p>
                {showLockoutNote && <p className="mt-1 text-danger/85">{t('login.lockoutNote')}</p>}
              </Alert>
            </StaggerItem>
          )}

          <StaggerItem>
            <TextField
              label={t('fields.email')}
              type="email"
              inputMode="email"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              placeholder={t('fields.emailPlaceholder')}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              error={errors.email}
            />
          </StaggerItem>

          <StaggerItem>
            <TextField
              label={t('fields.password')}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              error={errors.password}
            />
            <div className="mt-2.5 flex justify-end">
              <Link to="/forgot-password" className="text-link text-sm">
                {t('login.forgot')}
              </Link>
            </div>
          </StaggerItem>

          <StaggerItem>
            <Button type="submit" loading={submitting} loadingLabel={t('login.submitting')}>
              {t('login.submit')}
            </Button>
          </StaggerItem>

          <StaggerItem>
            <p className="text-center text-sm text-muted">
              {t('login.noAccount')}{' '}
              <Link to="/register" className="text-link">
                {t('login.register')}
              </Link>
            </p>
          </StaggerItem>
        </StaggerGroup>
      </form>
    </>
  )
}
