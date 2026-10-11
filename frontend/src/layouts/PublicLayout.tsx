import { motion } from 'motion/react'
import { useEffect, useState, type ComponentType, type ReactNode, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { HomeIcon, SearchIcon, ShieldIcon, UserIcon, WhatsAppIcon } from '../components/icons'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { Logo } from '../components/Logo'
import { whatsappLink } from '../lib/config'
import { DESKTOP, useMediaQuery } from '../lib/useMediaQuery'

// Shell for the public marketplace: home, search and property pages. Phones
// get a bottom bar instead of a menu; the property page swaps it for its own
// price and action bar.
export function PublicLayout() {
  const { t } = useTranslation()
  const { pathname, hash } = useLocation()
  // The home hero runs under the header, which stays clear until the page scrolls.
  const overHero = pathname === '/'
  // The property page has its own fixed price bar (not its full check sub-page).
  const onListing = /^\/listings\/[^/]+\/?$/.test(pathname)
  // The free check's phone flow is a full-screen map with its own sheet (S2).
  const onFreeCheck = pathname === '/free-check'
  const [scrolled, setScrolled] = useState(() => window.scrollY > 24)

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

  const clear = overHero && !scrolled
  // On phones the home hero is a dark band (M1), so the clear header uses light text.
  const desktop = useMediaQuery(DESKTOP)
  const light = clear && !desktop

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
          <Logo compact tone={light ? 'light' : 'dark'} />
          <nav aria-label={t('nav.main')} className="hidden items-center gap-1 md:flex">
            <HeaderLink to="/listings">{t('site.browse')}</HeaderLink>
            <HeaderLink to="/free-check">{t('site.freeCheck')}</HeaderLink>
            <HeaderLink to="/#how">{t('site.howItWorks')}</HeaderLink>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            <LanguageSwitch tone={light ? 'light' : 'dark'} />
            <div className="hidden md:block">
              <AccountActions />
            </div>
          </div>
        </div>
      </header>

      <main id="main" className={`flex-1 ${overHero ? '' : 'pt-18'}`}>
        <Outlet />
      </main>

      <SiteFooter />
      {/* Room for the fixed phone bars, so the footer's last line isn't covered. */}
      {!onFreeCheck && <div aria-hidden="true" className={onListing ? 'h-24 lg:hidden' : 'h-24 md:hidden'} />}
      {!onListing && !onFreeCheck && <BottomNav />}
    </div>
  )
}

type Tab = { to: string; label: string; icon: ComponentType<SVGProps<SVGSVGElement>>; active: boolean; external?: boolean }

// The M3 reference's floating dark bar, within thumb reach on phones.
function BottomNav() {
  const { t } = useTranslation()
  const { status } = useAuth()
  const { pathname } = useLocation()
  const signedIn = status === 'authenticated'

  const tabs: Tab[] = [
    { to: '/', label: t('site.home'), icon: HomeIcon, active: pathname === '/' },
    { to: '/listings', label: t('site.search'), icon: SearchIcon, active: pathname === '/listings' },
    { to: '/free-check', label: t('site.freeCheckTab'), icon: ShieldIcon, active: pathname.startsWith('/free-check') },
    { to: whatsappLink(t('site.supportMessage')), label: t('site.help'), icon: WhatsAppIcon, active: false, external: true },
    { to: signedIn ? '/account' : '/login', label: signedIn ? t('site.account') : t('site.signIn'), icon: UserIcon, active: false },
  ]

  return (
    <nav
      aria-label={t('site.bottomNav')}
      className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-40 rounded-2xl bg-navy/95 px-2 py-1.5 shadow-[0_18px_40px_-12px_rgba(15,23,42,0.6)] backdrop-blur md:hidden"
    >
      <ul className="grid grid-cols-5">
        {tabs.map((tab) => {
          const content = (
            <>
              {tab.active && (
                <motion.span
                  layoutId="bottom-nav-active"
                  className="absolute inset-x-2 inset-y-0.5 rounded-xl bg-white/10"
                  transition={{ type: 'spring', stiffness: 500, damping: 38 }}
                />
              )}
              <tab.icon className="relative size-5" />
              <span className="relative text-[11px] font-medium">{tab.label}</span>
            </>
          )
          const className = `relative flex h-14 flex-col items-center justify-center gap-1 ${tab.active ? 'text-gold-light' : 'text-white/70'}`
          return (
            <li key={tab.label}>
              {tab.external ? (
                <a href={tab.to} target="_blank" rel="noopener noreferrer" className={className}>
                  {content}
                </a>
              ) : (
                <Link to={tab.to} aria-current={tab.active ? 'page' : undefined} className={className}>
                  {content}
                </Link>
              )}
            </li>
          )
        })}
      </ul>
    </nav>
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
          <FooterLink to="/free-check">{t('site.freeCheck')}</FooterLink>
          <FooterLink to="/#how">{t('site.howItWorks')}</FooterLink>
        </FooterColumn>
        <FooterColumn title={t('site.footerAccount')}>
          <FooterLink to="/login">{t('site.signIn')}</FooterLink>
          <FooterLink to="/register">{t('site.register')}</FooterLink>
          <FooterLink to="/full-checks">{t('site.myFullChecks')}</FooterLink>
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
          <FooterLink to="/complaints/new">{t('site.complaint')}</FooterLink>
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
