import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { AlertIcon } from '../../../components/icons'

// After S7: a white card on the grey page, a large outlined mark, a light
// headline and one sentence, then sections of quiet label and value rows
// split by thin rules. Under the card, small centred notes.

export function ReceiptPage({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-[600px] px-4 pt-8 pb-16 sm:px-0 sm:pt-12">{children}</div>
}

export function ReceiptBrand() {
  return (
    <div className="mb-7 flex justify-center">
      <span className="font-display text-[22px] font-semibold tracking-[0.32em] text-gold uppercase">Oweru</span>
    </div>
  )
}

export function ReceiptCard({ mark, title, lead, children }: { mark: 'check' | 'alert'; title: string; lead: ReactNode; children: ReactNode }) {
  return (
    <article className="rounded-[3px] border border-mist/80 bg-white px-6 py-10 text-center shadow-[0_1px_3px_rgba(15,23,42,0.06)] sm:px-10 sm:py-12">
      <motion.span
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 320, damping: 20 }}
        className={`mx-auto grid size-20 place-items-center rounded-full border-[3px] ${mark === 'check' ? 'border-gold text-gold' : 'border-danger text-danger'}`}
      >
        {mark === 'check' ? (
          <svg viewBox="0 0 24 24" className="size-10" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <motion.path d="m5 12.5 4.5 4.5L19 7.5" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.2, duration: 0.45 }} />
          </svg>
        ) : (
          <AlertIcon className="size-10" />
        )}
      </motion.span>
      <h1 className="mt-6 text-[28px] leading-tight font-light text-navy sm:text-[32px]">{title}</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-muted">{lead}</p>
      {children}
    </article>
  )
}

export function ReceiptSection({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="mt-8 border-t border-mist pt-8 text-left">
      {title && <h2 className="mb-5 text-center text-[13px] font-medium tracking-[0.14em] text-navy/80 uppercase">{title}</h2>}
      {children}
    </section>
  )
}

export function ReceiptRows({ children }: { children: ReactNode }) {
  return <dl className="space-y-3">{children}</dl>
}

export function ReceiptRow({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-6">
        <dt className="shrink-0 text-[15px] text-muted">{label}</dt>
        <dd className="min-w-0 text-right text-[15px] font-medium break-words text-navy">{value}</dd>
      </div>
      {note && <p className="mt-1 text-[13px] leading-relaxed text-muted">{note}</p>}
    </div>
  )
}

export function ReceiptFooter({ children }: { children: ReactNode }) {
  return <div className="mt-8 space-y-4 text-center text-[15px] leading-relaxed text-muted">{children}</div>
}

// The round brand mark that closes the page, like S7's.
export function ReceiptSeal() {
  return (
    <div className="mt-8 flex justify-center">
      <span className="grid size-11 place-items-center overflow-hidden rounded-full bg-mist/70">
        <img src="/oweru-logo-print.jpg" alt="" className="size-full object-cover opacity-60 grayscale" />
      </span>
    </div>
  )
}
