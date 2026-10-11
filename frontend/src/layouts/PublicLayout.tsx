import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { CloseIcon, MenuIcon, WhatsAppIcon } from '../components/icons'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { Logo } from '../components/Logo'
import { whatsappLink } from '../lib/config'

// Shell for the public marketplace: home, search and property pages.
export function PublicLayout() {
  const { t } = useTranslation()
  const { pathname, hash } = useLocation()
  // The home hero runs under the header, which stays clear until the page scrolls.
  const overHero = pathname === '/'
  const [scrolled, setScrolled] = useState(() => window.scrollY > 24)
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)

  // A plain listener, not a ScrollTrigger: the page grows as listings load, and
  // a trigger's "end" measured before that would switch the header back mid-page.
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', update, { passive: true })
    return () => window.removeEventListener('scroll', update)
  }, [pathname])

  // A new page starts at the top; "/#how" style links scroll to their section.
  useEffect(() => {
    const target = hash ? document.getElementById(hash.slice(1)) : null
    if (target) target.scrollIntoView({ behavior: 'smooth' })
    else window.scrollTo(0, 0)
  }, [pathname, hash])

  const clear = overHero && !scrolled && !menuOpen

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-gold px-4 py-2 font-semibold text-navy focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        {t('site.skip')}
      </a>

      <header
        className={`fixed inset-x-0 top-0 z-40 transition-[background-color,box-shadow,border-color] duration-300 ${
          clear ? 'border-b border-transparent bg-transparent' : 'border-b border-mist bg-paper/90 shadow-[0_1px_0_rgba(15,23,42,0.02)] backdrop-blur-md'
        }`}
      >
        <div className="mx-auto flex h-18 max-w-7xl items-center justify-between gap-4 px-4 sm:px-8">
          <Logo compact />
          <nav aria-label={t('nav.main')} className="hidden items-center gap-1 md:flex">
            <HeaderLink to="/listings">{t('site.browse')}</HeaderLink>
            <HeaderLink to="/#how">{t('site.howItWorks')}</HeaderLink>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="hidden sm:block">
              <LanguageSwitch />
            </div>
            <div className="hidden md:block">
              <AccountActions />
            </div>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-controls="site-menu"
              aria-label={menuOpen ? t('site.closeMenu') : t('site.openMenu')}
              className="grid size-11 place-items-center rounded-xl text-navy ring-1 ring-mist hover:bg-white md:hidden"
            >
              {menuOpen ? <CloseIcon className="size-5" /> : <MenuIcon className="size-5" />}
            </button>
          </div>
        </div>

        <AnimatePresence>
          {menuOpen && (
            <motion.nav
              id="site-menu"
              aria-label={t('nav.main')}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden border-t border-mist bg-paper md:hidden"
            >
              <div className="space-y-1 px-4 pt-3 pb-5" onClick={(event) => (event.target as HTMLElement).closest('a') && closeMenu()}>
                <MenuLink to="/listings">{t('site.browse')}</MenuLink>
                <MenuLink to="/#how">{t('site.howItWorks')}</MenuLink>
                <div className="flex items-center justify-between gap-3 pt-4">
                  <LanguageSwitch />
                  <AccountActions />
                </div>
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main id="main" className={`flex-1 ${overHero ? '' : 'pt-18'}`}>
        <Outlet />
      </main>

      <SiteFooter />
    </div>
  )
}

function HeaderLink({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `relative rounded-md px-4 py-2 text-sm font-medium transition-colors ${isActive ? 'text-navy' : 'text-navy/75 hover:text-navy'}`
      }
    >
      {({ isActive }) => (
        <>
          {children}
          {isActive && !to.includes('#') && (
            <motion.span layoutId="site-nav-underline" className="absolute inset-x-3 -bottom-0.5 h-0.5 rounded-full bg-gold" />
          )}
        </>
      )}
    </NavLink>
  )
}

function MenuLink({ to, children }: { to: string; children: string }) {
  return (
    <Link to={to} className="flex h-12 items-center rounded-xl px-3 text-[15px] font-medium text-navy hover:bg-white">
      {children}
    </Link>
  )
}

function AccountActions() {
  const { t } = useTranslation()
  const { status } = useAuth()
  const { pathname } = useLocation()

  if (status === 'authenticated') {
    return (
      <Link to="/account" className="inline-flex h-11 items-center rounded-md bg-navy px-5 text-sm font-semibold text-white hover:bg-navy-soft">
        {t('site.myAccount')}
      </Link>
    )
  }
  return (
    <div className="flex items-center gap-2">
      <Link
        to="/login"
        state={{ from: pathname }}
        className="inline-flex h-11 items-center rounded-md px-3 text-sm font-semibold text-navy hover:bg-white"
      >
        {t('site.signIn')}
      </Link>
      <Link to="/register" className="inline-flex h-11 items-center rounded-md bg-navy px-5 text-sm font-semibold text-white hover:bg-navy-soft">
        {t('site.register')}
      </Link>
    </div>
  )
}

// Read once at load; a page left open over New Year shows last year until reload.
const YEAR = new Date().getFullYear()

function SiteFooter() {
  const { t } = useTranslation()

  return (
    <footer className="bg-navy text-white/75">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-8 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
        <div className="max-w-sm">
          <Logo tone="light" />
          <p className="mt-5 text-sm leading-relaxed">{t('site.tagline')}</p>
        </div>
        <FooterColumn title={t('site.footerExplore')}>
          <FooterLink to="/listings">{t('site.browse')}</FooterLink>
          <FooterLink to="/#how">{t('site.howItWorks')}</FooterLink>
        </FooterColumn>
        <FooterColumn title={t('site.footerAccount')}>
          <FooterLink to="/login">{t('site.signIn')}</FooterLink>
          <FooterLink to="/register">{t('site.register')}</FooterLink>
        </FooterColumn>
        <FooterColumn title={t('site.footerHelp')}>
          <a
            href={whatsappLink(t('site.supportMessage'))}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm text-white/85 hover:text-gold-light"
          >
            <WhatsAppIcon className="size-4" />
            {t('site.support')}
          </a>
        </FooterColumn>
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-7xl px-4 py-5 text-xs text-white/55 sm:px-8">{t('site.rights', { year: YEAR })}</p>
      </div>
    </footer>
  )
}

function FooterColumn({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="font-display text-xs font-semibold tracking-[0.25em] text-gold-light uppercase">{title}</p>
      <div className="mt-4 flex flex-col items-start gap-3">{children}</div>
    </div>
  )
}

function FooterLink({ to, children }: { to: string; children: string }) {
  return (
    <Link to={to} className="text-sm text-white/85 hover:text-gold-light">
      {children}
    </Link>
  )
}
