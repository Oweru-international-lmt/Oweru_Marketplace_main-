import { useId, useMemo, useState } from 'react'

// Small SVG charts for the market panel, after M1, M2, M4 and M6. Text always
// uses the ink colours; series colours only mark the data.

export const NAVY = '#0f172a'
export const GOLD = '#c89128'
export const GOLD_SOFT = '#e5b972'
export const SLATE = '#94a3b8'

// A smooth path through the points (monotone, so it never overshoots).
function smooth(points: [number, number][]) {
  if (points.length < 2) return points.length ? `M${points[0][0]},${points[0][1]}` : ''
  let path = `M${points[0][0]},${points[0][1]}`
  for (let index = 0; index < points.length - 1; index++) {
    const [x0, y0] = points[index]
    const [x1, y1] = points[index + 1]
    const mid = (x1 - x0) / 2
    path += ` C${x0 + mid},${y0} ${x1 - mid},${y1} ${x1},${y1}`
  }
  return path
}

function niceMax(value: number) {
  if (value <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  const step = [1, 2, 2.5, 5, 10].find((candidate) => candidate * power >= value / 4) ?? 10
  return Math.ceil(value / (step * power)) * step * power
}

// M2: one solid series with a soft area and one dashed series, a dashed
// guide and a dark value pill on the hovered month.
export function TrendLine({ labels, solid, dashed, format, height = 260, ariaLabel }: {
  labels: string[]
  solid: (number | null)[]
  dashed: (number | null)[]
  format: (value: number) => string
  height?: number
  ariaLabel: string
}) {
  const id = useId()
  const [hover, setHover] = useState<number | null>(null)
  const width = 640
  const pad = { left: 56, right: 12, top: 28, bottom: 30 }
  const values = [...solid, ...dashed].filter((value): value is number => value !== null)
  const max = niceMax(Math.max(...values, 0) * 1.08)
  const x = (index: number) => pad.left + (labels.length < 2 ? 0 : (index / (labels.length - 1)) * (width - pad.left - pad.right))
  const y = (value: number) => pad.top + (1 - value / max) * (height - pad.top - pad.bottom)
  const line = (series: (number | null)[]) => smooth(series.flatMap((value, index) => (value === null ? [] : [[x(index), y(value)] as [number, number]])))
  const solidPath = line(solid)
  const firstSolid = solid.findIndex((value) => value !== null)
  const lastSolid = solid.length - 1 - [...solid].reverse().findIndex((value) => value !== null)
  const area = solidPath && firstSolid >= 0 ? `${solidPath} L${x(lastSolid)},${y(0)} L${x(firstSolid)},${y(0)} Z` : ''
  const ticks = [0, 0.2, 0.4, 0.6, 0.8, 1].map((share) => share * max)
  const active = hover ?? (solid.length ? solid.reduce<number>((best, value, index) => ((value ?? -1) > (solid[best] ?? -1) ? index : best), 0) : null)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={ariaLabel} onMouseLeave={() => setHover(null)}>
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={NAVY} stopOpacity="0.14" />
          <stop offset="1" stopColor={NAVY} stopOpacity="0.01" />
        </linearGradient>
      </defs>
      {ticks.map((tick) => (
        <g key={tick}>
          <line x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} stroke="#eef0f3" />
          <text x={pad.left - 10} y={y(tick) + 4} textAnchor="end" className="fill-[#64748b] text-[11px]">{format(tick)}</text>
        </g>
      ))}
      {labels.map((label, index) => (
        <text key={label + index} x={x(index)} y={height - 8} textAnchor="middle" className="fill-[#64748b] text-[11px]">{label}</text>
      ))}
      {area && <path d={area} fill={`url(#${id}-fill)`} />}
      <path d={line(dashed)} fill="none" stroke={GOLD} strokeWidth="2" strokeDasharray="4 4" strokeLinecap="round" />
      <path d={solidPath} fill="none" stroke={NAVY} strokeWidth="2.5" strokeLinecap="round" />
      {active !== null && solid[active] !== null && solid[active] !== undefined && (
        <g>
          <line x1={x(active)} x2={x(active)} y1={y(solid[active] as number)} y2={y(0)} stroke="#94a3b8" strokeDasharray="3 3" />
          <circle cx={x(active)} cy={y(solid[active] as number)} r="4.5" fill={NAVY} stroke="#fff" strokeWidth="2" />
          <g transform={`translate(${Math.min(Math.max(x(active), pad.left + 34), width - 46)},${y(solid[active] as number) - 16})`}>
            <rect x="-38" y="-17" width="76" height="22" rx="6" fill={NAVY} />
            <text y="-2" textAnchor="middle" className="fill-white text-[11px] font-semibold">{format(solid[active] as number)}</text>
          </g>
        </g>
      )}
      {labels.map((label, index) => (
        <rect key={`hit-${label}-${index}`} x={x(index) - (width / labels.length) / 2} y={0} width={width / Math.max(labels.length, 1)} height={height} fill="transparent" onMouseEnter={() => setHover(index)} />
      ))}
    </svg>
  )
}

// M2: a donut with a gap between segments and the headline share inside.
export function Donut({ parts, center, size = 190 }: { parts: { label: string; value: number; color: string }[]; center: string; size?: number }) {
  const total = parts.reduce((sum, part) => sum + part.value, 0)
  const radius = 38
  const circumference = 2 * Math.PI * radius
  let offset = 0
  return (
    <div className="relative mx-auto" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="size-full -rotate-90" aria-hidden="true">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#f1f1f3" strokeWidth="22" />
        {total > 0 &&
          parts.map((part) => {
            const length = (part.value / total) * circumference
            const dash = Math.max(length - 1.5, 0)
            const element = (
              <circle key={part.label} cx="50" cy="50" r={radius} fill="none" stroke={part.color} strokeWidth="22" strokeDasharray={`${dash} ${circumference - dash}`} strokeDashoffset={-offset} />
            )
            offset += length
            return element
          })}
      </svg>
      <span className="absolute inset-0 grid place-items-center text-[30px] font-semibold text-navy tabular-nums">{center}</span>
    </div>
  )
}

// M1: a pale bar per month with the second series inside it; the top month is
// filled with gold stripes.
export function GhostBars({ labels, outer, inner, format, highlight }: { labels: string[]; outer: number[]; inner: number[]; format: (value: number) => string; highlight: number }) {
  const id = useId()
  const width = 620
  const height = 250
  const pad = { left: 44, right: 8, top: 10, bottom: 28 }
  const max = niceMax(Math.max(...outer, ...inner, 0))
  const slot = (width - pad.left - pad.right) / Math.max(labels.length, 1)
  const barWidth = Math.min(56, slot * 0.66)
  const y = (value: number) => pad.top + (1 - value / max) * (height - pad.top - pad.bottom)
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" aria-hidden="true">
      <defs>
        <pattern id={`${id}-stripes`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="8" height="8" fill={GOLD} />
          <rect width="3" height="8" fill={GOLD_SOFT} />
        </pattern>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map((share) => (
        <g key={share}>
          <line x1={pad.left} x2={width - pad.right} y1={y(share * max)} y2={y(share * max)} stroke="#eef0f3" strokeDasharray="4 4" />
          <text x={pad.left - 8} y={y(share * max) + 4} textAnchor="end" className="fill-[#64748b] text-[11px]">{format(share * max)}</text>
        </g>
      ))}
      {labels.map((label, index) => {
        const cx = pad.left + slot * index + slot / 2
        const top = y(outer[index] ?? 0)
        const innerTop = y(inner[index] ?? 0)
        const on = index === highlight
        return (
          <g key={label + index}>
            <rect x={cx - barWidth / 2} y={top} width={barWidth} height={y(0) - top} rx="12" fill="#f1f1f3" />
            <rect x={cx - barWidth / 2} y={innerTop} width={barWidth} height={Math.max(y(0) - innerTop, 0)} rx="12" fill={on ? `url(#${id}-stripes)` : '#e7e7ea'} />
            <line x1={cx - barWidth / 4} x2={cx + barWidth / 4} y1={innerTop + 6} y2={innerTop + 6} stroke="#fff" strokeWidth="2.5" strokeLinecap="round" opacity={inner[index] ? 1 : 0} />
            <text x={cx} y={height - 8} textAnchor="middle" className="fill-[#475569] text-[12px]">{label}</text>
          </g>
        )
      })}
    </svg>
  )
}

// M1: a row of thin rounded segments, the share of them filled.
export function SegmentBar({ share, color, segments = 30 }: { share: number; color: string; segments?: number }) {
  const filled = Math.round(Math.min(Math.max(share, 0), 1) * segments)
  return (
    <span className="flex h-9 gap-[3px]" aria-hidden="true">
      {Array.from({ length: segments }, (_, index) => (
        <span key={index} className="h-full flex-1 rounded-full" style={{ backgroundColor: index < filled ? color : '#ececef' }} />
      ))}
    </span>
  )
}

export function Sparkline({ values, color = NAVY, height = 44, fill = true }: { values: number[]; color?: string; height?: number; fill?: boolean }) {
  const id = useId()
  const width = 160
  const max = Math.max(...values, 1)
  const points = values.map((value, index) => [values.length < 2 ? width / 2 : (index / (values.length - 1)) * width, height - 4 - (value / max) * (height - 10)] as [number, number])
  const path = smooth(points)
  const last = points[points.length - 1]
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="block h-full w-full overflow-visible" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-f`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.18" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && path && <path d={`${path} L${width},${height} L0,${height} Z`} fill={`url(#${id}-f)`} />}
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
      {last && <circle cx={last[0]} cy={last[1]} r="3.5" fill="#fff" stroke={color} strokeWidth="2" />}
    </svg>
  )
}

// M4: step columns with their figures, falling bars and a soft band joining them.
export function StepFunnel({ steps }: { steps: { label: string; value: number; colour: string }[] }) {
  const top = steps[0]?.value || 1
  const shares = steps.map((step) => step.value / top)
  const band = useMemo(() => {
    const width = 100 / steps.length
    const points = shares.map((share, index) => `${index * width + width * 0.35},${100 - share * 100}`)
    return `M0,100 L0,${100 - (shares[0] ?? 0) * 100} L${points.join(' L')} L100,${100 - (shares[shares.length - 1] ?? 0) * 100} L100,100 Z`
  }, [shares, steps.length])
  return (
    <div className="relative">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="pointer-events-none absolute inset-x-0 bottom-0 h-[150px] w-full" aria-hidden="true">
        <path d={band} fill="#e8ebf2" opacity="0.7" />
      </svg>
      <ol className="relative grid" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
        {steps.map((step, index) => (
          <li key={step.label} className={`flex min-h-[250px] flex-col px-3 ${index ? 'border-l border-mist' : ''}`}>
            <p className="text-[13px] font-medium text-navy">{index + 1}. {step.label}</p>
            <p className="mt-1 text-[26px] leading-none font-semibold text-navy tabular-nums">{step.value.toLocaleString()}</p>
            <p className="mt-1 text-[12.5px] text-muted tabular-nums">{Math.round(shares[index] * 1000) / 10}%</p>
            <div className="mt-auto flex h-[150px] items-end">
              <span className="block w-[46%] rounded-t-[3px]" style={{ height: `${Math.max(shares[index] * 100, 3)}%`, backgroundColor: step.colour }} />
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

// M3 and M5 style: grouped bars per area, two series side by side.
export function GroupedBars({ labels, first, second, colours }: { labels: string[]; first: number[]; second: number[]; colours: [string, string] }) {
  const width = 520
  const height = 220
  const pad = { left: 40, right: 6, top: 8, bottom: 30 }
  const max = niceMax(Math.max(...first, ...second, 0))
  const slot = (width - pad.left - pad.right) / Math.max(labels.length, 1)
  const bar = Math.min(22, slot * 0.32)
  const y = (value: number) => pad.top + (1 - value / max) * (height - pad.top - pad.bottom)
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" aria-hidden="true">
      {[0, 0.25, 0.5, 0.75, 1].map((share) => (
        <g key={share}>
          <line x1={pad.left} x2={width - pad.right} y1={y(share * max)} y2={y(share * max)} stroke="#eef0f3" />
          <text x={pad.left - 8} y={y(share * max) + 4} textAnchor="end" className="fill-[#64748b] text-[10.5px]">{Math.round(share * max).toLocaleString()}</text>
        </g>
      ))}
      {labels.map((label, index) => {
        const cx = pad.left + slot * index + slot / 2
        return (
          <g key={label}>
            <rect x={cx - bar - 1} y={y(first[index])} width={bar} height={y(0) - y(first[index])} fill={colours[0]} rx="2" />
            <rect x={cx + 1} y={y(second[index])} width={bar} height={y(0) - y(second[index])} fill={colours[1]} rx="2" />
            <text x={cx} y={height - 10} textAnchor="middle" className="fill-[#475569] text-[11px]">{label.length > 12 ? `${label.slice(0, 11)}…` : label}</text>
          </g>
        )
      })}
    </svg>
  )
}

// M3: two plain lines over the months.
export function TwoLines({ labels, first, second, colours }: { labels: string[]; first: number[]; second: number[]; colours: [string, string] }) {
  const width = 520
  const height = 200
  const pad = { left: 44, right: 8, top: 10, bottom: 26 }
  const max = niceMax(Math.max(...first, ...second, 0))
  const x = (index: number) => pad.left + (labels.length < 2 ? 0 : (index / (labels.length - 1)) * (width - pad.left - pad.right))
  const y = (value: number) => pad.top + (1 - value / max) * (height - pad.top - pad.bottom)
  const path = (series: number[]) => smooth(series.map((value, index) => [x(index), y(value)] as [number, number]))
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" aria-hidden="true">
      {[0, 0.25, 0.5, 0.75, 1].map((share) => (
        <g key={share}>
          <line x1={pad.left} x2={width - pad.right} y1={y(share * max)} y2={y(share * max)} stroke="#eef0f3" />
          <text x={pad.left - 8} y={y(share * max) + 4} textAnchor="end" className="fill-[#64748b] text-[10.5px]">{Math.round(share * max).toLocaleString()}</text>
        </g>
      ))}
      {labels.map((label, index) => (
        <text key={label + index} x={x(index)} y={height - 6} textAnchor="middle" className="fill-[#64748b] text-[10.5px]">{label}</text>
      ))}
      <path d={path(first)} fill="none" stroke={colours[0]} strokeWidth="2" />
      <path d={path(second)} fill="none" stroke={colours[1]} strokeWidth="2" />
    </svg>
  )
}
