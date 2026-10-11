import { motion } from 'motion/react'

type SwitchProps = {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  disabled?: boolean
  busy?: boolean
}

export function Switch({ checked, onChange, label, disabled = false, busy = false }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      aria-busy={busy || undefined}
      disabled={disabled || busy}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full p-0.5 transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
        checked ? 'bg-gold' : 'bg-mist'
      }`}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 600, damping: 35 }}
        className={`block size-6 rounded-full bg-white shadow ${checked ? 'ml-auto' : ''}`}
      />
    </button>
  )
}
