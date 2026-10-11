import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { can } from '../../auth/access'
import { useAuth } from '../../auth/useAuth'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { TextField } from '../../components/TextField'
import { ApiError } from '../../lib/api'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { managementApi, type AccountSummary } from '../../lib/managementApi'
import { normalizePhone } from '../../lib/phone'
import { TemporaryPasswordPanel } from './TemporaryPasswordPanel'

type Message = { tone: 'error' | 'success'; text: string }

// ACC-06: edit, issue a new temporary password, deactivate or reactivate a staff account.
export function ManageAccountCard({ account, onChange }: { account: AccountSummary; onChange: (account: AccountSummary) => void }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const canManage = can(user, 'account.manage')
  const canSuspend = can(user, 'account.suspend')
  const [mode, setMode] = useState<'idle' | 'edit' | 'status'>('idle')
  const [message, setMessage] = useState<Message | null>(null)
  const [temporary, setTemporary] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!canManage && !canSuspend) return null

  async function issuePassword() {
    setBusy(true)
    setMessage(null)
    try {
      const result = await managementApi.issueTemporaryPassword(account.id)
      setTemporary(result.temporary_password)
      onChange(result.account)
    } catch (error) {
      setMessage({ tone: 'error', text: errorMessage(t, error) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={t('staffAccount.manageTitle')} titleId="manage-account" delay={0.1}>
      <div className="space-y-4">
        {message && <Alert tone={message.tone}>{message.text}</Alert>}
        {temporary && (
          <TemporaryPasswordPanel name={account.full_name} password={temporary} onDone={() => setTemporary(null)} />
        )}

        {mode === 'edit' ? (
          <EditDetails
            account={account}
            onCancel={() => setMode('idle')}
            onSaved={(updated) => {
              onChange(updated)
              setMode('idle')
              setMessage({ tone: 'success', text: t('staffAccount.saved') })
            }}
          />
        ) : mode === 'status' ? (
          <StatusForm
            account={account}
            onCancel={() => setMode('idle')}
            onSaved={(updated) => {
              onChange(updated)
              setMode('idle')
              setMessage({ tone: 'success', text: updated.is_active ? t('staffAccount.reactivated') : t('staffAccount.deactivated') })
            }}
          />
        ) : (
          <div className="flex flex-wrap gap-3">
            {canManage && (
              <>
                <Button type="button" variant="secondary" fullWidth={false} onClick={() => setMode('edit')}>
                  {t('staffAccount.editDetails')}
                </Button>
                <Button type="button" variant="secondary" fullWidth={false} loading={busy} onClick={() => void issuePassword()}>
                  {t('staffAccount.newTempPassword')}
                </Button>
              </>
            )}
            {canSuspend && (
              <button
                type="button"
                onClick={() => setMode('status')}
                className={`h-12 rounded-xl px-5 text-sm font-semibold ring-1 ${
                  account.is_active ? 'text-danger ring-danger/30 hover:bg-danger-soft' : 'text-success ring-success/30 hover:bg-success-soft'
                }`}
              >
                {account.is_active ? t('staffAccount.deactivate') : t('staffAccount.reactivate')}
              </button>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}

function EditDetails({
  account,
  onCancel,
  onSaved,
}: {
  account: AccountSummary
  onCancel: () => void
  onSaved: (account: AccountSummary) => void
}) {
  const { t } = useTranslation()
  const [fullName, setFullName] = useState(account.full_name)
  const [phone, setPhone] = useState('')
  const [errors, setErrors] = useState<{ full_name?: string; phone?: string }>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = phone.trim() ? normalizePhone(phone) : null
    const next = {
      full_name: fullName.trim() ? undefined : t('validation.required'),
      phone: phone.trim() && !normalized ? t('validation.phoneInvalid') : undefined,
    }
    setErrors(next)
    setFormError(null)
    if (next.full_name || next.phone) return

    setSaving(true)
    try {
      onSaved(await managementApi.updateStaffAccount(account.id, { full_name: fullName.trim(), ...(normalized ? { phone: normalized } : {}) }))
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
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField label={t('fields.fullName')} autoComplete="off" value={fullName} onChange={(e) => setFullName(e.target.value)} error={errors.full_name} />
        <TextField
          label={t('staffAccount.newPhone')}
          type="tel"
          inputMode="tel"
          autoComplete="off"
          hint={t('staffAccount.newPhoneHint')}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          error={errors.phone}
        />
      </div>
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

function StatusForm({
  account,
  onCancel,
  onSaved,
}: {
  account: AccountSummary
  onCancel: () => void
  onSaved: (account: AccountSummary) => void
}) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string>()
  const [saving, setSaving] = useState(false)
  const activating = !account.is_active

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!reason.trim()) {
      setError(t('server.reasonRequired'))
      return
    }
    setSaving(true)
    setError(undefined)
    try {
      onSaved(await managementApi.setAccountActive(account.id, activating, reason.trim()))
    } catch (err) {
      setError(errorMessage(t, err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit} className="space-y-4">
      <TextField label={t('staffAccount.reason')} value={reason} onChange={(e) => setReason(e.target.value)} error={error} />
      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          disabled={saving}
          className={`h-12 rounded-xl px-5 text-sm font-semibold text-white disabled:opacity-60 ${
            activating ? 'bg-success hover:bg-success/90' : 'bg-danger hover:bg-danger/90'
          }`}
        >
          {activating ? t('staffAccount.reactivate') : t('staffAccount.deactivate')}
        </button>
        <Button type="button" variant="secondary" fullWidth={false} onClick={onCancel} disabled={saving}>
          {t('profile.cancel')}
        </Button>
      </div>
    </form>
  )
}
