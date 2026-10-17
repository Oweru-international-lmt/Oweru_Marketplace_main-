import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import type { LatLng, PossibleDuplicate } from '../../../lib/staffApi'

export type MapView = 'satellite' | 'map'

// The details strip covers the lower part of the canvas, so the pin sits this
// many pixels above the middle.
const LIFT = 110

function aboveStrip(instance: L.Map, point: LatLng, zoom: number) {
  return instance.unproject(instance.project([point.lat, point.lng], zoom).add([0, LIFT]), zoom)
}
export type CheckMapHandle = { zoomIn: () => void; zoomOut: () => void; recenter: () => void }

const pinIcon = (label: string) =>
  L.divIcon({
    className: '',
    iconSize: [36, 46],
    iconAnchor: [18, 44],
    html: `<div style="position:relative">
      <div style="position:absolute;bottom:52px;left:50%;transform:translateX(-50%);white-space:nowrap;background:rgba(255,255,255,.96);border-radius:10px;padding:7px 11px;box-shadow:0 6px 18px rgba(15,23,42,.25);font:600 13px Poppins,system-ui;color:#0f172a">${label}</div>
      <svg viewBox="0 0 36 46" width="36" height="46" aria-hidden="true" style="filter:drop-shadow(0 6px 8px rgba(15,23,42,.45))">
        <path d="M18 1C8.6 1 1 8.5 1 17.8 1 30 18 45 18 45s17-15 17-27.2C35 8.5 27.4 1 18 1Z" fill="#0f172a"/>
        <circle cx="18" cy="17.5" r="6.5" fill="#e5b972"/>
      </svg></div>`,
  })

// C6's parcel tags: a small white label under each possible duplicate.
const duplicateIcon = (label: string) =>
  L.divIcon({
    className: '',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    html: `<div style="position:relative">
      <span style="display:block;width:22px;height:22px;border-radius:999px;background:rgba(200,145,40,.35);border:2px solid #c89128"></span>
      <span style="position:absolute;top:28px;left:50%;transform:translateX(-50%);white-space:nowrap;background:rgba(255,255,255,.94);border-radius:6px;padding:2px 7px;font:500 11px Poppins,system-ui;color:#0f172a;box-shadow:0 2px 6px rgba(15,23,42,.2)">${label}</span>
    </div>`,
  })

type Props = {
  pin: LatLng
  boundary: LatLng[] | null
  duplicates: PossibleDuplicate[]
  showDuplicates: boolean
  view: MapView
  pinLabel: string
  label: string
}

// Satellite imagery (Esri World Imagery) with place names over it, or the
// street map; the property's pin, its boundary when drawn, and possible
// duplicates as labelled rings.
export const CheckMap = forwardRef<CheckMapHandle, Props>(function CheckMap({ pin, boundary, duplicates, showDuplicates, view, pinLabel, label }, ref) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const layers = useRef<{ base?: L.TileLayer; overlays: L.LayerGroup; marks: L.LayerGroup } | null>(null)
  const home = useRef(pin)

  useEffect(() => {
    home.current = pin
  }, [pin])

  useImperativeHandle(ref, () => ({
    zoomIn: () => map.current?.zoomIn(),
    zoomOut: () => map.current?.zoomOut(),
    recenter: () => map.current?.flyTo(aboveStrip(map.current, home.current, 18), 18, { duration: 0.6 }),
  }))

  useEffect(() => {
    if (!element.current) return
    const instance = L.map(element.current, { zoomControl: false, attributionControl: true })
    instance.setView(aboveStrip(instance, home.current, 18), 18)
    instance.attributionControl.setPosition('topright')
    layers.current = { overlays: L.layerGroup().addTo(instance), marks: L.layerGroup().addTo(instance) }
    map.current = instance
    return () => {
      instance.remove()
      map.current = null
      layers.current = null
    }
  }, [])

  useEffect(() => {
    const instance = map.current
    const current = layers.current
    if (!instance || !current) return
    if (current.base) instance.removeLayer(current.base)
    current.overlays.clearLayers()
    if (view === 'satellite') {
      current.base = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics',
      }).addTo(instance)
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
      }).addTo(current.overlays)
    } else {
      current.base = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(instance)
    }
    current.base.bringToBack()
  }, [view])

  useEffect(() => {
    const current = layers.current
    if (!current) return
    current.marks.clearLayers()
    if (boundary && boundary.length > 2) {
      L.polygon(boundary.map((point) => [point.lat, point.lng] as L.LatLngTuple), {
        color: '#e5b972',
        weight: 3,
        fillColor: '#c89128',
        fillOpacity: 0.28,
      }).addTo(current.marks)
    }
    if (showDuplicates) {
      for (const duplicate of duplicates) {
        if (!duplicate.pin) continue
        L.marker([duplicate.pin.lat, duplicate.pin.lng], { icon: duplicateIcon(duplicate.property_id), keyboard: false }).addTo(current.marks)
      }
    }
    L.marker([pin.lat, pin.lng], { icon: pinIcon(pinLabel), keyboard: false, title: pinLabel }).addTo(current.marks)
  }, [pin, boundary, duplicates, showDuplicates, pinLabel])

  return <div ref={element} role="img" aria-label={label} className="absolute inset-0 bg-[#1f2a1d]" />
})
