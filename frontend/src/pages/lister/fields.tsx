import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { ChevronDownIcon } from '../../components/icons'

// L3's form controls: a small medium-weight label, a 44px box with a thin
// edge, a hint in small grey type under it, and the error in its place.

const BOX = 'block w-full rounded-lg border bg-white px-3.5 text-[14px] text-navy outline-none transition-[border-color,box-shadow] placeholder:text-muted/70 focus:ring-[3px]'
const OK = 'border-[#cfd5df] hover:border-navy-soft/40 focus:border-gold focus:ring-gold/20'
const BAD = 'border-danger focus:border-danger focus:ring-danger/15'

type Shell = { label: string; hint?: ReactNode; error?: string; className?: string; required?: boolean }

function Frame({ id, label, hint, error, className, required, children }: Shell & { id: string; children: ReactNode }) {
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-2 block text-[13.5px] font-medium text-navy">
        {label}
        {required && <span className="ml-0.5 text-danger" aria-hidden="true">*</span>}
      </label>
      {children}
      {error ? (
        <p id={`${id}-note`} className="mt-1.5 text-[12px] text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-note`} className="mt-1.5 text-[12px] text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

export function Input({ label, hint, error, className, required, prefix, ...input }: Shell & Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'prefix'> & { prefix?: ReactNode }) {
  const id = useId()
  const control = (
    <input
      id={id}
      aria-invalid={error ? true : undefined}
      aria-describedby={error || hint ? `${id}-note` : undefined}
      aria-required={required || undefined}
      className={`${BOX} h-11 ${prefix ? 'rounded-l-none' : ''} ${error ? BAD : OK}`}
      {...input}
    />
  )
  return (
    <Frame id={id} label={label} hint={hint} error={error} className={className} required={required}>
      {prefix ? (
        // L1's price box: a fixed currency segment joined to the input.
        <div className="flex">
          <span className="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-l-lg border border-r-0 border-[#cfd5df] bg-paper px-3.5 text-[14px] font-medium text-navy">
            {prefix}
          </span>
          <div className="min-w-0 flex-1">{control}</div>
        </div>
      ) : (
        control
      )}
    </Frame>
  )
}

export function Select({ label, hint, error, className, required, options, placeholder, ...select }: Shell &
  Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> & { options: { value: string; label: string }[]; placeholder?: string }) {
  const id = useId()
  return (
    <Frame id={id} label={label} hint={hint} error={error} className={className} required={required}>
      <div className="relative">
        <select
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? `${id}-note` : undefined}
          aria-required={required || undefined}
          className={`${BOX} h-11 appearance-none pr-10 ${select.value ? '' : 'text-muted/80'} ${error ? BAD : OK}`}
          {...select}
        >
          {placeholder !== undefined && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value} className="text-navy">
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-navy-soft" />
      </div>
    </Frame>
  )
}

export function TextArea({ label, hint, error, className, required, ...area }: Shell & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'>) {
  const id = useId()
  return (
    <Frame id={id} label={label} hint={hint} error={error} className={className} required={required}>
      <textarea
        id={id}
        rows={5}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? `${id}-note` : undefined}
        className={`${BOX} resize-y py-3 leading-relaxed ${error ? BAD : OK}`}
        {...area}
      />
    </Frame>
  )
}

// Two or three side-by-side choices drawn as bordered tiles.
export function ChoiceTiles<T extends string>({ label, value, options, onChange, error }: {
  label: string
  value: T | ''
  options: { value: T; label: string; hint?: string }[]
  onChange: (value: T) => void
  error?: string
}) {
  const id = useId()
  return (
    <fieldset aria-describedby={error ? `${id}-note` : undefined}>
      <legend className="mb-2 block text-[13.5px] font-medium text-navy">
        {label}
        <span className="ml-0.5 text-danger" aria-hidden="true">*</span>
      </legend>
      <div className="grid gap-3 sm:grid-cols-2">
        {options.map((option) => {
          const on = option.value === value
          return (
            <label
              key={option.value}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3.5 py-3 transition-colors ${
                on ? 'border-gold bg-gold/[0.07]' : error ? 'border-danger' : 'border-[#cfd5df] hover:border-navy-soft/40'
              }`}
            >
              <input type="radio" name={id} value={option.value} checked={on} onChange={() => onChange(option.value)} className="sr-only" />
              <span className={`mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border ${on ? 'border-gold' : 'border-[#b8c0cc]'}`}>
                {on && <span className="size-2 rounded-full bg-gold" />}
              </span>
              <span>
                <span className="block text-[14px] font-medium text-navy">{option.label}</span>
                {option.hint && <span className="mt-0.5 block text-[12px] text-muted">{option.hint}</span>}
              </span>
            </label>
          )
        })}
      </div>
      {error && (
        <p id={`${id}-note`} className="mt-1.5 text-[12px] text-danger">
          {error}
        </p>
      )}
    </fieldset>
  )
}

// L3's section heading inside a form card, with a hairline under it.
export function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="pt-2">
      <h3 className="border-b border-mist/80 pb-2.5 text-[16px] font-semibold text-navy">{title}</h3>
      <div className="mt-5 space-y-5">{children}</div>
    </div>
  )
}
