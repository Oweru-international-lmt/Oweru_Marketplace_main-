import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { CloseIcon, LogOutIcon, SidebarIcon, WhatsAppIcon } from '../components/icons'
import { Logo } from '../components/Logo'
import { whatsappLink } from '../lib/config'
import { visibleGroups } from './navigation'

type SidebarProps = {
  collapsed?: boolean
  // Kept for the desktop sidebar and the phone drawer, which share this panel.
  variant: 'desktop' | 'drawer'
  onNavigate?: () => void
  onToggleCollapse?: () => void
  onClose?: () => void
  onSignOut: () => void
}

// After W1: a darker block holding the logo, flat rows with small icons, the
// current page as one solid full-width bar, and a small-caps "Support" list
// of plain links at the bottom.
export function Sidebar({ collapsed = false, onNavigate, onToggleCollapse, onClose, onSignOut }: SidebarProps) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const groups = visibleGroups(user)
  const paths = groups.flatMap((group) => group.items.map((item) => item.to))

  return (
    <div className="flex h-full w-full flex-col bg-navy text-white">
      <div className={`flex h-[92px] shrink-0 items-center bg-[#0a101d] ${collapsed ? 'justify-center px-3' : 'justify-between px-5'}`}>
        <Logo tone="light" to={paths[0] ?? '/account'} iconOnly={collapsed} />
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label={t('nav.closeMenu')}
            className="grid size-10 place-items-center text-white/70 hover:bg-white/10 hover:text-white"
          >
            <CloseIcon className="size-5" />
          </button>
        )}
      </div>

      <nav aria-label={t('nav.main')} className="flex-1 overflow-y-auto pt-4 pb-6">
        {groups.map((group, index) => (
          <div key={group.titleKey} className={index > 0 ? 'mt-5' : ''}>
            {collapsed ? (
              index > 0 && <div className="mx-auto mb-3 h-px w-8 bg-white/10" aria-hidden="true" />
            ) : (
              <p className="mb-1.5 px-5 text-[10px] font-semibold tracking-[0.16em] text-white/40 uppercase">{t(group.titleKey)}</p>
            )}
            <ul>
              {group.items.map(({ to, labelKey, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    // A path that is also the start of another item only matches itself.
                    end={paths.some((other) => other !== to && other.startsWith(`${to}/`))}
                    onClick={onNavigate}
                    title={collapsed ? t(labelKey) : undefined}
                    className={({ isActive }) =>
                      `flex items-center gap-3 py-2.5 text-[13px] transition-colors ${collapsed ? 'justify-center px-0' : 'px-5'} ${
                        isActive ? 'bg-gold font-semibold text-navy' : 'text-white/70 hover:bg-white/[0.06] hover:text-white'
                      }`
                    }
                  >
                    <Icon className="size-[18px] shrink-0" />
                    <span className={collapsed ? 'sr-only' : 'truncate'}>{t(labelKey)}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className={`shrink-0 pb-5 ${collapsed ? 'space-y-1 px-2' : 'px-5'}`}>
        {!collapsed && <p className="mb-2 text-[10px] font-semibold tracking-[0.16em] text-white/40 uppercase">{t('nav.support')}</p>}
        <ul className={collapsed ? 'space-y-1' : 'space-y-1.5'}>
          <li>
            <a
              href={whatsappLink(t('nav.helpMessage'))}
              target="_blank"
              rel="noopener noreferrer"
              title={collapsed ? t('nav.helpAction') : undefined}
              className={`flex items-center gap-2.5 text-[12px] text-white/65 hover:text-white ${collapsed ? 'justify-center py-2.5' : 'py-1'}`}
            >
              <WhatsAppIcon className={collapsed ? 'size-5' : 'size-3.5'} />
              <span className={collapsed ? 'sr-only' : ''}>{t('nav.helpAction')}</span>
            </a>
          </li>
          {onToggleCollapse && (
            <li>
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-label={collapsed ? t('nav.expand') : t('nav.collapse')}
                aria-expanded={!collapsed}
                className={`flex w-full items-center gap-2.5 text-[12px] text-white/65 hover:text-white ${collapsed ? 'justify-center py-2.5' : 'py-1'}`}
              >
                <SidebarIcon className={collapsed ? 'size-5' : 'size-3.5'} />
                {!collapsed && t('nav.collapse')}
              </button>
            </li>
          )}
          <li>
            <button
              type="button"
              onClick={onSignOut}
              title={collapsed ? t('account.signOut') : undefined}
              className={`flex w-full items-center gap-2.5 text-[12px] text-white/65 hover:text-white ${collapsed ? 'justify-center py-2.5' : 'py-1'}`}
            >
              <LogOutIcon className={collapsed ? 'size-5' : 'size-3.5'} />
              <span className={collapsed ? 'sr-only' : ''}>{t('account.signOut')}</span>
            </button>
          </li>
        </ul>
      </div>
    </div>
  )
}
