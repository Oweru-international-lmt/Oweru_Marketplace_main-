import { motion } from 'motion/react'
import type { ComponentType, SVGProps } from 'react'

type StatTileProps = {
  label: string
  value: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  delay?: number
}

export function StatTile({ label, value, icon: Icon, delay = 0 }: StatTileProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay }}
      className="flex items-center gap-4 rounded-2xl bg-white p-5 ring-1 ring-mist"
    >
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-gold/15 text-navy">
        <Icon className="size-5" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm text-muted">{label}</p>
        <p className="font-display text-2xl font-semibold text-navy">{value}</p>
      </div>
    </motion.div>
  )
}
