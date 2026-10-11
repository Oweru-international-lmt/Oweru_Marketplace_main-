import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { ChevronRightIcon, MenuIcon } from '../components/icons'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { Logo } from '../components/Logo'
import { UserMenu } from '../components/UserMenu'
import { findNavItem } from './navigation'
import { Sidebar } from './Sidebar'

const COLLAPSE_KEY = 'oweru.sidebar.collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

// Shell for signed-in pages: navy sidebar (collapsible on desktop, a drawer on
// phones), a light top bar with breadcrumb and user menu, and the page content.
export function AppLayout() {
  const { signOut } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  function toggleCollapsed() {
    setCollapsed((value) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, value ? '0' : '1')
      } catch {
        // The choice just won't survive a reload.
      }
      return !value
    })
  }

  function handleSignOut() {
    setDrawerOpen(false)
    signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-dvh bg-paper">
      <aside
        className={`fixed inset-y-0 left-0 z-30 hidden transition-[width] duration-300 ease-out lg:flex ${
          collapsed ? 'w-20' : 'w-72'
        }`}
      >
        <Sidebar variant="desktop" collapsed={collapsed} onToggleCollapse={toggleCollapsed} onSignOut={handleSignOut} />
      </aside>

      <AnimatePresence>
        {drawerOpen && <MobileDrawer onClose={closeDrawer} onSignOut={handleSignOut} />}
      </AnimatePresence>

      <div className={`transition-[padding] duration-300 ease-out ${collapsed ? 'lg:pl-20' : 'lg:pl-72'}`}>
        <TopBar onOpenMenu={() => setDrawerOpen(true)} onSignOut={handleSignOut} />
        <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8 lg:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function TopBar({ onOpenMenu, onSignOut }: { onOpenMenu: () => void; onSignOut: () => void }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const current = findNavItem(pathname)

  return (
    <header className="sticky top-0 z-20 border-b border-mist bg-paper/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-5 sm:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onOpenMenu}
            aria-label={t('nav.openMenu')}
            className="grid size-10 shrink-0 place-items-center rounded-xl text-navy ring-1 ring-mist hover:bg-white lg:hidden"
          >
            <MenuIcon className="size-5" />
          </button>
          <span className="lg:hidden">
            <Logo to="/account" iconOnly />
          </span>
          {current && (
            <nav aria-label={t('nav.breadcrumb')} className="hidden min-w-0 items-center gap-2 text-sm sm:flex">
              <span className="text-muted">{t(current.group.titleKey)}</span>
              <ChevronRightIcon className="size-4 shrink-0 text-muted/60" />
              <span aria-current="page" className="truncate font-medium text-navy">
                {t(current.item.labelKey)}
              </span>
            </nav>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <LanguageSwitch />
          <UserMenu onSignOut={onSignOut} />
        </div>
      </div>
    </header>
  )
}

function MobileDrawer({ onClose, onSignOut }: { onClose: () => void; onSignOut: () => void }) {
  const { t } = useTranslation()
  const panel = useRef<HTMLDivElement>(null)

  // Escape closes, the page behind cannot scroll, and focus moves into the drawer.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    const previousOverflow = document.body.style.overflow
    const previousFocus = document.activeElement as HTMLElement | null
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKey)
    panel.current?.querySelector<HTMLElement>('a, button')?.focus()
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKey)
      previousFocus?.focus()
    }
  }, [onClose])

  return (
    <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label={t('nav.main')}>
      <motion.div
        className="absolute inset-0 bg-navy/60 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        ref={panel}
        className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] shadow-2xl"
        initial={{ x: '-100%' }}
        animate={{ x: 0 }}
        exit={{ x: '-100%' }}
        transition={{ type: 'spring', stiffness: 400, damping: 40 }}
      >
        <Sidebar variant="drawer" onNavigate={onClose} onClose={onClose} onSignOut={onSignOut} />
      </motion.div>
    </div>
  )
}
