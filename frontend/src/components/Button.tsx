import { motion, type HTMLMotionProps } from 'motion/react'
import type { ReactNode } from 'react'

type ButtonProps = Omit<HTMLMotionProps<'button'>, 'children'> & {
  children: ReactNode
  loading?: boolean
  loadingLabel?: string
  variant?: 'primary' | 'secondary'
}

const VARIANTS = {
  // Navy text on brand gold passes WCAG AA; white on gold does not.
  primary: 'bg-gold text-navy shadow-[0_8px_24px_-10px_rgba(200,145,40,0.7)] hover:bg-gold-light',
  secondary: 'bg-white text-navy ring-1 ring-mist hover:ring-navy-soft/40',
}

export function Button({
  loading = false,
  loadingLabel,
  variant = 'primary',
  disabled,
  children,
  className = '',
  ...props
}: ButtonProps) {
  return (
    <motion.button
      whileTap={loading || disabled ? undefined : { scale: 0.98 }}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex h-12 w-full items-center justify-center gap-2.5 rounded-xl px-6 font-display text-[15px] font-semibold tracking-wide transition-colors disabled:cursor-not-allowed disabled:opacity-70 ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {loading && (
        <span className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" aria-hidden="true" />
      )}
      {loading && loadingLabel ? loadingLabel : children}
    </motion.button>
  )
}
