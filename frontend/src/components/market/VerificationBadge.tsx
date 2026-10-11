import type { ComponentType, SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import type { Level } from '../../lib/marketApi'
import { MapPinIcon, ShieldIcon, TickIcon, UserIcon } from '../icons'

// SRD 10: the Oweru Verified name, colour and badge style belong to Level 3
// only. Lower levels use neutral tints so they never read as Level 3.
const STYLES: Record<Level, { className: string; icon: ComponentType<SVGProps<SVGSVGElement>> }> = {
  3: { className: 'bg-gradient-to-r from-gold to-gold-light text-navy shadow-[0_6px_18px_-8px_rgba(200,145,40,0.9)]', icon: ShieldIcon },
  2: { className: 'bg-navy text-white', icon: MapPinIcon },
  1: { className: 'bg-white text-navy ring-1 ring-navy/15', icon: UserIcon },
  0: { className: 'bg-paper text-muted ring-1 ring-mist', icon: TickIcon },
}

export function VerificationBadge({ level, size = 'sm' }: { level: Level; size?: 'sm' | 'md' }) {
  const { t } = useTranslation()
  const { className, icon: Icon } = STYLES[level]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold whitespace-nowrap ${className} ${
        size === 'md' ? 'px-3 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
      }`}
    >
      <Icon className={size === 'md' ? 'size-4' : 'size-3.5'} />
      {t(`levels.short.${level}`)}
    </span>
  )
}
