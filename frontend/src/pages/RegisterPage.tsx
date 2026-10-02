import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { AuthHeading } from '../components/AuthHeading'
import { Button } from '../components/Button'
import { StaggerGroup, StaggerItem } from '../components/Stagger'
import { TextField } from '../components/TextField'
import { isLanguage } from '../i18n'
import { ApiError } from '../lib/api'
import { errorMessage, fieldErrorsFrom } from '../lib/errors'
import { normalizePhone } from '../lib/phone'
import { emailError, passwordError } from '../lib/validation'

type Field = 'full_name' | 'email' | 'phone' | 'password' | 'confirm'
type Errors = Partial<Record<Field, string>>

export function RegisterPage() {
  const { t, i18n } = useTranslation()
  const { register, signIn } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function validate(normalizedPhone: string | null): Errors {
    return {
      full_name: fullName.trim() ? undefined : t('validation.required'),
      email: emailError(t, email),
      phone: !phone.trim() ? t('validation.required') : normalizedPhone ? undefined : t('validation.phoneInvalid'),
      password: passwordError(t, password),
      confirm: !confirm ? t('validation.required') : confirm !== password ? t('validation.passwordMismatch') : undefined,
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedPhone = normalizePhone(phone)
    const next = validate(normalizedPhone)
    setErrors(next)
    setFormError(null)
    if (!normalizedPhone || Object.values(next).some(Boolean)) return

    setSubmitting(true)
    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        phone: normalizedPhone,
        password,
        // The language chosen with the header switch becomes the account preference.
        language: isLanguage(i18n.language) ? i18n.language : 'sw',
      })
    } catch (error) {
      const fields = error instanceof ApiError ? fieldErrorsFrom(t, error.fieldErrors) : {}
      setErrors(fields)
      if (Object.keys(fields).length === 0) setFormError(errorMessage(t, error))
      setSubmitting(false)
      return
    }

    try {
      await signIn(email.trim(), password)
      navigate('/account', { replace: true })
    } catch {
      // The account exists now; retrying sign-up would only say "email taken".
      navigate('/login', { replace: true, state: { notice: 'registered' } })
    }
  }

  return (
    <>
      <AuthHeading title={t('register.title')} subtitle={t('register.subtitle')} />

      <form noValidate onSubmit={handleSubmit}>
        <StaggerGroup className="space-y-5">
          {formError && (
            <StaggerItem>
              <Alert tone="error">{formError}</Alert>
            </StaggerItem>
          )}

          <StaggerItem>
            <TextField
              label={t('fields.fullName')}
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              error={errors.full_name}
            />
          </StaggerItem>

          <StaggerItem>
            <TextField
              label={t('fields.email')}
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              placeholder={t('fields.emailPlaceholder')}
              hint={t('fields.emailHint')}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              error={errors.email}
            />
          </StaggerItem>

          <StaggerItem>
            <TextField
              label={t('fields.phone')}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="0712 345 678"
              hint={t('fields.phoneHint')}
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              error={errors.phone}
            />
          </StaggerItem>

          <StaggerItem className="grid gap-5 sm:grid-cols-2">
            <TextField
              label={t('fields.password')}
              type="password"
              autoComplete="new-password"
              hint={t('fields.passwordHint')}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              error={errors.password}
            />
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
            <Button type="submit" loading={submitting} loadingLabel={t('register.submitting')}>
              {t('register.submit')}
            </Button>
          </StaggerItem>

          <StaggerItem>
            <p className="text-center text-sm text-muted">
              {t('register.haveAccount')}{' '}
              <Link to="/login" className="text-link">
                {t('register.signIn')}
              </Link>
            </p>
          </StaggerItem>
        </StaggerGroup>
      </form>
    </>
  )
}
