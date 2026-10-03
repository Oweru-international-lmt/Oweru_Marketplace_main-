import { AnimatePresence, motion } from 'motion/react'
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { can } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { LockIcon, ShieldIcon, TickIcon, UsersIcon, WhatsAppIcon } from '../components/icons'
import { PageHeader } from '../components/PageHeader'
import { RoleBadge } from '../components/RoleBadge'
import { StatTile } from '../components/StatTile'
import { Switch } from '../components/Switch'
import { errorMessage } from '../lib/errors'
import { managementApi, type Permission } from '../lib/managementApi'
import {
  ALL_ROLES,
  OUTBOX_OPTIONAL_ROLES,
  OUTBOX_PERMISSION,
  PERMISSION_GROUP_ORDER,
  permissionGroup,
  ROLE_GROUPS,
} from '../lib/roles'

type Grants = Record<string, Set<string>>
type Data = { permissions: Permission[]; grants: Grants }

async function loadMatrix(): Promise<Data> {
  const [permissions, ...perRole] = await Promise.all([
    managementApi.permissions(),
    ...ALL_ROLES.map((role) => managementApi.rolePermissions(role)),
  ])
  const grants: Grants = {}
  ALL_ROLES.forEach((role, index) => {
    grants[role] = new Set(perRole[index].map((permission) => permission.code))
  })
  return { permissions, grants }
}

function groupPermissions(permissions: Permission[]) {
  const groups = new Map<string, Permission[]>()
  for (const permission of permissions) {
    const group = permissionGroup(permission.code)
    groups.set(group, [...(groups.get(group) ?? []), permission])
  }
  const order = (group: string) => {
    const index = PERMISSION_GROUP_ORDER.indexOf(group)
    return index === -1 ? PERMISSION_GROUP_ORDER.length : index
  }
  return [...groups.entries()].sort(([a], [b]) => order(a) - order(b))
}

export function ManagementRolesPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [data, setData] = useState<Data | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    loadMatrix()
      .then((result) => !cancelled && setData(result))
      .catch((error: unknown) => !cancelled && setLoadError(errorMessage(t, error)))
    return () => {
      cancelled = true
    }
    // `t` is left out on purpose: a language switch should not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt])

  const retry = useCallback(() => {
    setLoadError(null)
    setAttempt((value) => value + 1)
  }, [])

  function setGrant(role: string, granted: boolean) {
    setData((current) => {
      if (!current) return current
      const next = new Set(current.grants[role])
      if (granted) next.add(OUTBOX_PERMISSION)
      else next.delete(OUTBOX_PERMISSION)
      return { ...current, grants: { ...current.grants, [role]: next } }
    })
  }

  const outboxEnabled = data
    ? OUTBOX_OPTIONAL_ROLES.filter((role) => data.grants[role]?.has(OUTBOX_PERMISSION)).length
    : 0

  return (
    <>
      <PageHeader eyebrow={t('rolesPage.kicker')} title={t('rolesPage.title')} description={t('rolesPage.intro')} />
      {loadError ? (
        <Card>
          <div className="space-y-4">
            <Alert tone="error">{loadError}</Alert>
            <Button type="button" variant="secondary" className="sm:w-auto" onClick={retry}>
              {t('common.retry')}
            </Button>
          </div>
        </Card>
      ) : !data ? (
        <MatrixSkeleton />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatTile label={t('rolesPage.statRoles')} value={String(ALL_ROLES.length)} icon={UsersIcon} />
            <StatTile label={t('rolesPage.statPermissions')} value={String(data.permissions.length)} icon={ShieldIcon} delay={0.05} />
            <StatTile
              label={t('rolesPage.statOutbox')}
              value={t('rolesPage.statOutboxValue', { count: outboxEnabled, total: OUTBOX_OPTIONAL_ROLES.length })}
              icon={WhatsAppIcon}
              delay={0.1}
            />
          </div>
          <OutboxCard grants={data.grants} canManage={can(user, 'authorization.manage_outbox')} onGranted={setGrant} />
          <MatrixCard data={data} />
        </div>
      )}
    </>
  )
}

function OutboxCard({
  grants,
  canManage,
  onGranted,
}: {
  grants: Grants
  canManage: boolean
  onGranted: (role: string, granted: boolean) => void
}) {
  const { t } = useTranslation()
  const [busyRole, setBusyRole] = useState<string | null>(null)
  const [message, setMessage] = useState<{ tone: 'error' | 'success'; text: string } | null>(null)

  async function toggle(role: string, enabled: boolean) {
    setBusyRole(role)
    setMessage(null)
    onGranted(role, enabled)
    try {
      await managementApi.setOutboxSend(role, enabled)
      setMessage({ tone: 'success', text: t('rolesPage.outboxSaved') })
    } catch (error) {
      onGranted(role, !enabled)
      setMessage({ tone: 'error', text: errorMessage(t, error) })
    } finally {
      setBusyRole(null)
    }
  }

  return (
    <Card title={t('rolesPage.outboxTitle')} titleId="outbox-grants" description={t('rolesPage.outboxBody')} delay={0.1}>
      <ul className="grid gap-3 sm:grid-cols-2">
        {OUTBOX_OPTIONAL_ROLES.map((role) => {
          const enabled = grants[role]?.has(OUTBOX_PERMISSION) ?? false
          return (
            <li key={role} className="flex items-center justify-between gap-4 rounded-2xl border border-mist px-4 py-3.5">
              <div className="flex items-center gap-3">
                <RoleBadge role={role} />
                <span className={`text-sm font-medium ${enabled ? 'text-navy' : 'text-muted'}`}>
                  {enabled ? t('rolesPage.outboxOn') : t('rolesPage.outboxOff')}
                </span>
              </div>
              <Switch
                checked={enabled}
                busy={busyRole === role}
                disabled={!canManage}
                label={`${t('rolesPage.outboxTitle')}: ${t(`roleNames.${role}`)}`}
                onChange={(next) => void toggle(role, next)}
              />
            </li>
          )
        })}
      </ul>
      {!canManage && (
        <p className="mt-4 flex items-center gap-2 text-sm text-muted">
          <LockIcon className="size-4" />
          {t('rolesPage.outboxReadOnly')}
        </p>
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

function MatrixCard({ data }: { data: Data }) {
  const { t } = useTranslation()
  const groups = useMemo(() => groupPermissions(data.permissions), [data.permissions])
  const optional = (role: string, code: string) =>
    code === OUTBOX_PERMISSION && (OUTBOX_OPTIONAL_ROLES as readonly string[]).includes(role)

  return (
    // Edge-to-edge card so the table can scroll sideways; text keeps the card padding.
    <Card delay={0.15} className="px-0">
      <h2 id="permission-matrix" className="mb-2 px-6 font-display text-lg font-semibold text-navy">
        {t('rolesPage.matrixTitle')}
      </h2>
      <p className="mb-4 px-6 text-xs text-muted lg:hidden">{t('rolesPage.scrollHint')}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] border-separate border-spacing-0 text-sm">
          <caption className="sr-only">{t('rolesPage.matrixTitle')}</caption>
          <thead>
            <tr>
              <th rowSpan={2} scope="col" className="sticky left-0 z-20 bg-white px-6 pb-3 text-left align-bottom font-medium text-muted">
                {t('rolesPage.permission')}
              </th>
              {ROLE_GROUPS.map((group) => (
                <th
                  key={group.key}
                  colSpan={group.roles.length}
                  scope="colgroup"
                  className="border-b border-mist px-2 pb-2 text-center font-display text-[11px] font-medium tracking-[0.2em] text-muted uppercase"
                >
                  {t(`roleGroups.${group.key}`)}
                </th>
              ))}
            </tr>
            <tr>
              {ALL_ROLES.map((role) => (
                <th key={role} scope="col" className="w-24 px-2 pt-2 pb-3 text-center text-xs font-semibold text-navy">
                  {t(`roleNames.${role}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map(([group, permissions]) => (
              <Fragment key={group}>
                <tr>
                  <th
                    colSpan={ALL_ROLES.length + 1}
                    scope="colgroup"
                    className="sticky left-0 bg-paper px-6 py-2 text-left font-display text-xs font-semibold tracking-wide text-navy"
                  >
                    {t(`permissionGroups.${group}`, { defaultValue: group })}
                  </th>
                </tr>
                {permissions.map((permission) => (
                  <tr key={permission.code} className="group">
                    <th
                      scope="row"
                      className="sticky left-0 z-10 border-b border-mist/70 bg-white px-6 py-3 text-left font-normal group-hover:bg-paper"
                    >
                      <span className="block text-navy">{t(`permissionNames.${permission.code}`, { defaultValue: permission.name })}</span>
                      <code className="text-[11px] text-muted">{permission.code}</code>
                    </th>
                    {ALL_ROLES.map((role) => {
                      const granted = data.grants[role]?.has(permission.code) ?? false
                      return (
                        <td key={role} className="border-b border-mist/70 px-2 py-3 text-center group-hover:bg-paper">
                          {granted ? (
                            <span
                              className="mx-auto grid size-6 place-items-center rounded-full bg-gold/15 text-gold"
                              title={t('rolesPage.granted')}
                            >
                              <TickIcon className="size-4" strokeWidth={2.5} />
                              <span className="sr-only">{t('rolesPage.granted')}</span>
                            </span>
                          ) : (
                            <span className="mx-auto block h-px w-3 bg-mist" title={t('rolesPage.notGranted')}>
                              <span className="sr-only">{t('rolesPage.notGranted')}</span>
                            </span>
                          )}
                          {optional(role, permission.code) && (
                            <span className="mt-1 block text-[10px] font-medium text-muted">{t('rolesPage.optional')}</span>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function MatrixSkeleton() {
  return (
    <div className="space-y-6" aria-hidden="true">
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((tile) => (
          <div key={tile} className="h-[88px] animate-pulse rounded-2xl bg-white ring-1 ring-mist" />
        ))}
      </div>
      {[0, 1].map((card) => (
        <div key={card} className="rounded-2xl bg-white p-6 ring-1 ring-mist">
          <div className="h-5 w-48 animate-pulse rounded-full bg-mist" />
          <div className="mt-6 space-y-3">
            {Array.from({ length: card === 0 ? 2 : 6 }, (_, row) => (
              <div key={row} className="h-10 animate-pulse rounded-xl bg-paper" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
