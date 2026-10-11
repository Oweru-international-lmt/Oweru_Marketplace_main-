import { motion } from 'motion/react'
import { useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDownIcon } from '../../../components/icons'
import { VerificationBadge } from '../../../components/market/VerificationBadge'
import { digitsOnly, formatNumber, formatTshShort } from '../../../lib/format'
import { CATEGORIES, TITLE_TYPES, type Place, type SearchParams } from '../../../lib/marketApi'

export type Places = { regions: Place[]; districts: Place[]; wards: Place[] }
export type Change = Partial<Record<keyof SearchParams, string | undefined>>
type FieldProps = { filters: SearchParams; onChange: (change: Change) => void }

// SRC-01 filters as separate fields: the desktop pill row shows each in its
// own pop-over, the phone sheet stacks them all in the M2 reference's style.
// Changes apply to the URL at once.
export function FilterPanel({ filters, places, onChange }: FieldProps & { places: Places }) {
  const { t } = useTranslation()
  return (
    <div className="divide-y divide-mist">
      <SheetGroup title={t('search.category')}>
        <CategoryField filters={filters} onChange={onChange} />
      </SheetGroup>
      <SheetGroup title={t('search.priceRange')}>
        <PriceSliderField min={filters.min_price} max={filters.max_price} onCommit={(min, max) => onChange({ min_price: min, max_price: max })} />
      </SheetGroup>
      <SheetGroup title={t('search.location')}>
        <LocationFields filters={filters} places={places} onChange={onChange} />
      </SheetGroup>
      <SheetGroup title={t('search.level')}>
        <LevelBoxesField filters={filters} onChange={onChange} />
      </SheetGroup>
      <SheetGroup title={t('search.titleType')}>
        <TitleTypePills filters={filters} onChange={onChange} />
      </SheetGroup>
      <SheetGroup title={t('search.size')}>
        <RangeField min={filters.min_size} max={filters.max_size} onCommit={(min, max) => onChange({ min_size: min, max_size: max })} />
      </SheetGroup>
    </div>
  )
}

export function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset>
      <legend className="mb-3 text-xs font-semibold tracking-[0.2em] text-muted uppercase">{title}</legend>
      {children}
    </fieldset>
  )
}

// Sheet sections: a plain bold heading over the control, separated by hairlines.
function SheetGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="py-5 first:pt-1">
      <legend className="float-left mb-3.5 w-full text-[15px] font-semibold text-navy">{title}</legend>
      <div className="clear-both">{children}</div>
    </fieldset>
  )
}

// M2's chip row: navy when chosen, outlined otherwise.
export function CategoryField({ filters, onChange, nowrap = false }: FieldProps & { nowrap?: boolean }) {
  const { t } = useTranslation()
  // Unique per instance, so two panels never animate their pills into each other.
  const pillId = useId()
  return (
    <div className={`flex gap-2 ${nowrap ? 'w-max' : 'flex-wrap'}`}>
      {(['', ...CATEGORIES] as const).map((category) => {
        const active = (filters.category ?? '') === category
        return (
          <button
            key={category || 'any'}
            type="button"
            aria-pressed={active}
            onClick={() => onChange({ category: category || undefined })}
            className={`relative h-10 shrink-0 rounded-full px-5 text-[13px] font-semibold transition-colors ${
              active ? 'text-white' : 'bg-white text-navy ring-1 ring-mist hover:ring-navy/30'
            }`}
          >
            {active && (
              <motion.span
                layoutId={`filter-category-${pillId}`}
                className="absolute inset-0 rounded-full bg-navy"
                transition={{ type: 'spring', stiffness: 500, damping: 38 }}
              />
            )}
            <span className="relative">{category ? t(`market.category.${category}`) : t('search.any')}</span>
          </button>
        )
      })}
    </div>
  )
}

// Price stops in TSh. The first means "no minimum", the last "no maximum".
const PRICE_STOPS = [0, 5e6, 10e6, 20e6, 50e6, 100e6, 200e6, 500e6, 1e9, 2e9, 5e9]

function nearestStop(value?: string, fallback = 0) {
  if (!value) return fallback
  const amount = Number(value)
  let best = 0
  PRICE_STOPS.forEach((stop, index) => {
    if (Math.abs(stop - amount) < Math.abs(PRICE_STOPS[best] - amount)) best = index
  })
  return best
}

// M2/M5's two-thumb price slider. It applies when a thumb is let go.
export function PriceSliderField({ min, max, onCommit }: { min?: string; max?: string; onCommit: (min?: string, max?: string) => void }) {
  const { t, i18n } = useTranslation()
  const last = PRICE_STOPS.length - 1
  const source = `${min}|${max}`
  const [draft, setDraft] = useState({ low: nearestStop(min), high: nearestStop(max, last), source })
  const current = draft.source === source ? draft : { low: nearestStop(min), high: nearestStop(max, last), source }

  function commit() {
    const low = current.low > 0 ? String(PRICE_STOPS[current.low]) : undefined
    const high = current.high < last ? String(PRICE_STOPS[current.high]) : undefined
    if (low !== min || high !== max) onCommit(low, high)
  }

  const label = (index: number) =>
    index === 0 ? 'TSh 0' : index === last ? t('search.noLimit') : formatTshShort(PRICE_STOPS[index], i18n.language)
  const percent = (index: number) => (index / last) * 100
  const thumbs = [
    { key: 'low', value: current.low, name: t('search.min') },
    { key: 'high', value: current.high, name: t('search.max') },
  ] as const

  return (
    <div className="px-1.5">
      <div className="relative h-8">
        <span className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-mist" aria-hidden="true" />
        <span
          aria-hidden="true"
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-navy"
          style={{ left: `${percent(current.low)}%`, right: `${100 - percent(current.high)}%` }}
        />
        {thumbs.map((thumb) => (
          <input
            key={thumb.key}
            type="range"
            min={0}
            max={last}
            step={1}
            value={thumb.value}
            aria-label={thumb.name}
            aria-valuetext={label(thumb.value)}
            onChange={(event) => {
              const value = Number(event.target.value)
              setDraft(
                thumb.key === 'low'
                  ? { ...current, low: Math.min(value, current.high - 1) }
                  : { ...current, high: Math.max(value, current.low + 1) },
              )
            }}
            onPointerUp={commit}
            onKeyUp={commit}
            onBlur={commit}
            className="dual-range"
          />
        ))}
      </div>
      <div className="relative mt-2 h-8">
        {thumbs.map((thumb) => (
          <span
            key={thumb.key}
            className="absolute top-0 rounded-full bg-paper px-2.5 py-1 text-[12px] font-semibold whitespace-nowrap text-navy ring-1 ring-mist"
            style={{
              left: `clamp(0%, ${percent(thumb.value)}%, 100%)`,
              transform: `translateX(${thumb.value === 0 ? '0' : thumb.value === last ? '-100%' : '-50%'})`,
            }}
          >
            {label(thumb.value)}
          </span>
        ))}
      </div>
    </div>
  )
}

// M5's "Rooms" boxes, used for the minimum verification level.
export function LevelBoxesField({ filters, onChange }: FieldProps) {
  const { t } = useTranslation()
  const options = [
    { value: '', label: t('search.any') },
    { value: '1', label: '1+' },
    { value: '2', label: '2+' },
    { value: '3', label: '3' },
  ]
  const chosen = filters.min_verification_level ?? ''
  return (
    <div>
      <div className="grid grid-cols-4 gap-2">
        {options.map((option) => {
          const active = chosen === option.value
          return (
            <button
              key={option.value || 'any'}
              type="button"
              aria-pressed={active}
              onClick={() => onChange({ min_verification_level: option.value || undefined })}
              className={`h-12 rounded-xl text-sm font-semibold transition-colors ${
                active ? 'bg-navy text-white' : 'bg-white text-navy ring-1 ring-mist hover:ring-navy/30'
              }`}
            >
              {option.label}
            </button>
          )
        })}
      </div>
      {chosen && (
        <div className="mt-3">
          <VerificationBadge level={Number(chosen) as 1 | 2 | 3} />
        </div>
      )}
    </div>
  )
}

// M2's "House Type" pills, used for the title type.
function TitleTypePills({ filters, onChange }: FieldProps) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap gap-2">
      {TITLE_TYPES.map((type) => {
        const active = filters.title_type === type
        return (
          <button
            key={type}
            type="button"
            aria-pressed={active}
            onClick={() => onChange({ title_type: active ? undefined : type })}
            className={`h-10 rounded-full px-4 text-[13px] font-semibold transition-colors ${
              active ? 'bg-navy text-white' : 'bg-white text-navy ring-1 ring-mist hover:ring-navy/30'
            }`}
          >
            {t(`market.titleType.${type}`)}
          </button>
        )
      })}
    </div>
  )
}

export function LocationFields({ filters, places, onChange, inline = false }: FieldProps & { places: Places; inline?: boolean }) {
  const { t } = useTranslation()
  return (
    <div className={inline ? 'grid min-w-0 flex-1 grid-cols-3 divide-x divide-mist' : 'space-y-3'}>
      <Select
        label={t('search.region')}
        value={filters.region}
        onChange={(region) => onChange({ region, district: undefined, ward: undefined })}
        options={places.regions}
        bare={inline}
      />
      <Select
        label={t('search.district')}
        value={filters.district}
        onChange={(district) => onChange({ district, ward: undefined })}
        options={places.districts}
        disabledHint={filters.region ? undefined : t('search.chooseRegionFirst')}
        bare={inline}
      />
      <Select
        label={t('search.ward')}
        value={filters.ward}
        onChange={(ward) => onChange({ ward })}
        options={places.wards}
        disabledHint={filters.district ? undefined : t('search.chooseDistrictFirst')}
        bare={inline}
      />
    </div>
  )
}

export function TitleTypeField({ filters, onChange }: FieldProps) {
  const { t } = useTranslation()
  return (
    <Select
      label={t('search.titleType')}
      value={filters.title_type}
      onChange={(title_type) => onChange({ title_type })}
      options={TITLE_TYPES.map((type) => ({ id: type, name: t(`market.titleType.${type}`) }))}
    />
  )
}

export function LevelField({ filters, onChange }: FieldProps) {
  const { t } = useTranslation()
  const name = useId()
  return (
    <div className="space-y-2">
      {(['', '1', '2', '3'] as const).map((level) => {
        const active = (filters.min_verification_level ?? '') === level
        return (
          <label
            key={level || 'any'}
            className={`flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-3 py-2 ring-1 transition-colors ${
              active ? 'bg-gold/10 ring-gold/60' : 'ring-mist hover:ring-navy/30'
            }`}
          >
            <input
              type="radio"
              name={name}
              checked={active}
              onChange={() => onChange({ min_verification_level: level || undefined })}
              className="size-4 accent-gold"
            />
            {level ? (
              <span className="flex flex-wrap items-center gap-2 text-sm text-navy">
                <VerificationBadge level={Number(level) as 1 | 2 | 3} />
                {level !== '3' && <span className="text-muted">{t('search.orHigher')}</span>}
              </span>
            ) : (
              <span className="text-sm text-navy">{t('search.any')}</span>
            )}
          </label>
        )
      })}
    </div>
  )
}

function Select({
  label,
  value,
  onChange,
  options,
  disabledHint,
  bare = false,
}: {
  label: string
  value?: string
  onChange: (value: string | undefined) => void
  options: Place[]
  disabledHint?: string
  // Borderless, for the inline location bar.
  bare?: boolean
}) {
  const { t } = useTranslation()
  const disabled = Boolean(disabledHint)
  return (
    <label className="relative block min-w-0">
      <span className={bare ? 'pointer-events-none absolute top-2 left-4 text-[11px] font-medium text-muted' : 'sr-only'}>
        {label}
      </span>
      <select
        value={value ?? ''}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value || undefined)}
        className={`w-full cursor-pointer appearance-none truncate text-sm text-navy outline-none disabled:cursor-not-allowed disabled:text-muted ${
          bare
            ? 'h-14 rounded-md bg-transparent pt-5 pr-9 pl-4 font-semibold focus-visible:bg-paper'
            : 'h-11 rounded-xl border border-mist bg-white pr-10 pl-3 focus:border-gold focus:ring-4 focus:ring-gold/20 disabled:bg-paper'
        }`}
      >
        <option value="">{disabledHint ?? (bare ? t('search.any') : `${label}: ${t('search.any')}`)}</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
      <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted" />
    </label>
  )
}

// Min and max inputs that apply on blur or Enter, not on every keystroke.
export function RangeField({ min, max, onCommit }: { min?: string; max?: string; onCommit: (min?: string, max?: string) => void }) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const source = `${min}|${max}`
  const [draft, setDraft] = useState({ min: min ?? '', max: max ?? '', source })
  // Follow the URL when it changes elsewhere (a chip removed, filters cleared).
  const current = draft.source === source ? draft : { min: min ?? '', max: max ?? '', source }

  function commit() {
    let low = current.min || undefined
    let high = current.max || undefined
    if (low && high && Number(low) > Number(high)) [low, high] = [high, low]
    if (low !== min || high !== max) onCommit(low, high)
  }

  const display = (value: string) => (value ? formatNumber(value, i18n.language) : '')

  return (
    <div className="grid grid-cols-2 gap-2">
      {(['min', 'max'] as const).map((edge) => (
        <label key={edge} htmlFor={`${id}-${edge}`} className="block">
          <span className="mb-1 block text-xs text-muted">{t(`search.${edge}`)}</span>
          <input
            id={`${id}-${edge}`}
            inputMode="numeric"
            autoComplete="off"
            value={display(current[edge])}
            onChange={(event) => setDraft({ ...current, [edge]: digitsOnly(event.target.value) })}
            onBlur={commit}
            onKeyDown={(event) => event.key === 'Enter' && commit()}
            className="h-11 w-full rounded-xl border border-mist bg-white px-3 text-sm text-navy outline-none focus:border-gold focus:ring-4 focus:ring-gold/20"
          />
        </label>
      ))}
    </div>
  )
}
