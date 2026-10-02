import { AnimatePresence, motion } from 'motion/react'
import { useId, useState, type InputHTMLAttributes } from 'react'
import { useTranslation } from 'react-i18next'
import { EyeIcon, EyeOffIcon } from './icons'

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string
  hint?: string
  error?: string
}

export function TextField({ label, hint, error, type = 'text', className, ...input }: TextFieldProps) {
  const { t } = useTranslation()
  const id = useId()
  const [revealed, setRevealed] = useState(false)
  const isPassword = type === 'password'
  const describedBy = [error ? `${id}-error` : null, hint ? `${id}-hint` : null].filter(Boolean).join(' ') || undefined

  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-navy">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={isPassword && revealed ? 'text' : type}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={`block h-12 w-full rounded-xl border bg-white px-4 text-[15px] text-navy shadow-xs transition-[border-color,box-shadow] outline-none placeholder:text-muted/70 focus:ring-4 ${
            isPassword ? 'pr-12' : ''
          } ${
            error
              ? 'border-danger focus:border-danger focus:ring-danger/15'
              : 'border-mist hover:border-navy-soft/40 focus:border-gold focus:ring-gold/20'
          }`}
          {...input}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setRevealed((value) => !value)}
            aria-label={revealed ? t('common.hidePassword') : t('common.showPassword')}
            aria-pressed={revealed}
            className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-xl text-muted transition-colors hover:text-navy"
          >
            {revealed ? <EyeOffIcon className="size-5" /> : <EyeIcon className="size-5" />}
          </button>
        )}
      </div>
      <AnimatePresence initial={false} mode="wait">
        {error ? (
          <motion.p
            key="error"
            id={`${id}-error`}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18 }}
            className="mt-1.5 text-sm text-danger"
          >
            {error}
          </motion.p>
        ) : hint ? (
          <motion.p
            key="hint"
            id={`${id}-hint`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="mt-1.5 text-xs text-muted"
          >
            {hint}
          </motion.p>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
