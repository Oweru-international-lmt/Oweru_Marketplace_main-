import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/useAuth'
import { Card } from '../components/Card'
import { PageBody, PageHero } from '../components/PageHero'
import { RoleBadge } from '../components/RoleBadge'
import { isLanguage } from '../i18n'
import { formatPhone } from '../lib/phone'

// ACC-08 (edit profile, request deletion) has no endpoint yet, so this page is read-only.
export function AccountPage() {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  const list = useRef<HTMLDListElement>(null)

  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.from('[data-row]', { y: 14, opacity: 0, duration: 0.5, stagger: 0.07, ease: 'power3.out', delay: 0.3 })
      })
    },
    { scope: list },
  )

  if (!user) return null

  const firstName = user.full_name.split(' ')[0] || user.full_name
  const memberSince = new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', {
    dateStyle: 'long',
  }).format(new Date(user.created_at))

  const rows: { label: string; value: ReactNode }[] = [
    { label: t('fields.fullName'), value: user.full_name },
    { label: t('fields.email'), value: user.email },
    { label: t('fields.phone'), value: formatPhone(user.phone) },
    {
      label: t('account.roles'),
      value: user.roles.length ? (
        <span className="flex flex-wrap gap-2">
          {user.roles.map((role) => (
            <RoleBadge key={role} role={role} />
          ))}
        </span>
      ) : (
        <span className="text-muted">{t('account.noRoles')}</span>
      ),
    },
    { label: t('fields.language'), value: isLanguage(user.language) ? t(`common.languageNames.${user.language}`) : user.language },
    { label: t('account.memberSince'), value: memberSince },
  ]

  return (
    <>
      <PageHero
        kicker={t('account.title')}
        title={t('account.greeting', { name: firstName })}
        intro={t('account.intro')}
        documentTitle={t('account.title')}
      />
      <PageBody>
        <Card title={t('account.details')} titleId="account-details" className="sm:p-10">
          <dl ref={list} className="divide-y divide-mist">
            {rows.map((row) => (
              <div key={row.label} data-row className="grid gap-1 py-4 sm:grid-cols-[220px_1fr] sm:gap-6">
                <dt className="text-sm text-muted">{row.label}</dt>
                <dd className="text-[15px] font-medium break-words text-navy">{row.value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </PageBody>
    </>
  )
}
