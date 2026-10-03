import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { useRef, type ReactNode } from 'react'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

type PageHeroProps = {
  kicker: string
  title: string
  intro?: string
  // Browser tab title when it should differ from the heading (e.g. a greeting).
  documentTitle?: string
}

// Navy band under the app header. Page content overlaps its lower edge.
export function PageHero({ kicker, title, intro, documentTitle }: PageHeroProps) {
  const root = useRef<HTMLDivElement>(null)
  useDocumentTitle(documentTitle ?? title)

  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap
          .timeline({ defaults: { ease: 'power3.out' } })
          .from('[data-hero]', { y: 24, opacity: 0, duration: 0.7, stagger: 0.08 })
          .from('[data-rule]', { scaleX: 0, duration: 0.6, ease: 'power2.inOut' }, '<0.2')
      })
    },
    { scope: root, dependencies: [title], revertOnUpdate: true },
  )

  return (
    <div ref={root} className="bg-navy">
      <div className="mx-auto max-w-6xl px-5 pt-8 pb-28 sm:px-8 sm:pt-12">
        <p data-hero className="font-display text-[11px] font-medium tracking-[0.35em] text-gold-light uppercase">
          {kicker}
        </p>
        <h1 data-hero className="mt-3 font-display text-3xl font-medium text-white sm:text-5xl">
          {title}
        </h1>
        <span data-rule className="mt-5 block h-0.5 w-14 origin-left bg-gold" aria-hidden="true" />
        {intro && (
          <p data-hero className="mt-5 max-w-2xl text-[15px] leading-relaxed text-white/70">
            {intro}
          </p>
        )}
      </div>
    </div>
  )
}

export function PageBody({ children }: { children: ReactNode }) {
  return <main className="mx-auto -mt-16 max-w-6xl space-y-6 px-5 pb-16 sm:px-8">{children}</main>
}
