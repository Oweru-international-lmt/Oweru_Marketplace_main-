import { useEffect, useRef, useState, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import coastLarge from '../../assets/photos/dar-coast-1200.webp'
import coastSmall from '../../assets/photos/dar-coast-720.webp'
import sunsetLarge from '../../assets/photos/dar-sunset-1200.webp'
import sunsetSmall from '../../assets/photos/dar-sunset-720.webp'
import { ArrowRightIcon, ChatIcon, MapPinIcon, SearchIcon, ShieldIcon, TickIcon, UserIcon } from '../../components/icons'
import { ListingCard, ListingCardSkeleton } from '../../components/market/ListingCard'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { gsap, MOTION_OK, ScrollTrigger, useGSAP } from '../../lib/gsap'
import { LEVELS, marketApi, type PublicListing } from '../../lib/marketApi'

// Follows the Horizon Realty reference section by section: light hero with a
// serif headline and two buttons, a white strip over the hero's base,
// featured listings, and a dark call-to-action band.
export function HomePage() {
  // Empty title: the tab shows just the brand.
  useDocumentTitle('')

  return (
    <>
      <Hero />
      <LevelStrip />
      <LatestListings />
      <HowItWorks />
      <ListCallToAction />
    </>
  )
}

// Small uppercase label with a short gold rule under it, as in the reference.
function Eyebrow({ children, light = false, rule = false }: { children: string; light?: boolean; rule?: boolean }) {
  return (
    <div data-kicker>
      <p className={`text-xs font-semibold tracking-[0.2em] uppercase ${light ? 'text-gold-light' : rule ? 'text-navy' : 'text-gold'}`}>{children}</p>
      {rule && <span data-rule className="mt-3 block h-0.5 w-12 origin-left bg-gold" aria-hidden="true" />}
    </div>
  )
}

function Hero() {
  const { t } = useTranslation()
  const root = useRef<HTMLElement>(null)
  const lead = t('home.titleLead')
  const words = [
    ...lead.split(' ').map((word) => ({ word, gold: false })),
    ...t('home.titleAccent').split(' ').map((word) => ({ word, gold: true })),
  ]

  useGSAP(
    () => {
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap
          .timeline({ defaults: { ease: 'power3.out' } })
          .from('[data-kicker]', { opacity: 0, y: 10, duration: 0.5 })
          .from('[data-rule]', { scaleX: 0, duration: 0.7, ease: 'power2.inOut' }, '<0.1')
          .from('[data-word]', { yPercent: 110, duration: 0.9, stagger: 0.07 }, '<0.1')
          .from('[data-fade]', { opacity: 0, y: 16, duration: 0.6, stagger: 0.1 }, '-=0.5')
        // The photo drifts slower than the page as the hero scrolls away.
        gsap.to('[data-photo]', {
          yPercent: 8,
          ease: 'none',
          scrollTrigger: { trigger: root.current, start: 'top top', end: 'bottom top', scrub: true },
        })
      })
    },
    { scope: root, dependencies: [lead], revertOnUpdate: true },
  )

  return (
    <section ref={root} className="relative isolate overflow-hidden bg-paper pt-36 pb-44 lg:pt-44 lg:pb-52">
      <img
        data-photo
        src={coastSmall}
        srcSet={`${coastSmall} 720w, ${coastLarge} 1200w`}
        sizes="(min-width: 1024px) 70vw, 100vw"
        alt=""
        fetchPriority="high"
        className="absolute inset-y-0 right-0 -z-20 h-[112%] w-full object-cover [mask-image:linear-gradient(to_bottom,black_60%,transparent_88%)] lg:w-[70%]"
      />
      {/* Paper fades over the photo from the left, so the headline reads like print. */}
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-gradient-to-r from-paper from-30% via-paper/85 via-50% to-paper/0" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 -z-10 h-48 bg-gradient-to-t from-paper via-paper/70 to-transparent" />

      <div className="mx-auto w-full max-w-7xl px-4 sm:px-8">
        <div className="max-w-[680px]">
          <Eyebrow rule>{t('home.kicker')}</Eyebrow>
          <h1 className="mt-7 font-serif text-[44px] leading-[1.08] font-semibold text-navy sm:text-[54px] lg:text-[60px]">
            {words.map(({ word, gold }, index) => (
              <span key={`${word}-${index}`} className="inline-block overflow-hidden pb-1.5 align-bottom">
                <span data-word className={`mr-[0.22em] inline-block ${gold ? 'text-gold' : ''}`}>
                  {word}
                </span>
              </span>
            ))}
          </h1>
          <p data-fade className="mt-6 max-w-md text-base leading-relaxed text-navy/70">
            {t('home.subtitle')}
          </p>
          <div data-fade className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              to="/listings"
              className="inline-flex h-12 items-center rounded-md bg-navy px-7 text-sm font-semibold text-white shadow-[0_10px_24px_-12px_rgba(15,23,42,0.8)] transition-colors hover:bg-navy-soft"
            >
              {t('home.browseAll')}
            </Link>
            <Link
              to="/#how"
              className="group inline-flex h-12 items-center gap-3 rounded-md bg-white/60 pr-3 pl-6 text-sm font-semibold text-navy ring-1 ring-navy/25 backdrop-blur-sm transition-colors hover:bg-white"
            >
              {t('site.howItWorks')}
              <span className="grid size-6 place-items-center rounded-full ring-1 ring-navy/40 transition-transform group-hover:translate-x-0.5">
                <ArrowRightIcon className="size-3.5" />
              </span>
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}

const LEVEL_ICONS = { 0: TickIcon, 1: UserIcon, 2: MapPinIcon, 3: ShieldIcon } as const

// The reference's stats strip, carrying Oweru's own proof: the four levels.
function LevelStrip() {
  const { t } = useTranslation()
  const root = useRef<HTMLElement>(null)

  useGSAP(
    () => {
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap
          .timeline({ delay: 0.55, defaults: { ease: 'power3.out' } })
          .from('[data-strip]', { opacity: 0, y: 30, duration: 0.7 })
          .from('[data-level]', { opacity: 0, y: 12, duration: 0.5, stagger: 0.09 }, '-=0.35')
      })
    },
    { scope: root },
  )

  return (
    <section ref={root} aria-labelledby="levels-title" className="relative z-10 mx-auto -mt-32 max-w-7xl px-4 sm:px-8 lg:-mt-36">
      <div data-strip className="rounded-xl bg-white px-2 py-3 shadow-lift">
        <h2 id="levels-title" className="sr-only">
          {t('home.stripLabel')}
        </h2>
        <ol className="grid divide-y divide-mist sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4 lg:divide-x">
          {LEVELS.map((level) => {
            const Icon = LEVEL_ICONS[level]
            return (
              <li key={level} data-level className="flex items-start gap-4 px-6 py-6">
                <span
                  className={`grid size-12 shrink-0 place-items-center rounded-full ${
                    level === 3 ? 'bg-gold text-white' : 'bg-gold/10 text-gold'
                  }`}
                >
                  <Icon className="size-6" />
                </span>
                <div className="min-w-0">
                  <p className="font-serif text-[28px] leading-none font-semibold text-navy">{t('home.level', { level })}</p>
                  <p className="mt-2 text-sm font-semibold text-navy">{t(`levels.short.${level}`)}</p>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted">{t(`levels.meaning${level}`)}</p>
                </div>
              </li>
            )
          })}
        </ol>
      </div>
    </section>
  )
}

function SectionHeading({ kicker, lead, accent, light = false }: { kicker: string; lead: string; accent?: string; light?: boolean }) {
  return (
    <div data-reveal className="max-w-xl">
      <Eyebrow light={light}>{kicker}</Eyebrow>
      <h2 className={`mt-3 font-serif text-[34px] leading-[1.15] font-semibold text-balance sm:text-[40px] ${light ? 'text-white' : 'text-navy'}`}>
        {lead}
        {accent && <span className={light ? 'text-gold-light' : 'text-gold'}> {accent}</span>}
      </h2>
    </div>
  )
}

function useSectionReveal(scope: RefObject<HTMLElement | null>, dependencies: unknown[] = []) {
  useGSAP(
    () => {
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach((element) => {
          gsap.from(element, {
            opacity: 0,
            y: 24,
            duration: 0.7,
            ease: 'power3.out',
            scrollTrigger: { trigger: element, start: 'top 85%', once: true },
          })
        })
        ScrollTrigger.batch('[data-card]', {
          start: 'top 90%',
          once: true,
          onEnter: (cards) =>
            gsap.fromTo(cards, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.55, stagger: 0.08, ease: 'power2.out', overwrite: true }),
        })
      })
    },
    { scope, dependencies, revertOnUpdate: true },
  )
}

function LatestListings() {
  const { t } = useTranslation()
  const root = useRef<HTMLElement>(null)
  const [listings, setListings] = useState<PublicListing[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    marketApi
      .search({ sort: 'NEWEST', page_size: '6' })
      .then((page) => !cancelled && setListings(page.results))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [])

  useSectionReveal(root, [listings])

  // Nothing useful to show if the API is unreachable; the hero still works.
  if (failed) return null

  return (
    <section ref={root} className="mx-auto max-w-7xl px-4 pt-24 pb-12 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeading kicker={t('home.latestKicker')} lead={t('home.latestTitleLead')} accent={t('home.latestTitleAccent')} />
        {listings && listings.length > 0 && (
          <Link to="/listings" className="group inline-flex items-center gap-3 pb-2 text-sm font-semibold text-navy">
            <span className="underline decoration-navy/40 underline-offset-4 group-hover:decoration-gold">{t('home.viewAll')}</span>
            <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-1" />
          </Link>
        )}
      </div>

      <div className="mt-10">
        {listings === null ? (
          <div className="grid gap-7 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }, (_, index) => (
              <ListingCardSkeleton key={index} />
            ))}
          </div>
        ) : listings.length === 0 ? (
          <div data-reveal className="rounded-xl bg-white p-10 text-center shadow-card sm:p-14">
            <p className="font-serif text-2xl font-semibold text-navy">{t('home.emptyTitle')}</p>
            <p className="mx-auto mt-3 max-w-md text-[15px] leading-relaxed text-muted">{t('home.emptyBody')}</p>
            <Link to="/register" className="mt-7 inline-flex h-12 items-center rounded-md bg-navy px-7 text-sm font-semibold text-white hover:bg-navy-soft">
              {t('home.listCta')}
            </Link>
          </div>
        ) : (
          <div className="grid gap-7 sm:grid-cols-2 lg:grid-cols-3">
            {listings.map((listing, index) => (
              <ListingCard key={listing.listing_id} listing={listing} priority={index < 3} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function HowItWorks() {
  const { t } = useTranslation()
  const root = useRef<HTMLElement>(null)
  useSectionReveal(root)

  const steps = [
    { icon: SearchIcon, title: t('home.step1Title'), body: t('home.step1Body') },
    { icon: ChatIcon, title: t('home.step2Title'), body: t('home.step2Body') },
    { icon: ShieldIcon, title: t('home.step3Title'), body: t('home.step3Body') },
  ]

  return (
    <section ref={root} id="how" className="mx-auto max-w-7xl scroll-mt-24 px-4 py-16 sm:px-8">
      <SectionHeading kicker={t('home.howKicker')} lead={t('home.howTitle')} />
      {/* A real sequence, so the steps are numbered. */}
      <ol className="mt-10 grid gap-7 md:grid-cols-3">
        {steps.map((step, index) => (
          <li key={step.title} data-reveal className="relative rounded-xl bg-white p-7 shadow-card">
            <span className="absolute top-6 right-7 font-serif text-5xl font-semibold text-mist" aria-hidden="true">
              {index + 1}
            </span>
            <span className="grid size-12 place-items-center rounded-full bg-gold/10 text-gold">
              <step.icon className="size-6" />
            </span>
            <h3 className="mt-5 text-base font-semibold text-navy">{step.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">{step.body}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

// The reference's dark band: copy on the left, a photo filling the right half.
function ListCallToAction() {
  const { t } = useTranslation()
  const root = useRef<HTMLElement>(null)
  useSectionReveal(root)

  return (
    <section ref={root} className="mx-auto max-w-7xl px-4 pt-6 pb-24 sm:px-8">
      <div data-reveal className="relative isolate overflow-hidden rounded-xl bg-navy">
        <img
          src={sunsetSmall}
          srcSet={`${sunsetSmall} 720w, ${sunsetLarge} 1200w`}
          sizes="(min-width: 1024px) 60vw, 100vw"
          alt=""
          loading="lazy"
          decoding="async"
          className="absolute inset-y-0 right-0 -z-20 h-full w-full object-cover lg:w-3/5"
        />
        <div aria-hidden="true" className="absolute inset-0 -z-10 bg-gradient-to-r from-navy from-40% via-navy/80 via-55% to-navy/10" />
        <div className="max-w-lg px-8 py-12 sm:px-12 lg:py-16">
          <Eyebrow light>{t('home.listKicker')}</Eyebrow>
          <h2 className="mt-4 font-serif text-[34px] leading-[1.15] font-semibold text-balance text-white sm:text-[40px]">
            {t('home.listTitleLead')} <span className="text-gold-light">{t('home.listTitleAccent')}</span>
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-white/70">{t('home.listBody')}</p>
          <Link
            to="/register"
            className="group mt-8 inline-flex h-12 items-center gap-3 rounded-md bg-gold pr-3 pl-6 text-sm font-semibold text-navy transition-colors hover:bg-gold-light"
          >
            {t('home.listCta')}
            <span className="grid size-6 place-items-center rounded-full ring-1 ring-navy/40 transition-transform group-hover:translate-x-0.5">
              <ArrowRightIcon className="size-3.5" />
            </span>
          </Link>
        </div>
      </div>
    </section>
  )
}
