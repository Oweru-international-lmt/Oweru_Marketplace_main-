import type { ComponentType, ReactNode, SVGProps } from 'react'

// Pieces shared by the Marketer's pages (after M8, M10 and M11).

export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-[20px] border border-mist/80 bg-white ${className}`}>{children}</section>
}

// M8's tile: an icon and label row, then the figure in a grey inner box with a change chip.
export function NestedTile({ icon: Icon, label, value, chip }: { icon: ComponentType<SVGProps<SVGSVGElement>>; label: string; value: ReactNode; chip?: ReactNode }) {
  return (
    <div className="rounded-[18px] border border-mist/80 bg-white p-2">
      <p className="flex items-center gap-2 px-2.5 pt-1.5 pb-2 text-[14px] text-navy">
        <Icon className="size-4 text-navy-soft" />
        {label}
      </p>
      <div className="flex items-center justify-between gap-3 rounded-xl bg-[#f6f6f8] px-3.5 py-3">
        <span className="text-[24px] leading-none font-medium text-navy tabular-nums">{value}</span>
        {chip}
      </div>
    </div>
  )
}

export function Chip({ tone = 'muted', children }: { tone?: 'good' | 'bad' | 'muted' | 'gold'; children: ReactNode }) {
  const tones = {
    good: 'bg-success-soft text-success',
    bad: 'bg-danger-soft text-danger',
    muted: 'bg-paper text-navy-soft',
    gold: 'bg-gold/15 text-[#7a5410]',
  }
  return <span className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[12.5px] font-medium whitespace-nowrap ${tones[tone]}`}>{children}</span>
}
