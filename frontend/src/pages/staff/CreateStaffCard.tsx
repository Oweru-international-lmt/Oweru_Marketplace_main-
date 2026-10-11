import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { TextField } from '../../components/TextField'
import { isLanguage } from '../../i18n'
import { ApiError } from '../../lib/api'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { managementApi, type AccountSummary, type StaffAccountInput } from '../../lib/managementApi'
import { normalizePhone } from '../../lib/phone'
import { ASSIGNABLE_ROLES } from '../../lib/roles'
import { emailError } from '../../lib/validation'

type Errors = { full_name?: string; email?: string; phone?: string }
type StaffRole = StaffAccountInput['role']

// ACC-06: Management creates a Verifier or Marketer account. The backend emails
// the staff member a link to set their own password.
export function CreateStaffCard({ onCreated }: { onCreated: (account: AccountSummary, role: StaffRole) => void }) {
  const { t, i18n } = useTranslation()
  const [role, setRole] = useState<StaffRole>(ASSIGNABLE_ROLES[0])
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [createdEmail, setCreatedEmail] = useState<string | null>(null)

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
    setCreatedEmail(null)
    if (next.full_name || next.email || !normalizedPhone) return

    setSubmitting(true)
    try {
      const { id } = await managementApi.createStaffAccount({
        role,
        full_name: fullName.trim(),
        email: email.trim(),
        phone: normalizedPhone,
        language: isLanguage(i18n.language) ? i18n.language : 'sw',
      })
      setCreatedEmail(email.trim())
      onCreated({ id, full_name: fullName.trim(), account_category: 'operational', is_active: true }, role)
      setFullName('')
      setEmail('')
      setPhone('')
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
      <form noValidate onSubmit={handleSubmit} className="space-y-5">
        {formError && <Alert tone="error">{formError}</Alert>}
        {createdEmail && <Alert tone="success">{t('staffAccount.created', { email: createdEmail })}</Alert>}
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-navy">{t('staffAccount.role')}</legend>
          <div className="grid grid-cols-2 gap-3 sm:max-w-md">
            {ASSIGNABLE_ROLES.map((option) => (
              <label
                key={option}
                className="flex h-12 cursor-pointer items-center gap-3 rounded-xl border border-mist bg-white px-4 text-[15px] has-checked:border-gold has-checked:bg-gold/8"
              >
                <input
                  type="radio"
                  name="staff-role"
                  checked={role === option}
                  onChange={() => setRole(option)}
                  className="size-4 accent-gold"
                />
                {t(`roleNames.${option}`)}
              </label>
            ))}
          </div>
        </fieldset>
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
    </Card>
  )
}
