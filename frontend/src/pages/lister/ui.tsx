import { useEffect, useRef, useState, type ComponentType, type ReactNode, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { MoreIcon } from '../../components/icons'
import { initials } from '../../lib/initials'
import type { LeadStage, ListingStatus } from '../../lib/listerApi'

// Pieces shared by the lister screens: L10's count cards, panels and outlined
// status pills, and L13's small stage pills and initials avatars.

const STATUS_PILL: Record<ListingStatus, string> = {
  DRAFT: 'border-mist bg-paper text-muted',
  ACTIVE: 'border-success/35 bg-success-soft text-success',
  UNDER_OFFER: 'border-gold/40 bg-gold/10 text-[#7a5410]',
  SOLD: 'border-[#3552a8]/30 bg-[#e8eefb] text-[#3552a8]',
  WITHDRAWN: 'border-mist bg-mist/40 text-muted',
  SUSPENDED: 'border-danger/30 bg-danger-soft text-danger',
}

export function ListingStatusPill({ status }: { status: ListingStatus }) {
  const { t } = useTranslation()
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[12px] whitespace-nowrap ${STATUS_PILL[status]}`}>
      {t(`lister.statuses.${status}`)}
    </span>
  )
}

const STAGE_PILL: Record<LeadStage, string> = {
  NEW: 'border-[#3552a8]/45 bg-[#eef2fc] text-[#3552a8]',
  CONTACTED: 'border-[#6b3fa0]/35 bg-[#f5effb] text-[#6b3fa0]',
  VIEWING: 'border-gold/55 bg-gold/10 text-[#8a5f0e]',
  NEGOTIATION: 'border-[#1e7a8a]/35 bg-[#e9f6f8] text-[#1e6b78]',
  CLOSING: 'border-navy/30 bg-navy/5 text-navy',
  WON: 'border-success/40 bg-success-soft text-success',
  LOST: 'border-danger/40 bg-danger-soft text-danger',
}

export function StagePill({ stage }: { stage: LeadStage }) {
  const { t } = useTranslation()
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-[1px] text-[11px] whitespace-nowrap ${STAGE_PILL[stage]}`}>
      {t(`lister.stages.${stage}`)}
    </span>
  )
}

export function Avatar({ name, className = 'size-9 text-[13px]' }: { name: string; className?: string }) {
  return (
    <span aria-hidden="true" className={`grid shrink-0 place-items-center rounded-full bg-gold/12 font-medium text-[#8a5f0e] ${className}`}>
      {initials(name) || '?'}
    </span>
  )
}

type Icon = ComponentType<SVGProps<SVGSVGElement>>

// L10: label top left, its icon top right, a large figure, one line under it.
export function CountCard({ label, value, note, icon: Icon }: { label: string; value: ReactNode; note: string; icon: Icon }) {
  return (
    <div className="rounded-xl border border-mist bg-white px-6 py-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[15px] text-muted">{label}</p>
        <Icon className="size-5 shrink-0 text-navy-soft" />
      </div>
      <p className="mt-4 text-[40px] leading-none font-semibold tracking-tight text-navy tabular-nums">{value}</p>
      <p className="mt-3 truncate text-[13px] text-navy-soft">{note}</p>
    </div>
  )
}

// L10: a white panel whose title row carries an icon and an optional link.
export function Panel({ title, icon: Icon, action, children, className = '' }: {
  title: string
  icon: Icon
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`overflow-hidden rounded-xl border border-mist bg-white ${className}`}>
      <div className="flex items-center justify-between gap-3 border-b border-mist px-6 py-5">
        <h2 className="flex items-center gap-3 text-[16px] font-medium text-navy">
          <Icon className="size-5 text-navy-soft" />
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  )
}

// A full-width notice, e.g. "verify your identity before publishing".
export function Notice({ tone = 'gold', icon: Icon, title, body, action }: {
  tone?: 'gold' | 'danger' | 'success'
  icon: Icon
  title: string
  body: ReactNode
  action?: ReactNode
}) {
  const tones = {
    gold: 'border-gold/35 bg-[#fdf7ec] text-[#7a5410]',
    danger: 'border-danger/25 bg-danger-soft text-danger',
    success: 'border-success/25 bg-success-soft text-success',
  }
  return (
    <div className={`flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border px-5 py-4 ${tones[tone]}`}>
      <Icon className="size-5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold">{title}</p>
        <p className="mt-0.5 text-[13px] text-navy-soft">{body}</p>
      </div>
      {action}
    </div>
  )
}

export type MenuItem = { label: string; onSelect: () => void; tone?: 'danger' }

// L13's kebab: a small list of actions under the three dots.
export function RowMenu({ label, items }: { label: string; items: MenuItem[] }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  if (items.length === 0) return null
  return (
    <div ref={root} className="relative" onClick={(event) => event.stopPropagation()}>
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="grid size-9 place-items-center rounded-full text-navy-soft transition-colors hover:bg-paper hover:text-navy"
      >
        <MoreIcon className="size-5" />
      </button>
      {open && (
        <ul role="menu" className="absolute top-full right-0 z-20 mt-1 min-w-[240px] overflow-hidden rounded-lg border border-mist bg-white py-1 shadow-[0_12px_32px_-12px_rgba(15,23,42,0.35)]">
          {items.map((item) => (
            <li key={item.label} role="none">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false)
                  item.onSelect()
                }}
                className={`block w-full whitespace-nowrap px-4 py-2.5 text-left text-[13.5px] hover:bg-paper ${item.tone === 'danger' ? 'text-danger' : 'text-navy'}`}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
