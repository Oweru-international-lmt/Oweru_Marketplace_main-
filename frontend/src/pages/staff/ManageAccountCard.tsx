import { useEffect, useState, type FormEvent } from 'react'
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

type Message = { tone: 'error' | 'success'; text: string }
type Change = { reason: string; active?: boolean; full_name?: string }

// ACC-06 / ADM-02: rename, deactivate or reactivate a staff account. Every
// change carries a reason and the account's current version.
export function ManageAccountCard({ account, onChange }: { account: AccountSummary; onChange: (account: AccountSummary) => void }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const canManage = can(user, 'account.manage')
  const canSuspend = can(user, 'account.suspend')
  const [version, setVersion] = useState<number | null>(null)
  const [mode, setMode] = useState<'idle' | 'edit' | 'status'>('idle')
  const [message, setMessage] = useState<Message | null>(null)

  useEffect(() => {
    let cancelled = false
    managementApi
      .account(account.id)
      .then((detail) => !cancelled && setVersion(detail.version))
      .catch((error: unknown) => !cancelled && setMessage({ tone: 'error', text: errorMessage(t, error) }))
    return () => {
      cancelled = true
    }
  }, [account.id, t])

  if (!canManage && !canSuspend) return null

  async function reloadVersion() {
    try {
      setVersion((await managementApi.account(account.id)).version)
    } catch {
      // The form already shows the conflict; a later retry reloads again.
    }
  }

  // Throws so the open form can show the error next to its fields.
  async function apply(change: Change) {
    if (version === null) return
    try {
      const result = await managementApi.changeAccount(account.id, { version, ...change })
      setVersion(result.version)
      onChange({ ...account, is_active: result.is_active, full_name: change.full_name ?? account.full_name })
    } catch (error) {
      // Someone else changed the account; fetch the new version so a retry works.
      if (error instanceof ApiError && error.status === 409) await reloadVersion()
      throw error
    }
  }

  return (
    <Card title={t('staffAccount.manageTitle')} titleId="manage-account" delay={0.1}>
      <div className="space-y-4">
        {message && <Alert tone={message.tone}>{message.text}</Alert>}

        {mode === 'edit' ? (
          <EditDetails
            account={account}
            onSubmit={apply}
            onCancel={() => setMode('idle')}
            onSaved={() => {
              setMode('idle')
              setMessage({ tone: 'success', text: t('staffAccount.saved') })
            }}
          />
        ) : mode === 'status' ? (
          <StatusForm
            account={account}
            onSubmit={apply}
            onCancel={() => setMode('idle')}
            onSaved={(active) => {
              setMode('idle')
              setMessage({ tone: 'success', text: active ? t('staffAccount.reactivated') : t('staffAccount.deactivated') })
            }}
          />
        ) : (
          <div className="flex flex-wrap gap-3">
            {canManage && (
              <Button type="button" variant="secondary" fullWidth={false} disabled={version === null} onClick={() => setMode('edit')}>
                {t('staffAccount.editDetails')}
              </Button>
            )}
            {canSuspend && (
              <button
                type="button"
                disabled={version === null}
                onClick={() => setMode('status')}
                className={`h-12 rounded-xl px-5 text-sm font-semibold ring-1 disabled:opacity-60 ${
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
  onSubmit,
  onCancel,
  onSaved,
}: {
  account: AccountSummary
  onSubmit: (change: Change) => Promise<void>
  onCancel: () => void
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const [fullName, setFullName] = useState(account.full_name)
  const [reason, setReason] = useState('')
  const [errors, setErrors] = useState<{ full_name?: string; reason?: string }>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = {
      full_name: fullName.trim() ? undefined : t('validation.required'),
      reason: reason.trim() ? undefined : t('server.reasonRequired'),
    }
    setErrors(next)
    setFormError(null)
    if (next.full_name || next.reason) return

    setSaving(true)
    try {
      await onSubmit({ full_name: fullName.trim(), reason: reason.trim() })
      onSaved()
    } catch (error) {
      const fields = error instanceof ApiError ? fieldErrorsFrom(t, error.fieldErrors) : {}
      setErrors({ full_name: fields.full_name, reason: fields.reason })
      if (!fields.full_name && !fields.reason) setFormError(errorMessage(t, error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit} className="space-y-5">
      {formError && <Alert tone="error">{formError}</Alert>}
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField label={t('fields.fullName')} autoComplete="off" value={fullName} onChange={(e) => setFullName(e.target.value)} error={errors.full_name} />
        <TextField label={t('staffAccount.reason')} value={reason} onChange={(e) => setReason(e.target.value)} error={errors.reason} />
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
  onSubmit,
  onCancel,
  onSaved,
}: {
  account: AccountSummary
  onSubmit: (change: Change) => Promise<void>
  onCancel: () => void
  onSaved: (active: boolean) => void
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
      await onSubmit({ active: activating, reason: reason.trim() })
      onSaved(activating)
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
