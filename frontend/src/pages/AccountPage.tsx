import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/useAuth'
import { Card } from '../components/Card'
import { ChangePasswordForm } from '../components/ChangePasswordForm'
import { PageHeader } from '../components/PageHeader'
import { RoleBadge } from '../components/RoleBadge'
import { initials } from '../lib/initials'
import { DeletionCard } from './account/DeletionCard'
import { ProfileDetailsCard } from './account/ProfileDetailsCard'
import { VerificationList } from './account/VerificationList'

export function AccountPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  if (!user) return null

  const firstName = user.full_name.split(' ')[0] || user.full_name

  return (
    <>
      <PageHeader
        eyebrow={t('account.title')}
        title={t('account.greeting', { name: firstName })}
        description={t('account.intro')}
        documentTitle={t('account.title')}
      />

      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card>
            <div className="flex flex-col items-center text-center">
              <span className="grid size-20 place-items-center rounded-3xl bg-navy font-display text-2xl font-semibold text-gold-light">
                {initials(user.full_name)}
              </span>
              <p className="mt-4 font-display text-xl font-semibold text-navy">{user.full_name}</p>
              <p className="mt-1 max-w-full truncate text-sm text-muted">{user.email}</p>
            </div>
            {/* Only staff roles are known to the UI for now (see loadAccess). */}
            {user.roles.length > 0 && (
              <div className="mt-6 border-t border-mist pt-5">
                <p className="text-xs font-medium tracking-wide text-muted uppercase">{t('account.roles')}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {user.roles.map((role) => (
                    <RoleBadge key={role} role={role} />
                  ))}
                </div>
              </div>
            )}
            <div className="mt-6 border-t border-mist pt-5">
              <p className="mb-4 text-xs font-medium tracking-wide text-muted uppercase">{t('profile.verification')}</p>
              <VerificationList user={user} />
            </div>
          </Card>
        </div>

        <div className="min-w-0 space-y-6">
          <ProfileDetailsCard user={user} />
          <Card title={t('security.title')} titleId="account-security" description={t('security.description')} delay={0.15}>
            <ChangePasswordForm submitLabel={t('security.submit')} />
          </Card>
          <DeletionCard />
        </div>
      </div>
    </>
  )
}
