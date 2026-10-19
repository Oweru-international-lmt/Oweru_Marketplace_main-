import type { PanelRow } from '../../../lib/panelApi'

// Turns the panel's per-area cells into the figures each section shows. All
// sums stay by area and category; nothing here can identify a person.

export const CATEGORIES = ['LAND', 'HOUSE', 'COMMERCIAL'] as const
export const STAGES = ['NEW', 'CONTACTED', 'VIEWING', 'CLOSING', 'WON'] as const
// The map's three shading bands, darkest for the busiest areas.
export const BANDS = ['#0f172a', '#c89128', '#e5c98f'] as const

const num = (value: unknown) => (typeof value === 'number' && Number.isFinite(value) ? value : 0)

function addCounts(into: Record<string, number>, from: unknown) {
  if (!from || typeof from !== 'object') return
  for (const [key, value] of Object.entries(from as Record<string, unknown>)) into[key] = (into[key] ?? 0) + num(value)
}

export function byKind(rows: PanelRow[], kind: PanelRow['kind']) {
  return rows.filter((row) => row.kind === kind)
}

// The latest and earliest stock snapshot in the range.
export function stockDays(rows: PanelRow[]) {
  const days = [...new Set(byKind(rows, 'STOCK').map((row) => row.day))].sort()
  return { first: days[0] ?? null, last: days[days.length - 1] ?? null, all: days }
}

export function stockOn(rows: PanelRow[], day: string | null) {
  return day ? byKind(rows, 'STOCK').filter((row) => row.day === day) : []
}

// Count-weighted average of the cells' averages, and the count-weighted median
// of the cells' medians (the panel never returns individual prices).
export function priceStats(rows: PanelRow[], field: 'selling_price' | 'price_per_sqm') {
  let total = 0
  let count = 0
  const medians: { value: number; weight: number }[] = []
  for (const row of rows) {
    const stats = row.metrics[field]
    if (!stats || !stats.count) continue
    total += num(stats.average) * stats.count
    count += stats.count
    if (stats.median !== null) medians.push({ value: stats.median, weight: stats.count })
  }
  medians.sort((a, b) => a.value - b.value)
  let seen = 0
  let median: number | null = null
  for (const item of medians) {
    seen += item.weight
    if (seen >= count / 2) {
      median = item.value
      break
    }
  }
  return { average: count ? total / count : null, median, count }
}

export function sum(rows: PanelRow[], field: string) {
  return rows.reduce((total, row) => total + num(row.metrics[field]), 0)
}

export function counts(rows: PanelRow[], field: string) {
  const out: Record<string, number> = {}
  for (const row of rows) addCounts(out, row.metrics[field])
  return out
}

export function monthKey(day: string) {
  return day.slice(0, 7)
}

// Activity by calendar month, oldest first.
export function monthly<F extends string>(rows: PanelRow[], fields: F[]): ({ month: string } & Record<F, number>)[] {
  const months = new Map<string, Record<string, number>>()
  for (const row of byKind(rows, 'ACTIVITY')) {
    const key = monthKey(row.day)
    const entry = months.get(key) ?? Object.fromEntries(fields.map((field) => [field, 0]))
    for (const field of fields) entry[field] += num(row.metrics[field])
    months.set(key, entry)
  }
  return [...months.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, values]) => ({ month, ...values }) as { month: string } & Record<F, number>)
}

// Average and median selling price per month from the MONTHLY snapshots.
export function priceTrend(rows: PanelRow[]) {
  const months = new Map<string, PanelRow[]>()
  for (const row of byKind(rows, 'MONTHLY')) months.set(monthKey(row.day), [...(months.get(monthKey(row.day)) ?? []), row])
  return [...months.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, cells]) => ({ month, ...priceStats(cells, 'selling_price') }))
}

export function byRegion(rows: PanelRow[], value: (row: PanelRow) => number) {
  const out: Record<string, number> = {}
  for (const row of rows) if (row.region) out[row.region] = (out[row.region] ?? 0) + value(row)
  return out
}

export function percentChange(now: number, before: number) {
  if (!before) return null
  return ((now - before) / before) * 100
}

// Every source tag with what it brought, across the activity cells.
export function sources(rows: PanelRow[]) {
  const activity = byKind(rows, 'ACTIVITY')
  const tags: Record<string, { tag: string; searches: number; views: number; enquiries: number; won: number }> = {}
  const add = (field: string, key: 'searches' | 'views' | 'enquiries' | 'won') => {
    for (const [tag, value] of Object.entries(counts(activity, field))) {
      tags[tag] ??= { tag, searches: 0, views: 0, enquiries: 0, won: 0 }
      tags[tag][key] += value
    }
  }
  add('sources_search', 'searches')
  add('sources_view', 'views')
  add('sources_enquiry', 'enquiries')
  add('sources_won', 'won')
  return Object.values(tags).sort((a, b) => b.views + b.searches - (a.views + a.searches))
}

// One tag's visits by month, and by region, for the inspect panel.
export function tagDetail(rows: PanelRow[], tag: string) {
  const activity = byKind(rows, 'ACTIVITY')
  const months = new Map<string, number>()
  const regions: Record<string, number> = {}
  for (const row of activity) {
    const value = num((row.metrics.sources_view as Record<string, number> | undefined)?.[tag]) + num((row.metrics.sources_search as Record<string, number> | undefined)?.[tag])
    if (!value) continue
    months.set(monthKey(row.day), (months.get(monthKey(row.day)) ?? 0) + value)
    if (row.region) regions[row.region] = (regions[row.region] ?? 0) + value
  }
  return {
    months: [...months.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([month, value]) => ({ month, value })),
    regions: Object.entries(regions).sort(([, a], [, b]) => b - a),
  }
}

export function sourceKind(tag: string): 'campaign' | 'banner' | 'featured' | 'other' {
  if (tag === 'featured') return 'featured'
  if (tag.startsWith('banner') || tag.startsWith('guide')) return 'banner'
  if (tag.startsWith('newsletter') || tag.includes('campaign')) return 'campaign'
  return 'other'
}

export function isoDay(date: Date) {
  return date.toISOString().slice(0, 10)
}
