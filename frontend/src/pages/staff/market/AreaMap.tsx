import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'
import { BANDS } from './data'

// Regional centres (the region's administrative town). The panel reports by
// region only, so each region is one shaded area marker; no property pins.
const CENTRES: Record<string, [number, number]> = {
  Arusha: [-3.387, 36.683],
  'Dar es Salaam': [-6.792, 39.208],
  Dodoma: [-6.163, 35.752],
  Geita: [-2.872, 32.23],
  Iringa: [-7.77, 35.69],
  Kagera: [-1.332, 31.812],
  Katavi: [-6.35, 31.067],
  Kigoma: [-4.877, 29.627],
  Kilimanjaro: [-3.335, 37.34],
  Lindi: [-9.997, 39.714],
  Manyara: [-4.212, 35.748],
  Mara: [-1.5, 33.8],
  Mbeya: [-8.909, 33.461],
  Morogoro: [-6.828, 37.659],
  Mtwara: [-10.267, 40.183],
  Mwanza: [-2.516, 32.918],
  Njombe: [-9.333, 34.767],
  Pwani: [-6.767, 38.917],
  Rukwa: [-7.967, 31.617],
  Ruvuma: [-10.683, 35.65],
  Shinyanga: [-3.662, 33.423],
  Simiyu: [-2.8, 33.983],
  Singida: [-4.817, 34.75],
  Songwe: [-9.1, 32.933],
  Tabora: [-5.017, 32.8],
  Tanga: [-5.069, 39.099],
  'Mjini Magharibi': [-6.166, 39.203],
  'Kaskazini Unguja': [-5.9, 39.28],
  'Kusini Unguja': [-6.3, 39.45],
  'Kaskazini Pemba': [-4.95, 39.75],
  'Kusini Pemba': [-5.3, 39.75],
}

export type AreaValue = { name: string; value: number }

// M3: areas shaded in three bands with their names; the legend sits under the map.
export function AreaMap({ areas, bandOf, label }: { areas: AreaValue[]; bandOf: (value: number) => 0 | 1 | 2; label: string }) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const layer = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!element.current) return
    const instance = L.map(element.current, { center: [-6.3, 35.0], zoom: 5.4, zoomSnap: 0.2, zoomControl: false, attributionControl: true, scrollWheelZoom: false })
    instance.attributionControl.setPosition('bottomright')
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 12,
      attribution: '&copy; OpenStreetMap',
      className: 'oweru-faded-tiles',
    }).addTo(instance)
    layer.current = L.layerGroup().addTo(instance)
    map.current = instance
    return () => {
      instance.remove()
      map.current = null
      layer.current = null
    }
  }, [])

  useEffect(() => {
    const group = layer.current
    if (!group) return
    group.clearLayers()
    const max = Math.max(...areas.map((area) => area.value), 1)
    for (const area of areas) {
      const centre = CENTRES[area.name]
      if (!centre) continue
      const colour = BANDS[bandOf(area.value)]
      L.circle(centre, { radius: 55_000 + (area.value / max) * 85_000, color: '#ffffff', weight: 2, fillColor: colour, fillOpacity: 0.92 }).addTo(group)
      L.marker(centre, {
        interactive: false,
        keyboard: false,
        icon: L.divIcon({
          className: '',
          iconSize: [120, 34],
          iconAnchor: [60, 17],
          html: `<div style="text-align:center;font:600 11px Poppins,system-ui;color:${bandOf(area.value) === 0 ? '#fff' : '#0f172a'};line-height:1.15;text-shadow:${bandOf(area.value) === 0 ? 'none' : '0 0 2px #fff'}">${area.name}<br><span style="font-weight:500">${area.value.toLocaleString()}</span></div>`,
        }),
      }).addTo(group)
    }
  }, [areas, bandOf])

  return <div ref={element} role="img" aria-label={label} className="isolate h-[420px] w-full rounded-xl bg-[#f6f7f9] [&_.oweru-faded-tiles]:opacity-40 [&_.oweru-faded-tiles]:grayscale" />
}
