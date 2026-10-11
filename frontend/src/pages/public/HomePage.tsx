import { useEffect, useRef, useState, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import coastLarge from '../../assets/photos/dar-coast-1200.webp'
import coastSmall from '../../assets/photos/dar-coast-720.webp'
import sunsetLarge from '../../assets/photos/dar-sunset-1200.webp'
import sunsetSmall from '../../assets/photos/dar-sunset-720.webp'
import { ArrowRightIcon, ChatIcon, FilterIcon, MapPinIcon, SearchIcon, ShieldIcon, TickIcon, UserIcon } from '../../components/icons'
import { ListingCard, ListingCardSkeleton } from '../../components/market/ListingCard'
import { PhotoCard } from '../../components/market/PhotoCard'
import { useMediaQuery } from '../../lib/useMediaQuery'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { gsap, MOTION_OK, ScrollTrigger, useGSAP } from '../../lib/gsap'
import { CATEGORIES, LEVELS, marketApi, type PublicListing } from '../../lib/marketApi'

// Follows the Horizon Realty reference section by section: light hero with a
// serif headline and two buttons, a white strip over the hero's base,
// featured listings, and a dark call-to-action band.
export function HomePage() {
  // Empty title: the tab shows just the brand.
  useDocumentTitle('')

  return (
    <>
      <Hero />
      {/* Phones: M2's search row and chips, right under the hero. */}
      <div className="px-4 pt-6 sm:px-8 lg:hidden">
        <PhoneSearch />
      </div>
      <LevelStrip />
      <LatestListings />
      <HowItWorks />
      <ListCallToAction />
    </>
  )
}

// Small uppercase label with a short gold rule under it, as in the reference.
function Eyebrow({ children, light = false, rule = false }: { children: string; light?: boolean; rule?: boolean }) {
  // The hero eyebrow (rule) is gold on the phone's dark band, navy on desktop.
  const tone = light ? 'text-gold-light' : rule ? 'text-gold-light lg:text-navy' : 'text-gold'
  return (
    <div data-kicker>
      <p className={`text-xs font-semibold tracking-[0.2em] uppercase ${tone}`}>{children}</p>
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
    // Phones: M1's full-bleed dark band. Desktop: Horizon's light hero.
    <section ref={root} className="relative isolate overflow-hidden bg-navy pt-28 pb-10 lg:bg-paper lg:pt-44 lg:pb-52">
      {/* Desktop: the photo fills the right, paper fades over it from the left. */}
      <img
        data-photo
        src={coastSmall}
        srcSet={`${coastSmall} 720w, ${coastLarge} 1200w`}
        sizes="70vw"
        alt=""
        // Lazy: hidden images stay unloaded, so phones skip this one.
        loading="lazy"
        className="absolute inset-y-0 right-0 -z-20 hidden h-[112%] w-[70%] object-cover [mask-image:linear-gradient(to_bottom,black_60%,transparent_88%)] lg:block"
      />
      <div aria-hidden="true" className="absolute inset-0 -z-10 hidden bg-gradient-to-r from-paper from-30% via-paper/85 via-50% to-paper/0 lg:block" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 -z-10 hidden h-48 bg-gradient-to-t from-paper via-paper/70 to-transparent lg:block" />

      <div className="mx-auto w-full max-w-7xl px-4 sm:px-8">
        <div className="max-w-[680px]">
          <Eyebrow rule>{t('home.kicker')}</Eyebrow>
          <h1 className="mt-6 font-serif text-[40px] leading-[1.08] font-semibold text-white sm:text-[54px] lg:mt-7 lg:text-[60px] lg:text-navy">
            {words.map(({ word, gold }, index) => (
              <span key={`${word}-${index}`} className="inline-block overflow-hidden pb-1.5 align-bottom">
                <span data-word className={`mr-[0.22em] inline-block ${gold ? 'text-gold-light lg:text-gold' : ''}`}>
                  {word}
                </span>
              </span>
            ))}
          </h1>
          <p data-fade className="mt-5 max-w-md text-[15px] leading-relaxed text-white/70 lg:mt-6 lg:text-base lg:text-navy/70">
            {t('home.subtitle')}
          </p>
          {/* M1 on phones: gold filled and white outline; Horizon on desktop: navy and outline. */}
          {/* Phones: M1's pair of equal buttons side by side. */}
          <div data-fade className="mt-8 grid grid-cols-2 gap-3 lg:mt-9 lg:flex lg:items-center">
            <Link
              to="/listings"
              className="inline-flex h-12 items-center justify-center rounded-md bg-gold px-3 text-center text-[13px] leading-tight font-semibold text-navy transition-colors hover:bg-gold-light lg:bg-navy lg:px-7 lg:text-sm lg:text-white lg:shadow-[0_10px_24px_-12px_rgba(15,23,42,0.8)] lg:hover:bg-navy-soft"
            >
              {t('home.browseAll')}
            </Link>
            <Link
              to="/#how"
              className="group inline-flex h-12 items-center justify-center gap-3 rounded-md px-3 text-center text-[13px] leading-tight font-semibold text-white ring-1 ring-white/40 transition-colors hover:bg-white/10 lg:bg-white/60 lg:pr-3 lg:pl-6 lg:text-sm lg:text-navy lg:ring-navy/25 lg:backdrop-blur-sm lg:hover:bg-white"
            >
              {t('site.howItWorks')}
              <span className="hidden size-6 place-items-center rounded-full ring-1 ring-navy/40 transition-transform group-hover:translate-x-0.5 lg:grid">
                <ArrowRightIcon className="size-3.5" />
              </span>
            </Link>
          </div>
          <img
            data-fade
            src={coastSmall}
            srcSet={`${coastSmall} 720w, ${coastLarge} 1200w`}
            sizes="100vw"
            alt=""
            loading="lazy"
            className="mt-9 aspect-[16/11] w-full rounded-xl object-cover lg:hidden"
          />
        </div>
      </div>
    </section>
  )
}

// M2's search row: a pill field and a round filter button that open the search
// page, then pill chips that open it already filtered.
function PhoneSearch() {
  const { t } = useTranslation()
  return (
    <div>
      <div className="flex gap-2">
        <Link to="/listings" className="flex h-13 min-w-0 flex-1 items-center gap-3 rounded-full bg-white pr-4 pl-5 text-sm text-muted ring-1 ring-mist">
          <SearchIcon className="size-5 shrink-0 text-navy" />
          <span className="truncate">{t('home.searchPlaceholder')}</span>
        </Link>
        <Link
          to="/listings?filters=1"
          aria-label={t('home.openFilters')}
          className="grid size-13 shrink-0 place-items-center rounded-full bg-white text-navy ring-1 ring-mist"
        >
          <FilterIcon className="size-5" />
        </Link>
      </div>
      <div className="-mx-4 mt-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:-mx-8 sm:px-8">
        <Link to="/listings" className="inline-flex h-10 shrink-0 items-center rounded-full bg-navy px-5 text-[13px] font-semibold text-white">
          {t('home.anyCategoryShort')}
        </Link>
        {CATEGORIES.map((category) => (
          <Link
            key={category}
            to={`/listings?category=${category}`}
            className="inline-flex h-10 shrink-0 items-center rounded-full bg-white px-5 text-[13px] font-semibold text-navy ring-1 ring-mist"
          >
            {t(`market.category.${category}`)}
          </Link>
        ))}
      </div>
    </div>
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
    <section ref={root} aria-labelledby="levels-title" className="relative z-10 mx-auto max-w-7xl px-4 pt-8 sm:px-8 lg:-mt-36 lg:pt-0">
      <div data-strip className="overflow-hidden rounded-xl shadow-lift">
        <h2 id="levels-title" className="sr-only">
          {t('home.stripLabel')}
        </h2>
        {/* gap-px over a mist background draws the hairlines between tiles. */}
        <ol className="grid grid-cols-2 gap-px bg-mist lg:grid-cols-4">
          {LEVELS.map((level) => {
            const Icon = LEVEL_ICONS[level]
            return (
              <li key={level} data-level className="flex flex-col gap-3 bg-white p-4 lg:flex-row lg:items-start lg:gap-4 lg:px-7 lg:py-8">
                <span
                  className={`grid size-10 shrink-0 place-items-center rounded-full lg:size-12 ${
                    level === 3 ? 'bg-gold text-white' : 'bg-gold/10 text-gold'
                  }`}
                >
                  <Icon className="size-5 lg:size-6" />
                </span>
                <div className="min-w-0">
                  <p className="font-serif text-xl leading-none font-semibold text-navy lg:text-[28px]">{t('home.level', { level })}</p>
                  <p className="mt-1.5 text-[13px] leading-snug font-semibold text-navy lg:mt-2 lg:text-sm">{t(`levels.short.${level}`)}</p>
                  <p className="mt-1.5 line-clamp-3 text-[11px] leading-relaxed text-muted lg:line-clamp-none lg:text-xs">
                    {t(`levels.meaning${level}`)}
                  </p>
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
      <h2 className={`mt-3 font-serif text-[28px] leading-[1.15] font-semibold text-balance sm:text-[40px] ${light ? 'text-white' : 'text-navy'}`}>
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
  const phone = !useMediaQuery('(min-width: 640px)')

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

  // The cards make the page taller; triggers further down were measured
  // before they arrived, so re-measure once they render.
  useEffect(() => {
    if (listings) ScrollTrigger.refresh()
  }, [listings])

  // Nothing useful to show if the API is unreachable; the hero still works.
  if (failed) return null

  return (
    <section ref={root} className="mx-auto max-w-7xl px-4 pt-16 pb-12 sm:px-8 lg:pt-24">
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
          // Phones: M3's carousel of tall photo cards (the next one peeks in). Wider screens: Horizon's grid.
          <div className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-3 [scrollbar-width:none] sm:mx-0 sm:grid sm:grid-cols-2 sm:gap-7 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-3">
            {listings.map((listing, index) => (
              <div key={listing.listing_id} className="w-[68%] shrink-0 snap-start sm:w-auto">
                {phone ? <PhotoCard listing={listing} variant="tall" priority={index < 2} /> : <ListingCard listing={listing} priority={index < 3} />}
              </div>
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
        {/* Phones: the photo sits behind the copy, so the shade runs bottom to top. */}
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-gradient-to-t from-navy from-45% via-navy/85 via-70% to-navy/40 lg:bg-gradient-to-r lg:from-40% lg:via-navy/80 lg:via-55% lg:to-navy/10"
        />
        <div className="max-w-lg px-6 pt-40 pb-10 sm:px-12 sm:pt-48 lg:py-16">
          <Eyebrow light>{t('home.listKicker')}</Eyebrow>
          <h2 className="mt-4 font-serif text-[28px] leading-[1.15] font-semibold text-balance text-white sm:text-[40px]">
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
