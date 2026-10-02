import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { motion } from 'motion/react'
import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { LogOutIcon } from '../components/icons'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { Logo } from '../components/Logo'
import { isLanguage } from '../i18n'
import { formatPhone } from '../lib/phone'

// ACC-08 (edit profile, request deletion) has no endpoint yet, so this page is read-only.
export function AccountPage() {
  const { t, i18n } = useTranslation()
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const root = useRef<HTMLDivElement>(null)
  useDocumentTitle(t('account.title'))

  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap
          .timeline({ defaults: { ease: 'power3.out' } })
          .from('[data-hero]', { y: 24, opacity: 0, duration: 0.7, stagger: 0.08 })
          .from('[data-rule]', { scaleX: 0, duration: 0.6, ease: 'power2.inOut' }, '<0.2')
          .from('[data-row]', { y: 14, opacity: 0, duration: 0.5, stagger: 0.07 }, '<0.1')
      })
    },
    { scope: root },
  )

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

  function handleSignOut() {
    signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div ref={root} className="min-h-dvh bg-paper">
      <header className="bg-navy">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-5 py-5 sm:px-8">
          <Logo tone="light" to="/account" compact />
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <LanguageSwitch tone="light" />
            <button
              type="button"
              onClick={handleSignOut}
              title={t('account.signOut')}
              className="inline-flex h-10 min-w-10 shrink-0 items-center justify-center gap-2 rounded-full px-2.5 text-sm font-medium text-white/85 ring-1 ring-white/20 transition-colors hover:bg-white/10 hover:text-white sm:px-4"
            >
              <LogOutIcon className="size-4" />
              <span className="sr-only sm:not-sr-only">{t('account.signOut')}</span>
            </button>
          </div>
        </div>

        <div className="mx-auto max-w-5xl px-5 pt-8 pb-28 sm:px-8 sm:pt-12">
          <p data-hero className="font-display text-[11px] font-medium tracking-[0.35em] text-gold-light uppercase">
            {t('account.title')}
          </p>
          <h1 data-hero className="mt-3 font-display text-3xl font-medium text-white sm:text-5xl">
            {t('account.greeting', { name: firstName })}
          </h1>
          <span data-rule className="mt-5 block h-0.5 w-14 origin-left bg-gold" aria-hidden="true" />
          <p data-hero className="mt-5 max-w-lg text-[15px] leading-relaxed text-white/70">
            {t('account.intro')}
          </p>
        </div>
      </header>

      <main className="mx-auto -mt-16 max-w-5xl px-5 pb-16 sm:px-8">
        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
          aria-labelledby="account-details"
          className="rounded-3xl bg-white p-6 shadow-[0_24px_60px_-30px_rgba(15,23,42,0.35)] ring-1 ring-mist sm:p-10"
        >
          <h2 id="account-details" className="font-display text-xl font-semibold text-navy">
            {t('account.details')}
          </h2>
          <dl className="mt-6 divide-y divide-mist">
            {rows.map((row) => (
              <div key={row.label} data-row className="grid gap-1 py-4 sm:grid-cols-[220px_1fr] sm:gap-6">
                <dt className="text-sm text-muted">{row.label}</dt>
                <dd className="text-[15px] font-medium break-words text-navy">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        </motion.section>
      </main>
    </div>
  )
}
