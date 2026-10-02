import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { AlertIcon, CheckIcon } from './icons'

type AlertProps = {
  tone: 'error' | 'success'
  children: ReactNode
}

export function Alert({ tone, children }: AlertProps) {
  const error = tone === 'error'
  return (
    <motion.div
      role={error ? 'alert' : 'status'}
      initial={{ opacity: 0, y: -6 }}
      animate={error ? { opacity: 1, y: 0, x: [0, -6, 6, -3, 3, 0] } : { opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className={`flex gap-3 rounded-xl px-4 py-3 text-sm leading-relaxed ${
        error ? 'bg-danger-soft text-danger' : 'bg-success-soft text-success'
      }`}
    >
      {error ? <AlertIcon className="mt-0.5 size-5 shrink-0" /> : <CheckIcon className="mt-0.5 size-5 shrink-0" />}
      <div>{children}</div>
    </motion.div>
  )
}
