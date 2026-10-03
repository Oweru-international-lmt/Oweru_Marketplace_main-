import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/useAuth'
import { Card } from '../components/Card'
import { PageHeader } from '../components/PageHeader'
import { RoleBadge } from '../components/RoleBadge'
import { isLanguage } from '../i18n'
import { initials } from '../lib/initials'
import { formatPhone } from '../lib/phone'

// ACC-08 (edit profile, request deletion) has no endpoint yet, so this page is read-only.
export function AccountPage() {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  if (!user) return null

  const firstName = user.full_name.split(' ')[0] || user.full_name
  const memberSince = new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', {
    dateStyle: 'long',
  }).format(new Date(user.created_at))

  const rows = [
    { label: t('fields.fullName'), value: user.full_name },
    { label: t('fields.email'), value: user.email },
    { label: t('fields.phone'), value: formatPhone(user.phone) },
    { label: t('fields.language'), value: isLanguage(user.language) ? t(`common.languageNames.${user.language}`) : user.language },
    { label: t('account.memberSince'), value: memberSince },
  ]

  return (
    <>
      <PageHeader
        eyebrow={t('account.title')}
        title={t('account.greeting', { name: firstName })}
        description={t('account.intro')}
        documentTitle={t('account.title')}
      />

      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="self-start">
          <div className="flex flex-col items-center text-center">
            <span className="grid size-20 place-items-center rounded-3xl bg-navy font-display text-2xl font-semibold text-gold-light">
              {initials(user.full_name)}
            </span>
            <p className="mt-4 font-display text-xl font-semibold text-navy">{user.full_name}</p>
            <p className="mt-1 max-w-full truncate text-sm text-muted">{user.email}</p>
            <p className="mt-1 text-xs text-muted">{t(`categories.${user.account_category}`)}</p>
          </div>
          <div className="mt-6 border-t border-mist pt-5">
            <p className="text-xs font-medium tracking-wide text-muted uppercase">{t('account.roles')}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {user.roles.length ? (
                user.roles.map((role) => <RoleBadge key={role} role={role} />)
              ) : (
                <span className="text-sm text-muted">{t('account.noRoles')}</span>
              )}
            </div>
          </div>
        </Card>

        <Card title={t('account.details')} titleId="account-details" delay={0.1}>
          <dl className="divide-y divide-mist">
            {rows.map((row) => (
              <div key={row.label} className="grid gap-1 py-4 first:pt-0 last:pb-0 sm:grid-cols-[200px_1fr] sm:gap-6">
                <dt className="text-sm text-muted">{row.label}</dt>
                <dd className="text-[15px] font-medium break-words text-navy">{row.value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>
    </>
  )
}
