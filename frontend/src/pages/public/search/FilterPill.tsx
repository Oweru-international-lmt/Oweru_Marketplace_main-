import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useId, useRef, useState, type ComponentType, type ReactNode, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDownIcon } from '../../../components/icons'

type Props = {
  label: string
  // What the pill shows once a value is chosen, e.g. "Land" or "TSh 10M to 50M".
  value?: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  onClear?: () => void
  width?: string
  children: ReactNode
}

// Zoopla-style filter pill with a pop-over. Escape or a click outside closes
// it and returns focus to the pill.
export function FilterPill({ label, value, icon: Icon, onClear, width = 'w-[340px]', children }: Props) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const panelId = useId()
  const active = Boolean(value)

  useEffect(() => {
    if (!open) return
    function onPointer(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        button.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className={`inline-flex h-10 items-center gap-2 rounded-md pr-2.5 pl-3.5 text-[13px] font-semibold transition-colors ${
          active ? 'bg-navy text-white' : 'bg-white text-navy shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-mist hover:ring-navy/30'
        } ${open && !active ? 'ring-navy/40' : ''}`}
      >
        <Icon className={`size-4 ${active ? 'text-gold-light' : 'text-gold'}`} />
        <span className="max-w-44 truncate">{value ?? label}</span>
        <ChevronDownIcon className={`size-4 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            id={panelId}
            role="group"
            aria-label={label}
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            style={{ transformOrigin: 'top left' }}
            className={`absolute top-full left-0 z-30 mt-2 ${width} max-w-[calc(100vw-2rem)] rounded-lg bg-white p-5 shadow-lift ring-1 ring-mist`}
          >
            <p className="mb-4 text-sm font-semibold text-navy">{label}</p>
            {children}
            <div className="mt-5 flex items-center justify-between border-t border-mist pt-4">
              {onClear && active ? (
                <button type="button" onClick={onClear} className="text-link text-sm">
                  {t('search.clear')}
                </button>
              ) : (
                <span />
              )}
              <button
                type="button"
                onClick={() => {
                  setOpen(false)
                  button.current?.focus()
                }}
                className="h-10 rounded-md bg-navy px-5 text-sm font-semibold text-white hover:bg-navy-soft"
              >
                {t('search.done')}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
