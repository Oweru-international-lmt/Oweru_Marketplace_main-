import { AnimatePresence, motion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { can } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { LockIcon, SearchIcon } from '../components/icons'
import { PageHeader } from '../components/PageHeader'
import { RoleBadge } from '../components/RoleBadge'
import { TextField } from '../components/TextField'
import { errorMessage } from '../lib/errors'
import { initials } from '../lib/initials'
import { managementApi, type AccountSummary, type RoleAssignment } from '../lib/managementApi'
import { ASSIGNABLE_ROLES, REVOCABLE_ROLES } from '../lib/roles'
import { emailError } from '../lib/validation'
import { CreateStaffCard } from './staff/CreateStaffCard'
import { ManageAccountCard } from './staff/ManageAccountCard'

type Found = { account: AccountSummary; roles: RoleAssignment[] }
type Message = { tone: 'error' | 'success'; text: string }

export function ManagementStaffPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [email, setEmail] = useState('')
  const [fieldError, setFieldError] = useState<string>()
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  const [found, setFound] = useState<Found | 'none' | null>(null)

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const error = emailError(t, email)
    setFieldError(error)
    setSearchError(null)
    if (error) return

    setSearching(true)
    try {
      const [account] = await managementApi.findAccount(email.trim())
      if (!account) {
        setFound('none')
        return
      }
      setFound({ account, roles: await managementApi.accountRoles(account.id) })
    } catch (err) {
      setFound(null)
      setSearchError(errorMessage(t, err))
    } finally {
      setSearching(false)
    }
  }

  return (
    <>
      <PageHeader eyebrow={t('staffPage.kicker')} title={t('staffPage.title')} description={t('staffPage.intro')} />

      <div className="space-y-6">
        {can(user, 'account.manage') && (
          <CreateStaffCard onCreated={(account) => setFound({ account, roles: [] })} />
        )}
        <Card>
          <form noValidate onSubmit={handleSearch} className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-start">
            <TextField
              label={t('staffPage.searchLabel')}
              type="email"
              inputMode="email"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              placeholder={t('fields.emailPlaceholder')}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              error={fieldError}
            />
            <Button type="submit" loading={searching} loadingLabel={t('staffPage.searching')} className="sm:mt-[1.875rem] sm:w-auto">
              <SearchIcon className="size-4" />
              {t('staffPage.search')}
            </Button>
          </form>
          <p className="mt-4 text-xs text-muted">{t('staffPage.provisioningNote')}</p>
          {searchError && (
            <div className="mt-4">
              <Alert tone="error">{searchError}</Alert>
            </div>
          )}
        </Card>

        <AnimatePresence mode="wait">
          {found === 'none' && (
            <motion.div key="none" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <Card delay={0}>
                <p className="text-sm text-muted">{t('staffPage.notFound')}</p>
              </Card>
            </motion.div>
          )}
          {found && found !== 'none' && (
            <motion.div key={found.account.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <AccountResult found={found} onChange={setFound} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  )
}

function AccountResult({ found, onChange }: { found: Found; onChange: (found: Found) => void }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { account, roles } = found
  const isSelf = account.id === user?.id
  const isPublic = account.account_category === 'public'

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <Card delay={0} className="self-start">
        <div className="flex flex-col items-center text-center">
          <span className="grid size-16 place-items-center rounded-2xl bg-navy font-display text-xl font-semibold text-gold-light">
            {initials(account.full_name)}
          </span>
          <p className="mt-4 font-display text-lg font-semibold text-navy">{account.full_name}</p>
          <p className="mt-1 text-sm text-muted">{t(`categories.${account.account_category}`)}</p>
          <span
            className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              account.is_active ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
            }`}
          >
            <span className={`size-1.5 rounded-full ${account.is_active ? 'bg-success' : 'bg-danger'}`} aria-hidden="true" />
            {account.is_active ? t('staffPage.active') : t('staffPage.inactive')}
          </span>
          {account.must_change_password && (
            <span className="mt-2 text-xs font-medium text-muted">{t('staffAccount.pendingPassword')}</span>
          )}
        </div>
        <div className="mt-6 border-t border-mist pt-5">
          <p className="text-xs font-medium tracking-wide text-muted uppercase">{t('staffPage.currentRoles')}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {roles.length === 0 ? (
              <span className="text-sm text-muted">{t('staffPage.noRoles')}</span>
            ) : (
              roles.map((role) => (
                <RoleBadge key={role.role_code} role={role.role_code} state={role.is_active ? 'active' : 'revoked'} />
              ))
            )}
          </div>
        </div>
      </Card>

      {isSelf || isPublic ? (
        <Card title={t('staffPage.staffRoles')} titleId="staff-roles" delay={0.05} className="self-start">
          <p className="flex gap-3 rounded-xl bg-paper px-4 py-3 text-sm leading-relaxed text-muted">
            <LockIcon className="mt-0.5 size-4 shrink-0" />
            {isSelf ? t('staffPage.ownAccount') : t('staffPage.publicAccount')}
          </p>
        </Card>
      ) : (
        <div className="min-w-0 space-y-6">
          <StaffRolesCard found={found} onChange={onChange} />
          {!roles.some((role) => role.role_code === 'management' && role.is_active) && (
            <ManageAccountCard account={account} onChange={(updated) => onChange({ account: updated, roles })} />
          )}
        </div>
      )}
    </div>
  )
}

function StaffRolesCard({ found, onChange }: { found: Found; onChange: (found: Found) => void }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { account, roles } = found
  const [busyRole, setBusyRole] = useState<string | null>(null)
  const [confirmRole, setConfirmRole] = useState<string | null>(null)
  const [message, setMessage] = useState<Message | null>(null)

  const activeRoles = new Set(roles.filter((role) => role.is_active).map((role) => role.role_code))
  const canAssign = can(user, 'authorization.assign_role')
  const canRevoke = can(user, 'authorization.revoke_role')

  // Rows to manage: the assignable staff roles, plus any other operational
  // role the account currently holds (partners can be revoked, not assigned).
  const managedRoles = [
    ...ASSIGNABLE_ROLES,
    ...[...activeRoles].filter((role) => !(ASSIGNABLE_ROLES as readonly string[]).includes(role)),
  ]

  async function run(role: string, action: 'assign' | 'revoke') {
    setBusyRole(role)
    setConfirmRole(null)
    setMessage(null)
    const roleName = t(`roleNames.${role}`)
    try {
      if (action === 'assign') await managementApi.assignRole(account.id, role)
      else await managementApi.revokeRole(account.id, role)
      onChange({ account, roles: await managementApi.accountRoles(account.id) })
      setMessage({ tone: 'success', text: t(action === 'assign' ? 'staffPage.assigned' : 'staffPage.revoked', { role: roleName }) })
    } catch (error) {
      setMessage({ tone: 'error', text: errorMessage(t, error) })
    } finally {
      setBusyRole(null)
    }
  }

  return (
    <Card
      title={t('staffPage.staffRoles')}
      titleId="staff-roles"
      description={account.is_active ? undefined : t('staffPage.inactiveAccount')}
      delay={0.05}
      className="self-start"
    >
      <ul className="divide-y divide-mist rounded-xl border border-mist">
        {managedRoles.map((role) => {
          const active = activeRoles.has(role)
          const state = active ? 'active' : roles.some((r) => r.role_code === role) ? 'revoked' : 'absent'
          const assignable = (ASSIGNABLE_ROLES as readonly string[]).includes(role)
          const revocable = REVOCABLE_ROLES.includes(role)
          const roleName = t(`roleNames.${role}`)
          return (
            <li key={role} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5">
              <div className="flex items-center gap-3">
                <RoleBadge role={role} state={state} />
                <span className="text-sm text-muted">
                  {state === 'active'
                    ? t('staffPage.active')
                    : state === 'revoked'
                      ? t('staffPage.roleInactive')
                      : t('staffPage.notAssigned')}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {confirmRole === role ? (
                  <>
                    <span className="text-sm text-navy">{t('staffPage.confirmRevoke', { role: roleName })}</span>
                    <button
                      type="button"
                      onClick={() => void run(role, 'revoke')}
                      className="h-9 rounded-lg bg-danger px-3 text-sm font-semibold text-white hover:bg-danger/90"
                    >
                      {t('staffPage.confirm')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmRole(null)}
                      className="h-9 rounded-lg px-3 text-sm font-medium text-navy ring-1 ring-mist hover:bg-paper"
                    >
                      {t('staffPage.cancel')}
                    </button>
                  </>
                ) : active && revocable && canRevoke ? (
                  <button
                    type="button"
                    disabled={busyRole !== null}
                    onClick={() => setConfirmRole(role)}
                    className="h-9 rounded-lg px-3 text-sm font-medium text-danger ring-1 ring-danger/30 hover:bg-danger-soft disabled:opacity-60"
                  >
                    {busyRole === role ? t('common.loading') : t('staffPage.revoke')}
                  </button>
                ) : !active && assignable && canAssign && account.is_active ? (
                  <Button
                    type="button"
                    fullWidth={false}
                    className="h-9 rounded-lg px-4 text-sm"
                    loading={busyRole === role}
                    disabled={busyRole !== null}
                    onClick={() => void run(role, 'assign')}
                  >
                    {t('staffPage.assign')}
                  </Button>
                ) : !revocable && active ? (
                  <span className="text-xs text-muted">{t('staffPage.managedElsewhere')}</span>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>

      <AnimatePresence>
        {message && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
            <div className="pt-4">
              <Alert tone={message.tone}>{message.text}</Alert>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}
