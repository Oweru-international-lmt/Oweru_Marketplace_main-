import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { TextField } from '../../components/TextField'
import { isLanguage } from '../../i18n'
import { ApiError } from '../../lib/api'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { managementApi, type AccountSummary } from '../../lib/managementApi'
import { normalizePhone } from '../../lib/phone'
import { emailError } from '../../lib/validation'
import { TemporaryPasswordPanel } from './TemporaryPasswordPanel'

type Errors = { full_name?: string; email?: string; phone?: string }
type Created = { account: AccountSummary; password: string; email: string; phone: string }

// ACC-06: Management creates a staff account with a temporary password.
export function CreateStaffCard({ onCreated }: { onCreated: (account: AccountSummary) => void }) {
  const { t, i18n } = useTranslation()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [created, setCreated] = useState<Created | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedPhone = normalizePhone(phone)
    const next: Errors = {
      full_name: fullName.trim() ? undefined : t('validation.required'),
      email: emailError(t, email),
      phone: !phone.trim() ? t('validation.required') : normalizedPhone ? undefined : t('validation.phoneInvalid'),
    }
    setErrors(next)
    setFormError(null)
    if (next.full_name || next.email || !normalizedPhone) return

    setSubmitting(true)
    try {
      const result = await managementApi.createStaffAccount({
        full_name: fullName.trim(),
        email: email.trim(),
        phone: normalizedPhone,
        language: isLanguage(i18n.language) ? i18n.language : 'sw',
      })
      setCreated({ account: result.account, password: result.temporary_password, email: email.trim(), phone: normalizedPhone })
      setFullName('')
      setEmail('')
      setPhone('')
      onCreated(result.account)
    } catch (error) {
      const fields = error instanceof ApiError ? fieldErrorsFrom(t, error.fieldErrors) : {}
      setErrors({ full_name: fields.full_name, email: fields.email, phone: fields.phone })
      if (!fields.full_name && !fields.email && !fields.phone) setFormError(errorMessage(t, error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card title={t('staffAccount.createTitle')} titleId="create-staff" description={t('staffAccount.createDescription')}>
      {created ? (
        <TemporaryPasswordPanel
          name={created.account.full_name}
          password={created.password}
          email={created.email}
          phone={created.phone}
          onDone={() => setCreated(null)}
        />
      ) : (
        <form noValidate onSubmit={handleSubmit} className="space-y-5">
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="grid gap-5 sm:grid-cols-3">
            <TextField label={t('fields.fullName')} autoComplete="off" value={fullName} onChange={(e) => setFullName(e.target.value)} error={errors.full_name} />
            <TextField
              label={t('fields.email')}
              type="email"
              inputMode="email"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={errors.email}
            />
            <TextField
              label={t('fields.phone')}
              type="tel"
              inputMode="tel"
              autoComplete="off"
              placeholder="0712 345 678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              error={errors.phone}
            />
          </div>
          <Button type="submit" loading={submitting} loadingLabel={t('staffAccount.creating')} className="sm:w-auto">
            {t('staffAccount.create')}
          </Button>
        </form>
      )}
    </Card>
  )
}
