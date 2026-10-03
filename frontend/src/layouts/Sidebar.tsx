import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { CloseIcon, LogOutIcon, SidebarIcon, WhatsAppIcon } from '../components/icons'
import { Logo } from '../components/Logo'
import { whatsappLink } from '../lib/config'
import { visibleGroups } from './navigation'

type SidebarProps = {
  collapsed?: boolean
  // Distinguishes the desktop sidebar from the mobile drawer so their
  // active-item highlights animate independently.
  variant: 'desktop' | 'drawer'
  onNavigate?: () => void
  onToggleCollapse?: () => void
  onClose?: () => void
  onSignOut: () => void
}

export function Sidebar({ collapsed = false, variant, onNavigate, onToggleCollapse, onClose, onSignOut }: SidebarProps) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const groups = visibleGroups(user)

  return (
    <div className="flex h-full w-full flex-col bg-navy text-white">
      <div className={`flex h-20 shrink-0 items-center ${collapsed ? 'justify-center px-3' : 'justify-between px-5'}`}>
        <Logo tone="light" to="/account" iconOnly={collapsed} />
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label={t('nav.closeMenu')}
            className="grid size-10 place-items-center rounded-xl text-white/70 hover:bg-white/10 hover:text-white"
          >
            <CloseIcon className="size-5" />
          </button>
        )}
      </div>

      <nav aria-label={t('nav.main')} className="flex-1 overflow-y-auto px-3 pt-2 pb-6">
        {groups.map((group, index) => (
          <div key={group.titleKey} className={index > 0 ? 'mt-6' : ''}>
            {collapsed ? (
              index > 0 && <div className="mx-auto mb-3 h-px w-8 bg-white/10" aria-hidden="true" />
            ) : (
              <p className="mb-2 px-3 font-display text-[11px] font-medium tracking-[0.25em] text-white/40 uppercase">
                {t(group.titleKey)}
              </p>
            )}
            <ul className="space-y-1">
              {group.items.map(({ to, labelKey, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    onClick={onNavigate}
                    title={collapsed ? t(labelKey) : undefined}
                    className={({ isActive }) =>
                      `group relative flex items-center gap-3 rounded-xl py-2.5 text-sm font-medium transition-colors ${
                        collapsed ? 'justify-center px-0' : 'px-3'
                      } ${isActive ? 'text-white' : 'text-white/60 hover:bg-white/5 hover:text-white'}`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <motion.span
                            layoutId={`sidebar-active-${variant}`}
                            className="absolute inset-0 rounded-xl bg-white/10"
                            transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                          >
                            <span className="absolute inset-y-2 left-0 w-1 rounded-full bg-gold" />
                          </motion.span>
                        )}
                        <Icon className={`relative size-5 shrink-0 ${isActive ? 'text-gold-light' : ''}`} />
                        <span className={collapsed ? 'sr-only' : 'relative truncate'}>{t(labelKey)}</span>
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 space-y-2 border-t border-white/10 p-3">
        {collapsed ? (
          <a
            href={whatsappLink(t('nav.helpMessage'))}
            target="_blank"
            rel="noopener noreferrer"
            title={t('nav.helpTitle')}
            className="mx-auto grid size-11 place-items-center rounded-xl text-white/70 hover:bg-white/10 hover:text-white"
          >
            <WhatsAppIcon className="size-5" />
            <span className="sr-only">{t('nav.helpAction')}</span>
          </a>
        ) : (
          <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
            <p className="font-display text-sm font-semibold">{t('nav.helpTitle')}</p>
            <p className="mt-1 text-xs leading-relaxed text-white/60">{t('nav.helpBody')}</p>
            <a
              href={whatsappLink(t('nav.helpMessage'))}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-2 rounded-lg bg-gold px-3 py-2 text-xs font-semibold text-navy hover:bg-gold-light"
            >
              <WhatsAppIcon className="size-4" />
              {t('nav.helpAction')}
            </a>
          </div>
        )}

        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? t('nav.expand') : t('nav.collapse')}
            aria-expanded={!collapsed}
            title={collapsed ? t('nav.expand') : undefined}
            className={`flex w-full items-center gap-3 rounded-xl py-2.5 text-sm font-medium text-white/60 hover:bg-white/5 hover:text-white ${
              collapsed ? 'justify-center' : 'px-3'
            }`}
          >
            <SidebarIcon className="size-5 shrink-0" />
            {!collapsed && t('nav.collapse')}
          </button>
        )}

        <button
          type="button"
          onClick={onSignOut}
          title={collapsed ? t('account.signOut') : undefined}
          className={`flex w-full items-center gap-3 rounded-xl py-2.5 text-sm font-medium text-white/60 hover:bg-white/5 hover:text-white ${
            collapsed ? 'justify-center' : 'px-3'
          }`}
        >
          <LogOutIcon className="size-5 shrink-0" />
          <span className={collapsed ? 'sr-only' : ''}>{t('account.signOut')}</span>
        </button>
      </div>
    </div>
  )
}
