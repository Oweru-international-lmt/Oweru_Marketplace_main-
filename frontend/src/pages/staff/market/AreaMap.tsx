import { useEffect, useMemo, useState } from 'react'
import { BANDS } from './data'

// Region outlines: geoBoundaries gbOpen TZA ADM1 (CC BY 4.0), simplified and
// served from /geo. Songwe is inside Mbeya in that release.
type Ring = [number, number][]
type Feature = { properties: { name: string }; geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: Ring[] | Ring[][] } }
type Shape = { name: string; path: string; centre: [number, number]; area: number }

const ALIASES: Record<string, string> = { Songwe: 'Mbeya' }
const WIDTH = 640
const HEIGHT = 640

let outlines: Promise<Feature[]> | null = null
function loadOutlines() {
  outlines ??= fetch('/geo/tz-regions.json')
    .then((response) => (response.ok ? response.json() : Promise.reject(new Error(String(response.status)))))
    .then((data: { features: Feature[] }) => data.features)
  outlines.catch(() => {
    outlines = null
  })
  return outlines
}

export type AreaValue = { name: string; value: number }

// M3: the regions drawn as flat shapes, shaded in three bands, with white
// borders and their names; regions with nothing recorded stay pale.
export function AreaMap({ areas, bandOf, label }: { areas: AreaValue[]; bandOf: (value: number) => 0 | 1 | 2; label: string }) {
  const [features, setFeatures] = useState<Feature[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    loadOutlines().then(
      (loaded) => live && setFeatures(loaded),
      () => live && setFailed(true),
    )
    return () => {
      live = false
    }
  }, [])

  const shapes = useMemo<Shape[]>(() => {
    if (!features) return []
    const polygons = features.map((feature) => ({
      name: feature.properties.name,
      rings: feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates as Ring[]] : (feature.geometry.coordinates as Ring[][]),
    }))
    const points = polygons.flatMap((polygon) => polygon.rings.flatMap((rings) => rings.flat()))
    const lons = points.map(([lon]) => lon)
    const lats = points.map(([, lat]) => lat)
    const [minLon, maxLon, minLat, maxLat] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)]
    const squeeze = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180)
    const scale = Math.min((WIDTH - 20) / ((maxLon - minLon) * squeeze), (HEIGHT - 20) / (maxLat - minLat))
    const offsetX = (WIDTH - (maxLon - minLon) * squeeze * scale) / 2
    const offsetY = (HEIGHT - (maxLat - minLat) * scale) / 2
    const project = ([lon, lat]: [number, number]): [number, number] => [offsetX + (lon - minLon) * squeeze * scale, offsetY + (maxLat - lat) * scale]
    return polygons.map(({ name, rings }) => {
      let largest = 0
      let centre: [number, number] = [0, 0]
      const path = rings
        .map((polygon) =>
          polygon
            .map((ring, index) => {
              const projected = ring.map(project)
              if (index === 0) {
                const xs = projected.map(([x]) => x)
                const ys = projected.map(([, y]) => y)
                const size = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys))
                if (size > largest) {
                  largest = size
                  centre = [(Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2]
                }
              }
              return `M${projected.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join('L')}Z`
            })
            .join(''),
        )
        .join('')
      return { name, path, centre, area: largest }
    })
  }, [features])

  const values = useMemo(() => {
    const out: Record<string, number> = {}
    for (const area of areas) {
      const name = ALIASES[area.name] ?? area.name
      out[name] = (out[name] ?? 0) + area.value
    }
    return out
  }, [areas])

  if (failed) return <p className="py-16 text-center text-[13px] text-muted">{label}</p>
  if (!features) return <div className="h-[420px] animate-pulse rounded-xl bg-paper" />

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="mx-auto h-auto w-full max-w-[560px]" role="img" aria-label={label}>
      {shapes.map((shape) => {
        const value = values[shape.name]
        const band = value ? bandOf(value) : null
        return (
          <path key={shape.name} d={shape.path} fill={band === null ? '#e8ebf2' : BANDS[band]} stroke="#fff" strokeWidth="1.4" strokeLinejoin="round">
            <title>{`${shape.name}: ${(value ?? 0).toLocaleString()}`}</title>
          </path>
        )
      })}
      {shapes
        .filter((shape) => shape.area > 1600)
        .map((shape) => {
          const value = values[shape.name]
          const dark = value !== undefined && bandOf(value) === 0
          return (
            <text key={`label-${shape.name}`} x={shape.centre[0]} y={shape.centre[1]} textAnchor="middle" className={`pointer-events-none text-[11px] italic ${dark ? 'fill-white' : 'fill-[#1e293b]'}`}>
              {shape.name}
              {value ? <tspan x={shape.centre[0]} dy="13" className="font-semibold not-italic">{value.toLocaleString()}</tspan> : null}
            </text>
          )
        })}
    </svg>
  )
}
