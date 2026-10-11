import { motion } from 'motion/react'
import type { ReactNode } from 'react'

type CardProps = {
  title?: string
  titleId?: string
  description?: string
  action?: ReactNode
  delay?: number
  className?: string
  children: ReactNode
}

export function Card({ title, titleId, description, action, delay = 0.05, className = '', children }: CardProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1], delay }}
      aria-labelledby={title ? titleId : undefined}
      className={`rounded-2xl bg-white p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-mist ${className}`}
    >
      {(title || action) && (
        <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title && (
              <h2 id={titleId} className="font-display text-lg font-semibold text-navy">
                {title}
              </h2>
            )}
            {description && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </motion.section>
  )
}
