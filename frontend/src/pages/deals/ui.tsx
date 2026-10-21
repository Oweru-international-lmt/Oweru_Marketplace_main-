import { AnimatePresence, animate, motion, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckIcon, CloseIcon, CopyIcon, DocumentIcon, SendIcon, TickIcon } from '../../components/icons'
import type { PaymentStatus, PayoutStatus } from '../../lib/dealsApi'
import type { TimelineItem } from './data'
import { formatTsh } from '../../lib/format'

// Pieces shared by the Phase 1 money screens. Reference codes: D1 copy rows,
// D3 three-step bar, D6 numbered progress, D7 tick timeline, D8 amount box.

const EASE = [0.22, 1, 0.36, 1] as const

// D8: the big figure counts up once when it first appears.
export function CountUp({ value, className = '' }: { value: number; className?: string }) {
  const { i18n } = useTranslation()
  const reduce = useReducedMotion()
  const node = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const element = node.current
    if (!element) return
    const write = (amount: number) => {
      element.textContent = formatTsh(Math.round(amount), i18n.language)
    }
    if (reduce) {
      write(value)
      return
    }
    const controls = animate(value * 0.82, value, { duration: 0.9, ease: EASE, onUpdate: write })
    return () => controls.stop()
  }, [value, reduce, i18n.language])
  return <span ref={node} className={`tabular-nums ${className}`} aria-label={formatTsh(value, i18n.language)} />
}

// D1: a value with a copy button; the icon turns into a tick for a moment.
export function CopyValue({ value, label, mono = false }: { value: string; label: string; mono?: boolean }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(timer)
  }, [copied])
  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
    } catch {
      // Clipboard can be blocked; the value stays selectable.
    }
  }
  return (
    <span className="inline-flex max-w-full items-center gap-1.5">
      <span className={`min-w-0 text-[15px] font-semibold break-all text-navy ${mono ? 'font-mono text-[13px] tracking-wide' : ''}`}>{value}</span>
      <button
        type="button"
        onClick={() => void copy()}
        aria-label={copied ? t('deals.copied') : t('deals.copyLabel', { label })}
        className="relative grid size-7 place-items-center rounded-md text-muted transition-colors hover:bg-white hover:text-navy"
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={copied ? 'done' : 'copy'}
            initial={{ scale: 0.4, opacity: 0, rotate: copied ? -30 : 0 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            exit={{ scale: 0.4, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 520, damping: 26 }}
          >
            {copied ? <TickIcon className="size-4 text-success" /> : <CopyIcon className="size-4" />}
          </motion.span>
        </AnimatePresence>
      </button>
    </span>
  )
}

// D8 rows: label left, value right, a hairline between rows.
export function DetailRow({ label, children, strong = false }: { label: string; children: ReactNode; strong?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-mist/70 py-3.5 last:border-b-0">
      <span className="text-[14px] text-muted">{label}</span>
      <span className={`min-w-0 text-right text-[14px] break-words ${strong ? 'font-semibold text-navy' : 'font-medium text-navy'}`}>{children}</span>
    </div>
  )
}

const PAYMENT_CHIP: Record<PaymentStatus, string> = {
  AWAITING_PAYMENT: 'bg-[#fdf3d8] text-[#7a5410]',
  PROOF_UPLOADED: 'bg-[#e8eefb] text-[#3552a8]',
  OWNER_CONFIRMED: 'bg-[#f1e9fa] text-[#6b3fa0]',
  OWERU_CONFIRMED: 'bg-[#f1e9fa] text-[#6b3fa0]',
  BOTH_CONFIRMED: 'bg-success-soft text-success',
  COMPLETE: 'bg-navy text-white',
}

export function PaymentChip({ status }: { status: PaymentStatus }) {
  const { t } = useTranslation()
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium whitespace-nowrap ${PAYMENT_CHIP[status]}`}>{t(`deals.paymentStatus.${status}`)}</span>
}

const PAYOUT_CHIP: Record<PayoutStatus, string> = {
  PENDING: 'bg-[#fdf3d8] text-[#7a5410]',
  DUE: 'bg-[#e8eefb] text-[#3552a8]',
  ON_HOLD: 'bg-danger-soft text-danger',
  PAID: 'bg-success-soft text-success',
}

export function PayoutChip({ status }: { status: PayoutStatus }) {
  const { t } = useTranslation()
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium whitespace-nowrap ${PAYOUT_CHIP[status]}`}>{t(`deals.payoutStatus.${status}`)}</span>
}

// D3: three ticked circles joined by lines; the lines draw in up to the
// current step, and a note bubble points at the step the buyer is on.
export function ThreeStepBar({ steps, note }: { steps: { label: string; at: string | null }[]; note?: string }) {
  const { i18n } = useTranslation()
  const reduce = useReducedMotion()
  const current = steps.findIndex((step) => !step.at)
  const pointer = current === -1 ? steps.length - 1 : current
  return (
    <div>
      <ol className="grid grid-cols-3">
        {steps.map((step, index) => {
          const done = Boolean(step.at)
          return (
            <li key={step.label} className="relative flex flex-col items-center text-center">
              {index > 0 && (
                <span aria-hidden="true" className="absolute top-[18px] right-1/2 left-[-50%] mx-6 h-[2px] bg-mist">
                  <motion.span
                    className="absolute inset-0 origin-left bg-success"
                    initial={reduce ? false : { scaleX: 0 }}
                    animate={{ scaleX: done ? 1 : 0 }}
                    transition={{ duration: 0.45, delay: index * 0.28, ease: EASE }}
                  />
                </span>
              )}
              <motion.span
                className={`relative z-10 grid size-9 place-items-center rounded-full ring-4 ${done ? 'bg-success text-white ring-success/15' : 'bg-white text-muted ring-mist'}`}
                initial={reduce ? false : { scale: 0.5, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 420, damping: 22, delay: index * 0.28 }}
              >
                {done ? <CheckIcon className="size-4" /> : <span className="text-[13px] font-semibold">{index + 1}</span>}
              </motion.span>
              <span className={`mt-3 max-w-[9rem] text-[13px] leading-snug ${done ? 'text-navy' : 'text-muted'}`}>{step.label}</span>
              <span className="mt-1.5 text-[11px] text-muted tabular-nums">{step.at ? new Date(step.at).toLocaleString(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ' '}</span>
            </li>
          )
        })}
      </ol>
      {note && (
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.9, ease: EASE }}
          className="relative mt-4 rounded-lg bg-success-soft px-4 py-3 text-[13px] leading-relaxed text-success"
        >
          <span
            aria-hidden="true"
            className="absolute -top-1.5 size-3 rotate-45 bg-success-soft"
            style={{ left: `calc(${(pointer * 2 + 1) * (100 / (steps.length * 2))}% - 6px)` }}
          />
          {note}
        </motion.div>
      )}
    </div>
  )
}

// D7: a tick per finished step, a dashed ring for the next one, dates right.
export function TickTimeline({ items, header, status }: { items: TimelineItem[]; header: string; status: ReactNode }) {
  const { i18n } = useTranslation()
  const reduce = useReducedMotion()
  const firstOpen = items.findIndex((item) => !item.at)
  return (
    <div className="rounded-2xl border border-mist bg-white p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <span className="rounded-full border border-mist px-3.5 py-1.5 text-[13px] text-navy shadow-[0_1px_2px_rgba(15,23,42,0.06)]">{header}</span>
        {status}
      </div>
      <ol className="mt-5">
        {items.map((item, index) => {
          const done = Boolean(item.at)
          const next = index === firstOpen
          return (
            <motion.li
              key={item.key}
              className="relative flex gap-4 pb-6 last:pb-0"
              initial={reduce ? false : { opacity: 0, x: -8 }}
              animate={{ opacity: done || next ? 1 : 0.55, x: 0 }}
              transition={{ duration: 0.35, delay: 0.08 * index, ease: EASE }}
            >
              {index < items.length - 1 && <span aria-hidden="true" className={`absolute top-10 bottom-1 left-[17px] w-px ${done ? 'bg-success/40' : 'bg-mist'}`} />}
              <span
                className={`relative z-10 grid size-9 shrink-0 place-items-center rounded-full border ${
                  done ? 'border-success/20 bg-success-soft text-success' : next ? 'border-dashed border-gold bg-[#fdf7ec] text-[#9a6c12]' : 'border-dashed border-mist bg-paper text-muted'
                }`}
              >
                {done ? <TickIcon className="size-4" /> : <span className="size-1.5 rounded-full bg-current" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                  <p className={`text-[15px] ${done || next ? 'font-medium text-navy' : 'text-muted'}`}>{item.title}</p>
                  {item.at && (
                    <time dateTime={item.at} className="text-[12px] text-success tabular-nums">
                      {new Date(item.at).toLocaleString(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </time>
                  )}
                </div>
                <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{item.body}</p>
              </div>
            </motion.li>
          )
        })}
      </ol>
    </div>
  )
}

export type SubEvent = { at: string; text: string; tone: 'done' | 'sent' | 'failed' }

// D6: numbered steps, newest at the top with the current one banded, a dotted
// spine, and the small events of the open step underneath it.
export function NumberedProgress({ title, items, events = [], action }: { title: string; items: TimelineItem[]; events?: SubEvent[]; action?: ReactNode }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const reached = items.filter((item, index) => item.at || index === items.findIndex((row) => !row.at))
  const shown = [...reached].reverse()
  return (
    <section className="rounded-2xl border border-mist bg-white py-7 shadow-card">
      <h2 className="px-7 text-[17px] font-medium text-navy">{title}</h2>
      <ol className="relative mt-5">
        <span aria-hidden="true" className="absolute top-3 bottom-3 left-[118px] w-px border-l border-dashed border-mist" />
        {shown.map((item, order) => {
          const number = items.indexOf(item) + 1
          const current = !item.at
          return (
            <motion.li
              key={item.key}
              initial={reduce ? false : { opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.07 * order, ease: EASE }}
              className={`relative ${current ? 'bg-[#fdf3e2]' : ''}`}
            >
              <div className="flex items-center gap-0 py-3.5 pr-7">
                <span className={`w-[106px] shrink-0 pl-7 text-[12px] font-medium tracking-[0.06em] uppercase tabular-nums ${current ? 'text-navy' : 'text-muted'}`}>
                  {t('deals.stepNumber', { number: String(number).padStart(2, '0') })}
                </span>
                <span className="relative z-10 grid w-6 shrink-0 place-items-center">
                  {current ? (
                    <motion.span
                      className="size-2 rounded-full bg-gold"
                      animate={reduce ? undefined : { scale: [1, 1.6, 1], opacity: [1, 0.55, 1] }}
                      transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                    />
                  ) : (
                    <span className="size-1.5 rounded-full bg-success" />
                  )}
                </span>
                <span className={`min-w-0 flex-1 pl-4 text-[14px] ${current ? 'font-medium text-navy' : 'text-navy-soft'}`}>{item.title}</span>
                {item.at && (
                  <time dateTime={item.at} className="hidden text-[12px] text-muted tabular-nums sm:block">
                    {new Date(item.at).toLocaleDateString(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { day: 'numeric', month: 'short' })}
                  </time>
                )}
              </div>
              {current && (events.length > 0 || action) && (
                <div className="pb-4 pl-[148px] pr-7">
                  {events.length > 0 && (
                    <ul className="space-y-2">
                      {events.map((event) => (
                        <li key={`${event.at}-${event.text}`} className="flex items-center gap-3 text-[13px] text-muted">
                          {event.tone === 'done' ? <TickIcon className="size-3.5 text-success" /> : event.tone === 'sent' ? <SendIcon className="size-3.5 text-navy-soft" /> : <CloseIcon className="size-3.5 text-danger" />}
                          <span className="tabular-nums">{new Date(event.at).toLocaleString(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                          <span className="text-mist">|</span>
                          <span className="min-w-0 truncate">{event.text}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {action && <div className="mt-3">{action}</div>}
                </div>
              )}
            </motion.li>
          )
        })}
      </ol>
    </section>
  )
}

// A document as a file row (D2): icon, name, open.
export function FileRow({ name, note, onOpen }: { name: string; note?: string; onOpen: () => void }) {
  const { t } = useTranslation()
  return (
    <motion.button
      type="button"
      onClick={onOpen}
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex w-full items-center gap-3 rounded-lg border border-mist bg-white px-3.5 py-2.5 text-left transition-colors hover:border-navy-soft/40"
    >
      <span className="grid size-9 shrink-0 place-items-center rounded-md bg-danger-soft text-danger">
        <DocumentIcon className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium text-navy">{name}</span>
        {note && <span className="block text-[11px] text-muted">{note}</span>}
      </span>
      <span className="text-[12px] font-medium text-[#9a6c12]">{t('deals.open')}</span>
    </motion.button>
  )
}

// Hidden file input behind a button-shaped label, for slips and agreements.
export function FilePick({ accept, onPick, children, className = '', disabled = false }: { accept: string; onPick: (file: File) => void; children: ReactNode; className?: string; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <>
      <button type="button" disabled={disabled} onClick={() => input.current?.click()} className={className}>
        {children}
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) onPick(file)
        }}
      />
    </>
  )
}


// D19: a details panel that slides in from the right over the list, with a
// scrim; Escape or the close button dismisses it.
export function SidePanel({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  useEffect(() => {
    if (!open) return
    const close = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.button
            type="button"
            aria-label={t('deals.close')}
            onClick={onClose}
            className="absolute inset-0 bg-navy/30 backdrop-blur-[1px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={reduce ? { opacity: 0 } : { x: '100%' }}
            animate={reduce ? { opacity: 1 } : { x: 0 }}
            exit={reduce ? { opacity: 0 } : { x: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 34 }}
            className="absolute inset-y-0 right-0 flex w-full max-w-[460px] flex-col bg-white shadow-lift"
          >
            <div className="flex items-center justify-between gap-3 px-6 pt-6 pb-4">
              <h2 className="text-[20px] font-semibold text-navy">{title}</h2>
              <button type="button" onClick={onClose} aria-label={t('deals.close')} className="grid size-9 place-items-center rounded-full text-muted hover:bg-paper hover:text-navy">
                <CloseIcon className="size-5" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-8">{children}</div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  )
}
