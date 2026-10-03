import { AnimatePresence, motion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { can } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { LockIcon, SearchIcon } from '../components/icons'
import { PageBody, PageHero } from '../components/PageHero'
import { RoleBadge } from '../components/RoleBadge'
import { TextField } from '../components/TextField'
import { errorMessage } from '../lib/errors'
import { managementApi, type AccountSummary, type RoleAssignment } from '../lib/managementApi'
import { ASSIGNABLE_ROLES, REVOCABLE_ROLES } from '../lib/roles'
import { emailError } from '../lib/validation'

type Found = { account: AccountSummary; roles: RoleAssignment[] }
type Message = { tone: 'error' | 'success'; text: string }

export function ManagementStaffPage() {
  const { t } = useTranslation()
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
      <PageHero kicker={t('staffPage.kicker')} title={t('staffPage.title')} intro={t('staffPage.intro')} />
      <PageBody>
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
              <AccountCard found={found} onChange={setFound} />
            </motion.div>
          )}
        </AnimatePresence>
      </PageBody>
    </>
  )
}

function initials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

function AccountCard({ found, onChange }: { found: Found; onChange: (found: Found) => void }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { account, roles } = found
  const [busyRole, setBusyRole] = useState<string | null>(null)
  const [confirmRole, setConfirmRole] = useState<string | null>(null)
  const [message, setMessage] = useState<Message | null>(null)

  const activeRoles = new Set(roles.filter((role) => role.is_active).map((role) => role.role_code))
  const isSelf = account.id === user?.id
  const isPublic = account.account_category === 'public'
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

  const blocker = isSelf
    ? t('staffPage.ownAccount')
    : isPublic
      ? t('staffPage.publicAccount')
      : !account.is_active
        ? t('staffPage.inactiveAccount')
        : null

  return (
    <Card delay={0}>
      <div className="flex flex-wrap items-center gap-4">
        <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-navy font-display text-lg font-semibold text-gold-light">
          {initials(account.full_name)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-xl font-semibold text-navy">{account.full_name}</p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
            <span>{t(`categories.${account.account_category}`)}</span>
            <span aria-hidden="true">·</span>
            <span className={account.is_active ? 'text-success' : 'text-danger'}>
              {account.is_active ? t('staffPage.active') : t('staffPage.inactive')}
            </span>
          </p>
        </div>
      </div>

      <div className="mt-6">
        <p className="text-sm font-medium text-navy">{t('staffPage.currentRoles')}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {roles.length === 0 ? (
            <span className="text-sm text-muted">{t('staffPage.noRoles')}</span>
          ) : (
            roles.map((role) => (
              <RoleBadge key={role.role_code} role={role.role_code} state={role.is_active ? 'active' : 'revoked'} />
            ))
          )}
        </div>
      </div>

      {blocker && (isSelf || isPublic) ? (
        <p className="mt-6 flex gap-2 rounded-2xl bg-paper px-4 py-3 text-sm leading-relaxed text-muted">
          <LockIcon className="mt-0.5 size-4 shrink-0" />
          {blocker}
        </p>
      ) : (
        <div className="mt-6">
          <p className="text-sm font-medium text-navy">{t('staffPage.staffRoles')}</p>
          {blocker && <p className="mt-2 text-sm text-muted">{blocker}</p>}
          <ul className="mt-3 divide-y divide-mist rounded-2xl border border-mist">
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
                  <div className="flex items-center gap-2">
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
                        className="h-9 w-auto rounded-lg px-4 text-sm"
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
        </div>
      )}

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
