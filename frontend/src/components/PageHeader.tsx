import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { useRef, type ReactNode } from 'react'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

type PageHeaderProps = {
  title: string
  description?: string
  eyebrow?: string
  actions?: ReactNode
  // Browser tab title when it should differ from the heading (e.g. a greeting).
  documentTitle?: string
}

export function PageHeader({ title, description, eyebrow, actions, documentTitle }: PageHeaderProps) {
  const root = useRef<HTMLDivElement>(null)
  useDocumentTitle(documentTitle ?? title)

  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.from('[data-reveal]', { y: 14, opacity: 0, duration: 0.6, stagger: 0.07, ease: 'power3.out' })
      })
    },
    { scope: root, dependencies: [title], revertOnUpdate: true },
  )

  return (
    <div ref={root} className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && (
          <p
            data-reveal
            className="mb-2 flex items-center gap-2 font-display text-[11px] font-medium tracking-[0.3em] text-muted uppercase"
          >
            <span className="h-0.5 w-5 rounded-full bg-gold" aria-hidden="true" />
            {eyebrow}
          </p>
        )}
        <h1 data-reveal className="font-display text-3xl font-semibold tracking-tight text-navy sm:text-4xl">
          {title}
        </h1>
        {description && (
          <p data-reveal className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">
            {description}
          </p>
        )}
      </div>
      {actions && <div data-reveal>{actions}</div>}
    </div>
  )
}
