import { animate, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { marketApi, type Place } from '../../../lib/marketApi'
import { partnersApi } from '../../../lib/partnersApi'

// Shared by the partners table, its side panels and the coverage map.

export type PartnerStatus = 'INVITED' | 'EXPIRED' | 'AWAITING_APPROVAL' | 'ACTIVE' | 'DEACTIVATED' | 'INACTIVE'

const CHIP: Record<PartnerStatus, string> = {
  INVITED: 'border-[#c9d6f5] bg-[#eef3fd] text-[#3552a8]',
  EXPIRED: 'border-mist bg-paper text-muted',
  AWAITING_APPROVAL: 'border-[#f3d3a6] bg-[#fdf3e2] text-[#b4640a]',
  ACTIVE: 'border-[#bfe3cc] bg-success-soft text-success',
  DEACTIVATED: 'border-[#f2c4c4] bg-danger-soft text-danger',
  INACTIVE: 'border-[#f2c4c4] bg-danger-soft text-danger',
}

// R12: a small outlined chip with a dot.
export function PartnerChip({ status }: { status: PartnerStatus }) {
  const { t } = useTranslation()
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${CHIP[status]}`}>
      <span className="size-1.5 rounded-full bg-current" />
      {t(`partners.status.${status}`)}
    </span>
  )
}

export function Count({ value, className = '' }: { value: number; className?: string }) {
  const reduce = useReducedMotion()
  const node = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const element = node.current
    if (!element) return
    if (reduce) {
      element.textContent = String(value)
      return
    }
    const controls = animate(0, value, { duration: 0.8, ease: [0.22, 1, 0.36, 1], onUpdate: (amount) => (element.textContent = String(Math.round(amount))) })
    return () => controls.stop()
  }, [value, reduce])
  return <span ref={node} className={`tabular-nums ${className}`} aria-label={String(value)} />
}

export function Initials({ name, className = '' }: { name: string; className?: string }) {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
  return <span className={`grid shrink-0 place-items-center rounded-full bg-navy text-[12px] font-semibold text-gold ${className}`}>{letters || '?'}</span>
}

export const fieldClass = 'h-11 w-full rounded-[6px] border border-mist bg-white px-3 text-[14px] text-navy outline-none focus:border-gold focus:ring-2 focus:ring-gold/20 disabled:bg-paper disabled:text-muted'

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-navy">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[12px] text-muted">{hint}</span>}
    </label>
  )
}

function rows<T>(value: T[] | { results: T[] }) {
  return Array.isArray(value) ? value : value.results
}

// Region, then district, then ward, then the approved street or village.
export function LocalityPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { t } = useTranslation()
  const [regions, setRegions] = useState<Place[]>([])
  const [districts, setDistricts] = useState<Place[]>([])
  const [wards, setWards] = useState<Place[]>([])
  const [streets, setStreets] = useState<{ id: string; name: string; kind: string }[]>([])
  const [pick, setPick] = useState({ region: '', district: '', ward: '' })

  useEffect(() => {
    marketApi.regions().then((list) => setRegions(rows(list)), () => setRegions([]))
  }, [])

  function choose(level: 'region' | 'district' | 'ward', id: string) {
    onChange('')
    if (level === 'region') {
      setPick({ region: id, district: '', ward: '' })
      setDistricts([])
      setWards([])
      setStreets([])
      if (id) marketApi.districts(id).then((list) => setDistricts(rows(list)), () => setDistricts([]))
    } else if (level === 'district') {
      setPick((current) => ({ ...current, district: id, ward: '' }))
      setWards([])
      setStreets([])
      if (id) marketApi.wards(id).then((list) => setWards(rows(list)), () => setWards([]))
    } else {
      setPick((current) => ({ ...current, ward: id }))
      setStreets([])
      if (id) partnersApi.localities(id).then((list) => setStreets(rows(list)), () => setStreets([]))
    }
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t('partners.place.region')}>
        <select className={fieldClass} value={pick.region} onChange={(event) => choose('region', event.target.value)}>
          <option value="">{t('partners.place.choose')}</option>
          {regions.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
      </Field>
      <Field label={t('partners.place.district')}>
        <select className={fieldClass} value={pick.district} disabled={!pick.region} onChange={(event) => choose('district', event.target.value)}>
          <option value="">{t('partners.place.choose')}</option>
          {districts.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
      </Field>
      <Field label={t('partners.place.ward')}>
        <select className={fieldClass} value={pick.ward} disabled={!pick.district} onChange={(event) => choose('ward', event.target.value)}>
          <option value="">{t('partners.place.choose')}</option>
          {wards.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
      </Field>
      <Field label={t('partners.place.locality')}>
        <select className={fieldClass} value={value} disabled={!pick.ward} onChange={(event) => onChange(event.target.value)}>
          <option value="">{pick.ward && streets.length === 0 ? t('partners.place.none') : t('partners.place.choose')}</option>
          {streets.map((row) => (
            <option key={row.id} value={row.id}>{`${row.name} (${t(`partners.place.kinds.${row.kind}`)})`}</option>
          ))}
        </select>
      </Field>
    </div>
  )
}
