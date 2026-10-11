import { AnimatePresence, motion } from 'motion/react'
import { useId, useRef, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDownIcon, CloseIcon, DocumentIcon, ImageIcon } from './icons'

// Siblings of TextField for the public service forms: same label, hint and
// error treatment, same 48px control height.

const CONTROL = 'block w-full rounded-xl border bg-white px-4 text-[15px] text-navy shadow-xs transition-[border-color,box-shadow] outline-none focus:ring-4'
const OK = 'border-mist hover:border-navy-soft/40 focus:border-gold focus:ring-gold/20'
const BAD = 'border-danger focus:border-danger focus:ring-danger/15'

function Message({ id, error, hint }: { id: string; error?: string; hint?: ReactNode }) {
  return (
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
        <motion.p key="hint" id={`${id}-hint`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-1.5 text-xs text-muted">
          {hint}
        </motion.p>
      ) : null}
    </AnimatePresence>
  )
}

function describedBy(id: string, error?: string, hint?: ReactNode): string | undefined {
  return [error ? `${id}-error` : null, hint && !error ? `${id}-hint` : null].filter(Boolean).join(' ') || undefined
}

type SelectFieldProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> & {
  label: string
  hint?: string
  error?: string
  options: { value: string; label: string }[]
  placeholder?: string
}

export function SelectField({ label, hint, error, options, placeholder, className, ...select }: SelectFieldProps) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-navy">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, error, hint)}
          className={`${CONTROL} h-12 appearance-none pr-11 ${error ? BAD : OK}`}
          {...select}
        >
          {placeholder !== undefined && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-4 size-4 -translate-y-1/2 text-muted" />
      </div>
      <Message id={id} error={error} hint={hint} />
    </div>
  )
}

type TextAreaFieldProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> & { label: string; hint?: string; error?: string }

export function TextAreaField({ label, hint, error, className, rows = 4, ...area }: TextAreaFieldProps) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-navy">
        {label}
      </label>
      <textarea
        id={id}
        rows={rows}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, error, hint)}
        className={`${CONTROL} resize-y py-3 leading-relaxed placeholder:text-muted/70 ${error ? BAD : OK}`}
        {...area}
      />
      <Message id={id} error={error} hint={hint} />
    </div>
  )
}

type FilesFieldProps = {
  label: string
  hint?: string
  error?: string
  files: File[]
  onChange: (files: File[]) => void
  accept: string
  max: number
  className?: string
}

// Up to `max` files, each removable. The input resets after every pick so the
// same file can be chosen again after removing it.
export function FilesField({ label, hint, error, files, onChange, accept, max, className }: FilesFieldProps) {
  const { t } = useTranslation()
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const full = files.length >= max

  return (
    <div className={className}>
      <p id={`${id}-label`} className="mb-1.5 block text-sm font-medium text-navy">
        {label}
      </p>
      {files.length > 0 && (
        <ul className="mb-3 space-y-2">
          {files.map((file, index) => (
            <li key={`${file.name}-${file.size}-${index}`} className="flex items-center gap-3 rounded-xl bg-white px-3 py-2.5 shadow-card">
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-paper text-navy">
                {file.type.startsWith('image/') ? <ImageIcon className="size-4" /> : <DocumentIcon className="size-4" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-navy">{file.name}</span>
                <span className="block text-xs text-muted">{Math.max(1, Math.round(file.size / 1024))} KB</span>
              </span>
              <button
                type="button"
                onClick={() => onChange(files.filter((_, position) => position !== index))}
                aria-label={t('forms.removeFile', { name: file.name })}
                className="grid size-10 shrink-0 place-items-center rounded-full text-muted transition-colors hover:bg-paper hover:text-navy"
              >
                <CloseIcon className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        ref={input}
        id={id}
        type="file"
        accept={accept}
        multiple
        aria-labelledby={`${id}-label`}
        aria-describedby={describedBy(id, error, hint)}
        className="sr-only"
        disabled={full}
        onChange={(event) => {
          const picked = Array.from(event.target.files ?? [])
          onChange([...files, ...picked].slice(0, max))
          event.target.value = ''
        }}
      />
      <label
        htmlFor={id}
        className={`flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-3 text-sm font-semibold transition-colors ${
          full ? 'cursor-not-allowed border-mist text-muted' : 'border-navy/25 text-navy hover:border-gold hover:bg-white'
        } ${error ? 'border-danger' : ''}`}
      >
        <ImageIcon className="size-4" />
        {full ? t('forms.filesFull', { max }) : t('forms.addFiles', { count: files.length, max })}
      </label>
      <Message id={id} error={error} hint={hint} />
    </div>
  )
}
