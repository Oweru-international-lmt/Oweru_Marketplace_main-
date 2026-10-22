import L from 'leaflet'

// Free imagery only (project decision D2). With a free ArcGIS Location
// Platform key the tiles come through Esri's keyed service (2,000,000 free
// tiles a month); without one, development falls back to the public service.
// "Powered by Esri" must stay visible on every map.
const ESRI_KEY = import.meta.env.VITE_ESRI_API_KEY || ''

const IMAGERY = ESRI_KEY
  ? `https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token=${ESRI_KEY}`
  : 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'

const LABELS = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
const STREETS = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'

const ATTRIBUTION = 'Powered by <a href="https://www.esri.com" target="_blank" rel="noopener">Esri</a> &middot; Imagery &copy; Esri, Maxar, Earthstar Geographics'

export function satelliteLayer(): L.TileLayer {
  return L.tileLayer(IMAGERY, { maxZoom: 20, maxNativeZoom: 19, attribution: ATTRIBUTION })
}

export function placeLabelsLayer(): L.TileLayer {
  return L.tileLayer(LABELS, { maxZoom: 20, maxNativeZoom: 19 })
}

export function streetLayer(): L.TileLayer {
  return L.tileLayer(STREETS, { maxZoom: 20, maxNativeZoom: 19, attribution: 'Powered by <a href="https://www.esri.com" target="_blank" rel="noopener">Esri</a>' })
}

// Polygon area in square metres on the WGS84 sphere (as Leaflet.draw does).
// The server measures the final area with PostGIS; this is the live estimate.
export function ringArea(points: [number, number][]): number {
  if (points.length < 3) return 0
  const radius = 6378137
  const rad = Math.PI / 180
  let area = 0
  for (let index = 0; index < points.length; index++) {
    const [lng1, lat1] = points[index]
    const [lng2, lat2] = points[(index + 1) % points.length]
    area += (lng2 - lng1) * rad * (2 + Math.sin(lat1 * rad) + Math.sin(lat2 * rad))
  }
  return Math.abs((area * radius * radius) / 2)
}

export function ringPerimeter(points: [number, number][]): number {
  if (points.length < 2) return 0
  let total = 0
  for (let index = 0; index < points.length; index++) {
    const [lng1, lat1] = points[index]
    const [lng2, lat2] = points[(index + 1) % points.length]
    total += L.latLng(lat1, lng1).distanceTo(L.latLng(lat2, lng2))
  }
  return total
}
