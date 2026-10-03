import { motion } from 'motion/react'
import type { ReactNode } from 'react'

type CardProps = {
  title?: string
  titleId?: string
  action?: ReactNode
  delay?: number
  className?: string
  children: ReactNode
}

export function Card({ title, titleId, action, delay = 0.1, className = '', children }: CardProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay }}
      aria-labelledby={title ? titleId : undefined}
      className={`rounded-3xl bg-white p-6 shadow-[0_24px_60px_-30px_rgba(15,23,42,0.35)] ring-1 ring-mist sm:p-8 ${className}`}
    >
      {(title || action) && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          {title && (
            <h2 id={titleId} className="font-display text-xl font-semibold text-navy">
              {title}
            </h2>
          )}
          {action}
        </div>
      )}
      {children}
    </motion.section>
  )
}
