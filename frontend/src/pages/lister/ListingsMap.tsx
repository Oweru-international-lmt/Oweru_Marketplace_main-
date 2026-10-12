import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { formatTshShort } from '../../lib/format'
import type { ListingRow } from './rows'

// L11's map: each listing as a price pill with a soft halo, recoloured gold.
// The highlighted one (the row under the pointer) turns navy.
export function ListingsMap({ rows, highlighted, onOpen }: { rows: ListingRow[]; highlighted: string | null; onOpen: (listingId: string) => void }) {
  const { t, i18n } = useTranslation()
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const layer = useRef<L.LayerGroup | null>(null)
  const open = useRef(onOpen)

  useEffect(() => {
    open.current = onOpen
  }, [onOpen])

  useEffect(() => {
    if (!element.current) return
    const instance = L.map(element.current, { center: [-6.8, 39.25], zoom: 10, zoomControl: false })
    L.control.zoom({ position: 'bottomright' }).addTo(instance)
    // L11's grey map: the standard OSM tiles, desaturated (see index.css).
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      className: 'map-tiles-muted',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(instance)
    layer.current = L.layerGroup().addTo(instance)
    map.current = instance
    return () => {
      instance.remove()
      map.current = null
      layer.current = null
    }
  }, [])

  // Fit the view to the pins whenever the set of listings changes.
  const pinned = rows.filter((row) => row.property?.pin)
  const pinKey = pinned.map((row) => row.listing.listing_id).join(',')
  useEffect(() => {
    const instance = map.current
    if (!instance || pinned.length === 0) return
    const bounds = L.latLngBounds(pinned.map((row) => [row.property!.pin!.coordinates[1], row.property!.pin!.coordinates[0]] as L.LatLngTuple))
    instance.fitBounds(bounds, { padding: [60, 60], maxZoom: 14 })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refit only when the set changes
  }, [pinKey])

  useEffect(() => {
    const group = layer.current
    if (!group) return
    group.clearLayers()
    for (const row of pinned) {
      const [lng, lat] = row.property!.pin!.coordinates
      const on = row.listing.listing_id === highlighted
      const price = formatTshShort(row.listing.selling_price, i18n.language).replace('TSh ', '')
      const icon = L.divIcon({
        className: '',
        iconSize: [0, 0],
        html: `<span style="position:absolute;transform:translate(-50%,-50%);display:inline-flex;align-items:center;justify-content:center;white-space:nowrap;padding:6px 12px;border-radius:999px;font:600 13px/1 Poppins,system-ui,sans-serif;color:${on ? '#fff' : '#0f172a'};background:${on ? '#0f172a' : '#c89128'};box-shadow:0 0 0 7px ${on ? 'rgba(15,23,42,.18)' : 'rgba(200,145,40,.22)'},0 0 0 14px ${on ? 'rgba(15,23,42,.08)' : 'rgba(200,145,40,.1)'}">${price}</span>`,
      })
      L.marker([lat, lng], { icon, keyboard: true, title: price, zIndexOffset: on ? 1000 : 0 })
        .on('click', () => open.current(row.listing.listing_id))
        .addTo(group)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- pinned follows rows
  }, [rows, highlighted, i18n.language])

  return (
    <div className="relative isolate h-full overflow-hidden rounded-lg border border-mist bg-mist/40">
      <div ref={element} role="application" aria-label={t('lister.listings.map')} className="size-full" />
      <p className="pointer-events-none absolute top-3 left-4 z-[500] text-[22px] font-light text-navy/80">{t('lister.listings.map')}</p>
    </div>
  )
}
