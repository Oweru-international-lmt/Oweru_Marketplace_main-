import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { gsap, MOTION_OK, useGSAP } from '../../../lib/gsap'

// Building blocks shared by the free check, complaint and full check pages.
// Phones get the M1 dark band header; desktop keeps the Horizon serif heading.
// The status, receipt and form pieces live in tracking.tsx, receipt.tsx and fields.tsx.

type HeaderProps = { kicker: string; lead: string; accent?: string; body?: string; children?: ReactNode }

export function ServiceHeader({ kicker, lead, accent, body, children }: HeaderProps) {
  const root = useRef<HTMLElement>(null)
  useGSAP(
    () => {
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap
          .timeline({ defaults: { ease: 'power3.out' } })
          .from('[data-head]', { opacity: 0, y: 16, duration: 0.6, stagger: 0.08 })
          .from('[data-rule]', { scaleX: 0, duration: 0.6, ease: 'power2.inOut' }, 0.1)
      })
    },
    { scope: root },
  )

  return (
    <header
      ref={root}
      className="rounded-b-[28px] bg-navy px-5 pt-8 pb-9 text-white sm:rounded-none sm:bg-transparent sm:px-0 sm:pt-4 sm:pb-0 sm:text-navy"
    >
      <p data-head className="text-xs font-semibold tracking-[0.2em] text-gold-light uppercase sm:text-gold">
        {kicker}
      </p>
      <span data-rule aria-hidden="true" className="mt-3 block h-0.5 w-12 origin-left bg-gold" />
      <h1 data-head className="mt-4 max-w-3xl font-serif text-[30px] leading-[1.15] font-semibold text-balance sm:text-[40px] lg:text-[46px]">
        {lead} {accent && <span className="text-gold-light sm:text-gold">{accent}</span>}
      </h1>
      {body && (
        <p data-head className="mt-3 max-w-2xl text-[15px] leading-relaxed text-white/75 sm:text-base sm:text-muted">
          {body}
        </p>
      )}
      {children && <div data-head>{children}</div>}
    </header>
  )
}

// Main column plus a sticky aside on desktop. On phones the aside follows.
export function ServiceColumns({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mt-6 grid gap-8 px-4 sm:mt-10 sm:px-0 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-10">
      <div className="min-w-0 space-y-6">{children}</div>
      {aside && <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">{aside}</aside>}
    </div>
  )
}

export function ServicePage({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-7xl pb-12 sm:px-8 sm:pt-6 lg:pt-10 lg:pb-20">{children}</div>
}

export function Panel({ title, children, tone = 'white' }: { title?: string; children: ReactNode; tone?: 'white' | 'navy' }) {
  const navy = tone === 'navy'
  return (
    <section className={`rounded-2xl p-6 sm:rounded-md ${navy ? 'bg-navy text-white' : 'bg-white shadow-card'}`}>
      {title && <h2 className={`text-xs font-semibold tracking-[0.2em] uppercase ${navy ? 'text-gold-light' : 'text-gold'}`}>{title}</h2>}
      <div className={title ? 'mt-4' : ''}>{children}</div>
    </section>
  )
}

export function CopyButton({ value, label }: { value: string; label?: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 2000)
    return () => window.clearTimeout(timer)
  }, [copied])

  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => setCopied(true))
      }}
      className="inline-flex h-9 shrink-0 items-center rounded-full bg-paper px-3 text-xs font-semibold text-navy ring-1 ring-mist transition-colors hover:ring-navy/30"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={copied ? 'done' : 'idle'} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.15 }}>
          {copied ? t('forms.copied') : (label ?? t('forms.copy'))}
        </motion.span>
      </AnimatePresence>
      <span className="sr-only" aria-live="polite">
        {copied ? t('forms.copied') : ''}
      </span>
    </button>
  )
}
