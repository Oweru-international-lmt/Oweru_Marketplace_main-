import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { can } from '../../auth/access'
import { useAuth } from '../../auth/useAuth'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { TextField } from '../../components/TextField'
import { isLanguage, LANGUAGES, type Language } from '../../i18n'
import { ApiError } from '../../lib/api'
import { authApi, type User } from '../../lib/authApi'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { formatPhone, normalizePhone } from '../../lib/phone'

type Errors = { full_name?: string; phone?: string }

// ACC-08: view and edit own name, phone and language. Email is the sign-in
// identifier and is not edited here.
export function ProfileDetailsCard({ user }: { user: User }) {
  const { t, i18n } = useTranslation()
  const { setUser } = useAuth()
  const [editing, setEditing] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const canEdit = can(user, 'account.update')

  const memberSince = new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { dateStyle: 'long' }).format(
    new Date(user.created_at),
  )
  const rows = [
    { label: t('fields.fullName'), value: user.full_name },
    { label: t('fields.email'), value: user.email },
    { label: t('fields.phone'), value: formatPhone(user.phone) },
    { label: t('fields.language'), value: isLanguage(user.language) ? t(`common.languageNames.${user.language}`) : user.language },
    { label: t('account.memberSince'), value: memberSince },
  ]

  return (
    <Card
      title={t('account.details')}
      titleId="account-details"
      delay={0.1}
      action={
        canEdit && !editing ? (
          <button
            type="button"
            onClick={() => {
              setMessage(null)
              setEditing(true)
            }}
            className="h-9 rounded-lg px-3 text-sm font-medium text-navy ring-1 ring-mist hover:bg-paper"
          >
            {t('profile.edit')}
          </button>
        ) : undefined
      }
    >
      {message && (
        <div className="mb-4">
          <Alert tone="success">{message}</Alert>
        </div>
      )}
      {editing ? (
        <EditForm
          user={user}
          onCancel={() => setEditing(false)}
          onSaved={(updated) => {
            setUser(updated)
            if (isLanguage(updated.language)) void i18n.changeLanguage(updated.language)
            setEditing(false)
            setMessage(t('profile.saved'))
          }}
        />
      ) : (
        <dl className="divide-y divide-mist">
          {rows.map((row) => (
            <div key={row.label} className="grid gap-1 py-4 first:pt-0 last:pb-0 sm:grid-cols-[200px_1fr] sm:gap-6">
              <dt className="text-sm text-muted">{row.label}</dt>
              <dd className="text-[15px] font-medium break-words text-navy">{row.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  )
}

function EditForm({ user, onCancel, onSaved }: { user: User; onCancel: () => void; onSaved: (user: User) => void }) {
  const { t } = useTranslation()
  const [fullName, setFullName] = useState(user.full_name)
  const [phone, setPhone] = useState(formatPhone(user.phone))
  const [language, setLanguage] = useState<Language>(user.language)
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = normalizePhone(phone)
    const next: Errors = {
      full_name: fullName.trim() ? undefined : t('validation.required'),
      phone: !phone.trim() ? t('validation.required') : normalized ? undefined : t('validation.phoneInvalid'),
    }
    setErrors(next)
    setFormError(null)
    if (next.full_name || !normalized) return

    setSaving(true)
    try {
      onSaved(await authApi.updateProfile({ full_name: fullName.trim(), phone: normalized, language }))
    } catch (error) {
      const fields = error instanceof ApiError ? fieldErrorsFrom(t, error.fieldErrors) : {}
      setErrors({ full_name: fields.full_name, phone: fields.phone })
      if (!fields.full_name && !fields.phone) setFormError(errorMessage(t, error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit} className="space-y-5">
      {formError && <Alert tone="error">{formError}</Alert>}
      <TextField label={t('fields.fullName')} autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} error={errors.full_name} />
      <TextField
        label={t('fields.phone')}
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        hint={t('profile.phoneChangeNote')}
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        error={errors.phone}
      />
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium text-navy">{t('fields.language')}</legend>
        <div className="grid grid-cols-2 gap-3">
          {LANGUAGES.map((option) => (
            <label
              key={option}
              className="flex h-12 cursor-pointer items-center gap-3 rounded-xl border border-mist bg-white px-4 text-[15px] has-checked:border-gold has-checked:bg-gold/8"
            >
              <input
                type="radio"
                name="profile-language"
                checked={language === option}
                onChange={() => setLanguage(option)}
                className="size-4 accent-gold"
              />
              <span lang={option}>{t(`common.languageNames.${option}`)}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap gap-3">
        <Button type="submit" loading={saving} loadingLabel={t('profile.saving')} fullWidth={false}>
          {t('profile.save')}
        </Button>
        <Button type="button" variant="secondary" fullWidth={false} onClick={onCancel} disabled={saving}>
          {t('profile.cancel')}
        </Button>
      </div>
    </form>
  )
}
