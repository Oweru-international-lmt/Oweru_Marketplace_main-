import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MapPinIcon } from './icons'

// [longitude, latitude], the GeoJSON order the API expects.
export type LngLat = [number, number]

// Most listings are in and around Dar es Salaam.
const START: L.LatLngTuple = [-6.8, 39.25]

const PIN = L.divIcon({
  className: '',
  iconSize: [36, 46],
  iconAnchor: [18, 44],
  html: `<svg viewBox="0 0 36 46" width="36" height="46" aria-hidden="true" style="filter:drop-shadow(0 6px 8px rgba(15,23,42,.35))">
    <path d="M18 1C8.6 1 1 8.5 1 17.8 1 30 18 45 18 45s17-15 17-27.2C35 8.5 27.4 1 18 1Z" fill="#0f172a"/>
    <circle cx="18" cy="17.5" r="6.5" fill="#e5b972"/>
  </svg>`,
})

type Props = {
  value: LngLat | null
  onChange: (value: LngLat) => void
  invalid?: boolean
  describedBy?: string
  // "bare" is the map alone, filling `mapClassName`; the page supplies its own
  // controls (the phone sheet). "dark" suits the navy step form.
  bare?: boolean
  tone?: 'light' | 'dark'
  mapClassName?: string
}

// Tap the map, or drag the pin, to mark the property. Keyboard users pan with
// the arrow keys and pin the centre with the button below the map.
export function MapPicker({ value, onChange, invalid, describedBy, bare = false, tone = 'light', mapClassName = 'h-[300px] sm:h-[380px]' }: Props) {
  const { t } = useTranslation()
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const marker = useRef<L.Marker | null>(null)
  const change = useRef(onChange)
  // A map created after the pin was dropped opens on the pin.
  const fresh = useRef(true)
  const bareAtStart = useRef(bare)
  const [locating, setLocating] = useState(false)
  const [locateError, setLocateError] = useState(false)

  useEffect(() => {
    change.current = onChange
  }, [onChange])

  useEffect(() => {
    if (!element.current) return
    const instance = L.map(element.current, { center: START, zoom: 11, zoomControl: false, attributionControl: true })
    L.control.zoom({ position: 'topright' }).addTo(instance)
    // On the bare map a sheet covers the bottom; the OSM credit must stay visible.
    if (bareAtStart.current) instance.attributionControl.setPosition('topleft')
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(instance)
    instance.on('click', (event: L.LeafletMouseEvent) => change.current([event.latlng.lng, event.latlng.lat]))
    map.current = instance
    fresh.current = true
    return () => {
      instance.remove()
      map.current = null
      marker.current = null
    }
  }, [])

  // Keep the pin in step with the form value.
  useEffect(() => {
    const instance = map.current
    if (!instance) return
    if (!value) {
      fresh.current = false
      marker.current?.remove()
      marker.current = null
      return
    }
    const position: L.LatLngTuple = [value[1], value[0]]
    // A new map, or a pin set from outside (the phone's location), may not show it.
    if (fresh.current || !instance.getBounds().contains(position)) instance.setView(position, Math.max(instance.getZoom(), 16))
    fresh.current = false
    if (marker.current) {
      marker.current.setLatLng(position)
      return
    }
    const pin = L.marker(position, { icon: PIN, draggable: true, keyboard: false }).addTo(instance)
    pin.on('dragend', () => {
      const point = pin.getLatLng()
      change.current([point.lng, point.lat])
    })
    marker.current = pin
  }, [value])

  function locate() {
    if (!('geolocation' in navigator)) {
      setLocateError(true)
      return
    }
    setLocating(true)
    setLocateError(false)
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocating(false)
        change.current([coords.longitude, coords.latitude])
        map.current?.flyTo([coords.latitude, coords.longitude], 17, { duration: 0.8 })
      },
      () => {
        setLocating(false)
        setLocateError(true)
      },
      { enableHighAccuracy: true, timeout: 15000 },
    )
  }

  function pinCentre() {
    const centre = map.current?.getCenter()
    if (centre) change.current([centre.lng, centre.lat])
  }

  const dark = tone === 'dark'
  if (bare) {
    return <div ref={element} role="application" aria-label={t('freeCheck.mapLabel')} aria-describedby={describedBy} className={`isolate w-full bg-mist ${mapClassName}`} />
  }

  return (
    <div>
      <div
        className={`relative isolate overflow-hidden rounded-2xl ring-1 ${invalid ? 'ring-2 ring-danger' : dark ? 'ring-white/15' : 'ring-mist'}`}
        aria-describedby={describedBy}
      >
        <div
          ref={element}
          role="application"
          aria-label={t('freeCheck.mapLabel')}
          className={`w-full bg-mist ${mapClassName}`}
        />
        {!value && (
          <p className="pointer-events-none absolute inset-x-3 top-3 z-[500] mx-auto w-fit rounded-full bg-navy/90 px-4 py-2 text-center text-xs font-medium text-white shadow-card sm:text-sm">
            {t('freeCheck.mapHint')}
          </p>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={locate}
          disabled={locating}
          aria-busy={locating || undefined}
          className={`inline-flex h-11 items-center gap-2 rounded-full px-4 text-sm font-semibold transition-colors disabled:opacity-70 ${
            dark ? 'bg-gold text-navy hover:bg-gold-light' : 'bg-navy text-white hover:bg-navy-soft'
          }`}
        >
          <MapPinIcon className="size-4" />
          {locating ? t('freeCheck.locating') : t('freeCheck.useLocation')}
        </button>
        <button
          type="button"
          onClick={pinCentre}
          className={`inline-flex h-11 items-center rounded-full px-4 text-sm font-semibold ring-1 transition-colors ${
            dark ? 'bg-white/[0.06] text-white ring-white/20 hover:ring-white/40' : 'bg-white text-navy ring-mist hover:ring-navy/30'
          }`}
        >
          {t('freeCheck.pinCentre')}
        </button>
      </div>
      {locateError && <p className={`mt-2 text-sm ${dark ? 'text-[#ffb3a6]' : 'text-danger'}`}>{t('freeCheck.locateFailed')}</p>}
    </div>
  )
}
