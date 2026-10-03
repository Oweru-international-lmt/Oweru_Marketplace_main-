import { motion } from 'motion/react'
import type { ComponentType, SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { can } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import { LogOutIcon, ShieldIcon, UserIcon, UsersIcon } from '../components/icons'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { Logo } from '../components/Logo'

type NavItem = {
  to: string
  labelKey: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  permission?: string
}

// Links appear only for people whose permissions allow the page.
const NAV: NavItem[] = [
  { to: '/account', labelKey: 'nav.account', icon: UserIcon },
  { to: '/management/roles', labelKey: 'nav.roles', icon: ShieldIcon, permission: 'authorization.view' },
  { to: '/management/staff', labelKey: 'nav.staff', icon: UsersIcon, permission: 'authorization.view' },
]

// Shell for signed-in pages: navy header, role-aware navigation, page content below.
export function AppLayout() {
  const { t } = useTranslation()
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const items = NAV.filter((item) => !item.permission || can(user, item.permission))

  function handleSignOut() {
    signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-dvh bg-paper">
      <header className="bg-navy">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-5 py-5 sm:px-8">
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

        {items.length > 1 && (
          <nav aria-label={t('nav.main')} className="mx-auto max-w-6xl px-5 sm:px-8">
            <ul className="-mb-px flex gap-1 overflow-x-auto border-b border-white/10 [scrollbar-width:none]">
              {items.map(({ to, labelKey, icon: Icon }) => (
                <li key={to} className="shrink-0">
                  <NavLink
                    to={to}
                    className={({ isActive }) =>
                      `relative flex items-center gap-2 px-3 py-3 text-sm font-medium transition-colors sm:px-4 ${
                        isActive ? 'text-white' : 'text-white/60 hover:text-white'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon className="size-4" />
                        {t(labelKey)}
                        {isActive && (
                          <motion.span
                            layoutId="nav-underline"
                            className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-gold sm:inset-x-4"
                            transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                          />
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>

      <Outlet />
    </div>
  )
}
