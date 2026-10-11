import { useId, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CameraIcon, CloseIcon, DocumentIcon, ImageIcon } from '../../../components/icons'

// Form controls for the service pages, one look per Pinterest reference:
// "dark" for the navy step form (S3), "line" for the phone address sheet (S2),
// "filled" for the report-an-issue screens (S5).
export type Variant = 'dark' | 'line' | 'filled'

const LABEL: Record<Variant, string> = {
  dark: 'mb-2 block text-[13px] text-white/75',
  line: 'block text-xs text-muted',
  filled: 'mb-2 block text-sm font-medium text-navy',
}

const CONTROL: Record<Variant, string> = {
  dark: 'block w-full rounded-xl border border-white/25 bg-white/[0.04] px-4 text-[15px] text-white outline-none transition-colors placeholder:text-white/35 focus:border-gold focus:ring-2 focus:ring-gold/25 [&>option]:text-navy',
  line: 'block w-full border-0 border-b border-mist bg-transparent px-0 text-[15px] text-navy outline-none transition-colors placeholder:text-muted/60 focus:border-gold',
  filled: 'block w-full rounded-2xl border-0 bg-paper px-4 text-[15px] text-navy outline-none ring-1 ring-transparent transition-shadow placeholder:text-muted/70 focus:ring-gold/60',
}

const INVALID: Record<Variant, string> = {
  dark: 'border-[#ff9b8a]',
  line: 'border-danger',
  filled: 'ring-danger',
}

const ERROR_TEXT: Record<Variant, string> = { dark: 'text-[#ffb3a6]', line: 'text-danger', filled: 'text-danger' }
const HINT_TEXT: Record<Variant, string> = { dark: 'text-white/50', line: 'text-muted', filled: 'text-muted' }

type ControlProps = { id: string; 'aria-describedby'?: string; 'aria-invalid'?: true; className: string }

type FieldProps = {
  label: string
  variant: Variant
  hint?: string
  error?: string
  className?: string
  children: (control: ControlProps) => ReactNode
}

// Label, hint and error around one control; the page renders the control
// itself so inputs, selects and text areas share the treatment.
export function Field({ label, variant, hint, error, className, children }: FieldProps) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div className={className}>
      <label htmlFor={id} className={LABEL[variant]}>
        {label}
      </label>
      {children({
        id,
        'aria-describedby': describedBy,
        'aria-invalid': error ? true : undefined,
        className: `${CONTROL[variant]} ${error ? INVALID[variant] : ''}`,
      })}
      {error ? (
        <p id={`${id}-error`} className={`mt-1.5 text-sm ${ERROR_TEXT[variant]}`}>
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className={`mt-1.5 text-xs leading-relaxed ${HINT_TEXT[variant]}`}>
            {hint}
          </p>
        )
      )}
    </div>
  )
}

type ChipsProps<T extends string> = {
  label: string
  options: { value: T; label: string }[]
  value: T | ''
  onChange: (value: T) => void
  variant: 'dark' | 'light' | 'tag'
  error?: string
  centered?: boolean
}

// One choice from a few, as chips: S5's issue chips, S2's location tags.
export function Chips<T extends string>({ label, options, value, onChange, variant, error, centered = false }: ChipsProps<T>) {
  const id = useId()
  const styles = {
    dark: { on: 'bg-gold text-navy', off: 'bg-white/[0.06] text-white/85 ring-1 ring-white/20 hover:ring-white/40' },
    light: { on: 'bg-gold text-navy', off: 'bg-paper text-navy/75 hover:bg-mist/70' },
    tag: { on: 'bg-gold text-navy ring-1 ring-gold', off: 'bg-white text-navy/70 ring-1 ring-mist hover:ring-navy/30' },
  }[variant]
  return (
    <div>
      <p id={id} className={`text-xs ${variant === 'dark' ? 'text-white/75' : 'text-muted'} ${centered ? 'text-center' : ''}`}>
        {label}
      </p>
      <div role="radiogroup" aria-labelledby={id} aria-invalid={error ? true : undefined} className={`mt-2.5 flex flex-wrap gap-2 ${centered ? 'justify-center' : ''}`}>
        {options.map((option) => {
          const on = option.value === value
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange(option.value)}
              className={`inline-flex items-center gap-1.5 rounded-full font-medium transition-colors ${
                variant === 'tag' ? 'h-8 px-3.5 text-[13px]' : 'h-9 px-4 text-[13px]'
              } ${on ? styles.on : styles.off}`}
            >
              {option.label}
            </button>
          )
        })}
      </div>
      {error && <p className={`mt-1.5 text-sm ${variant === 'dark' ? 'text-[#ffb3a6]' : 'text-danger'} ${centered ? 'text-center' : ''}`}>{error}</p>}
    </div>
  )
}

type PhotoBoxProps = {
  label: string
  files: File[]
  onChange: (files: File[]) => void
  accept: string
  max: number
  variant: 'dark' | 'filled'
  error?: string
}

// S5's grey "Add photo" box; picked files list under it, each removable.
export function PhotoBox({ label, files, onChange, accept, max, variant, error }: PhotoBoxProps) {
  const { t } = useTranslation()
  const id = useId()
  const dark = variant === 'dark'
  const full = files.length >= max

  return (
    <div>
      <input
        id={id}
        type="file"
        accept={accept}
        multiple={max > 1}
        disabled={full}
        className="sr-only"
        onChange={(event) => {
          onChange([...files, ...Array.from(event.target.files ?? [])].slice(0, max))
          event.target.value = ''
        }}
      />
      <label
        htmlFor={id}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl px-4 py-7 text-center text-[13px] transition-colors ${
          dark ? 'border border-dashed border-white/25 bg-white/[0.04] text-white/70 hover:border-gold' : 'bg-paper text-muted hover:bg-mist/60'
        } ${full ? 'cursor-not-allowed opacity-60' : ''} ${error ? (dark ? 'border-[#ff9b8a]' : 'ring-1 ring-danger') : ''}`}
      >
        <CameraIcon className={`size-6 ${dark ? 'text-gold-light' : 'text-navy/70'}`} />
        <span>{full ? t('forms.filesFull', { max }) : label}</span>
        <span className={`text-[11px] ${dark ? 'text-white/45' : 'text-muted/80'}`}>{t('forms.addFiles', { count: files.length, max })}</span>
      </label>
      {files.length > 0 && (
        <ul className="mt-3 space-y-2">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${file.size}-${index}`}
              className={`flex items-center gap-3 rounded-xl px-3 py-2 ${dark ? 'bg-white/[0.06] text-white' : 'bg-white text-navy ring-1 ring-mist'}`}
            >
              {file.type.startsWith('image/') ? <ImageIcon className="size-4 shrink-0 opacity-70" /> : <DocumentIcon className="size-4 shrink-0 opacity-70" />}
              <span className="min-w-0 flex-1 truncate text-sm">{file.name}</span>
              <button
                type="button"
                onClick={() => onChange(files.filter((_, position) => position !== index))}
                aria-label={t('forms.removeFile', { name: file.name })}
                className={`grid size-9 shrink-0 place-items-center rounded-full ${dark ? 'hover:bg-white/10' : 'hover:bg-paper'}`}
              >
                <CloseIcon className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className={`mt-1.5 text-sm ${dark ? 'text-[#ffb3a6]' : 'text-danger'}`}>{error}</p>}
    </div>
  )
}
