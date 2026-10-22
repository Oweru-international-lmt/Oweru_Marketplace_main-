import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { AlertIcon, ArrowLeftIcon, CameraIcon, CheckIcon, ImageIcon, MapPinIcon, ResetIcon, TickIcon, UploadIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ApiError } from '../../lib/api'
import { errorMessage } from '../../lib/errors'
import { formatNumber } from '../../lib/format'
import { ringArea, ringPerimeter, satelliteLayer, placeLabelsLayer } from '../../lib/maps'
import { captureApi, type Capture, type CaptureAsset } from '../../lib/tasksApi'

// MAP-01 to MAP-05, FUL-03: walk the plot and record each corner on the phone.
// After R1 (numbered corners joined on satellite, the area large, perimeter,
// area and accuracy in a strip), R2 (thick buttons and an accuracy bar for the
// field), R4 (work saved on the phone, synced when online) and R5 (a last
// check that every piece of evidence is there before submitting).

type Fix = { lng: number; lat: number; accuracy: number; at: string }
type Pending = { lng: number; lat: number; accuracy: number; at: string }
type Step = 'corners' | 'evidence' | 'review'

const QUEUE = (id: string) => `oweru-capture-queue:${id}`

function readQueue(id: string): Pending[] {
  try {
    return JSON.parse(localStorage.getItem(QUEUE(id)) || '[]') as Pending[]
  } catch {
    return []
  }
}

function writeQueue(id: string, rows: Pending[]) {
  try {
    if (rows.length) localStorage.setItem(QUEUE(id), JSON.stringify(rows))
    else localStorage.removeItem(QUEUE(id))
  } catch {
    // Storage can be blocked; the corners stay in memory for this visit.
  }
}

export function CapturePage() {
  const { propertyId = '' } = useParams()
  const [params] = useSearchParams()
  const taskId = params.get('task') ?? undefined
  const { t } = useTranslation()
  useDocumentTitle(t('field.capture.title'))
  const [capture, setCapture] = useState<Capture | null>(null)
  const [error, setError] = useState('')
  const [fix, setFix] = useState<Fix | null>(null)
  const [watchError, setGpsError] = useState('')
  const hasGps = 'geolocation' in navigator
  const gpsError = hasGps ? watchError : t('field.capture.noGps')
  const creating = useRef(false)

  // GPS: the phone's own location, high accuracy, as fresh as possible.
  useEffect(() => {
    if (!hasGps) return
    const watch = navigator.geolocation.watchPosition(
      (position) => {
        setGpsError('')
        setFix({ lng: position.coords.longitude, lat: position.coords.latitude, accuracy: position.coords.accuracy, at: new Date(position.timestamp).toISOString() })
      },
      (failure) => setGpsError(failure.code === failure.PERMISSION_DENIED ? t('field.capture.gpsDenied') : t('field.capture.gpsWaiting')),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 30000 },
    )
    return () => navigator.geolocation.clearWatch(watch)
  }, [hasGps, t])

  // Keep the screen on while walking the plot, where the browser allows it.
  useEffect(() => {
    let lock: { release: () => Promise<void> } | null = null
    const nav = navigator as Navigator & { wakeLock?: { request: (kind: 'screen') => Promise<{ release: () => Promise<void> }> } }
    nav.wakeLock?.request('screen').then((value) => (lock = value), () => undefined)
    return () => void lock?.release()
  }, [])

  // Find the open draft for this property (and task), or wait for a fix to start one.
  useEffect(() => {
    let live = true
    captureApi
      .list(propertyId)
      .then((page) => {
        if (!live) return
        const mine = page.results.filter((row) => (taskId ? row.verification_task_id === taskId : true))
        const draft = mine.find((row) => row.status === 'DRAFT') ?? (taskId ? mine.find((row) => row.status === 'SUBMITTED') : undefined)
        if (draft) return captureApi.get(draft.capture_id).then((row) => live && setCapture(row))
      })
      .catch((failure) => live && setError(errorMessage(t, failure)))
    return () => {
      live = false
    }
  }, [propertyId, taskId, t])

  useEffect(() => {
    if (capture || !fix || creating.current || error) return
    creating.current = true
    captureApi
      .create(propertyId, fix.lng, fix.lat, taskId)
      .then(setCapture)
      .catch((failure) => setError(errorMessage(t, failure)))
  }, [capture, fix, propertyId, taskId, error, t])

  return (
    <div className="fixed inset-0 flex flex-col bg-[#11180f] text-white">
      {capture ? (
        <Workspace capture={capture} fix={fix} gpsError={gpsError} onChange={setCapture} taskId={taskId} />
      ) : (
        <Waiting propertyId={propertyId} error={error} gpsError={gpsError} fix={fix} />
      )}
    </div>
  )
}

function Waiting({ propertyId, error, gpsError, fix }: { propertyId: string; error: string; gpsError: string; fix: Fix | null }) {
  const { t } = useTranslation()
  return (
    <div className="m-auto max-w-sm px-6 text-center">
      <motion.span animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 1.6, repeat: Infinity }} className="mx-auto grid size-16 place-items-center rounded-full bg-gold/20 text-gold">
        <MapPinIcon className="size-7" />
      </motion.span>
      <p className="mt-5 text-[18px] font-semibold">{t('field.capture.starting', { property: propertyId })}</p>
      <p className="mt-2 text-[14px] text-white/70">{error || gpsError || (fix ? t('field.capture.creating') : t('field.capture.gpsWaiting'))}</p>
      <Link to="/tasks" className="mt-6 inline-block text-[14px] text-gold underline underline-offset-4">
        {t('field.capture.back')}
      </Link>
    </div>
  )
}

function Workspace({ capture, fix, gpsError, onChange, taskId }: { capture: Capture; fix: Fix | null; gpsError: string; onChange: (capture: Capture) => void; taskId?: string }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const reduce = useReducedMotion()
  const locked = capture.status === 'SUBMITTED'
  const limit = capture.map_context?.corner_accuracy_m ?? 10
  const [pending, setPending] = useState<Pending[]>(() => readQueue(capture.capture_id))
  const [online, setOnline] = useState(() => navigator.onLine)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState<{ tone: 'error' | 'ok'; text: string } | null>(null)
  const [step, setStep] = useState<Step>(locked ? 'review' : 'corners')
  const [follow, setFollow] = useState(true)
  const [previews, setPreviews] = useState<Record<string, string>>({})

  const points = useMemo<[number, number][]>(() => [...capture.corners.map((row) => row.point), ...pending.map((row) => [row.lng, row.lat] as [number, number])], [capture.corners, pending])
  const area = useMemo(() => (locked && capture.measured_area_sqm ? Number(capture.measured_area_sqm) : ringArea(points)), [locked, capture.measured_area_sqm, points])
  const perimeter = useMemo(() => ringPerimeter(points), [points])
  const good = fix !== null && fix.accuracy <= limit
  const photos = capture.assets.filter((row) => row.mime_type.startsWith('image/'))
  const hasVideo = capture.assets.some((row) => row.mime_type.startsWith('video/'))

  const refresh = useCallback(async () => onChange(await captureApi.get(capture.capture_id)), [capture.capture_id, onChange])

  const flush = useCallback(async () => {
    const queue = readQueue(capture.capture_id)
    if (!queue.length) return
    setBusy('sync')
    const left = [...queue]
    try {
      while (left.length) {
        const row = left[0]
        await captureApi.corner(capture.capture_id, row.lng, row.lat, row.accuracy, row.at)
        left.shift()
        writeQueue(capture.capture_id, left)
        setPending([...left])
      }
      await refresh()
    } catch (failure) {
      if (!(failure instanceof ApiError && failure.isNetworkError)) {
        // The server refused a stored corner (e.g. accuracy): drop it and say so.
        left.shift()
        writeQueue(capture.capture_id, left)
        setPending([...left])
        setMessage({ tone: 'error', text: errorMessage(t, failure) })
      }
    } finally {
      setBusy('')
    }
  }, [capture.capture_id, refresh, t])

  useEffect(() => {
    const up = () => {
      setOnline(true)
      void flush()
    }
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [flush])

  async function record() {
    if (!fix || !good || locked) return
    setMessage(null)
    const row: Pending = { lng: fix.lng, lat: fix.lat, accuracy: fix.accuracy, at: fix.at }
    if (navigator.vibrate) navigator.vibrate(40)
    if (!navigator.onLine) {
      const next = [...readQueue(capture.capture_id), row]
      writeQueue(capture.capture_id, next)
      setPending(next)
      return
    }
    setBusy('record')
    try {
      await captureApi.corner(capture.capture_id, row.lng, row.lat, row.accuracy, row.at)
      await refresh()
    } catch (failure) {
      if (failure instanceof ApiError && failure.isNetworkError) {
        const next = [...readQueue(capture.capture_id), row]
        writeQueue(capture.capture_id, next)
        setPending(next)
      } else setMessage({ tone: 'error', text: errorMessage(t, failure) })
    } finally {
      setBusy('')
    }
  }

  async function undo() {
    if (locked) return
    if (pending.length) {
      const next = pending.slice(0, -1)
      writeQueue(capture.capture_id, next)
      setPending(next)
      return
    }
    if (!capture.corners.length) return
    setBusy('undo')
    try {
      await captureApi.undoCorner(capture.capture_id)
      await refresh()
    } catch (failure) {
      setMessage({ tone: 'error', text: errorMessage(t, failure) })
    } finally {
      setBusy('')
    }
  }

  async function addFiles(files: FileList | null, source: 'CAMERA' | 'UPLOAD') {
    if (!files?.length) return
    setMessage(null)
    setBusy('upload')
    try {
      for (const file of Array.from(files)) {
        const asset: CaptureAsset = await captureApi.asset(capture.capture_id, file, source)
        const url = URL.createObjectURL(file)
        setPreviews((current) => ({ ...current, [asset.media_id]: file.type.startsWith('video/') ? `video:${url}` : url }))
      }
      await refresh()
    } catch (failure) {
      setMessage({ tone: 'error', text: errorMessage(t, failure) })
    } finally {
      setBusy('')
    }
  }

  async function submit() {
    setBusy('submit')
    setMessage(null)
    try {
      const done = await captureApi.submit(capture.capture_id)
      onChange(done)
      setMessage({ tone: 'ok', text: t('field.capture.submitted') })
    } catch (failure) {
      setMessage({ tone: 'error', text: errorMessage(t, failure) })
    } finally {
      setBusy('')
    }
  }

  const checks = [
    { key: 'corners', ok: capture.corners.length >= 3 && !pending.length, text: t('field.capture.checkCorners', { count: capture.corners.length }) },
    { key: 'synced', ok: !pending.length, text: pending.length ? t('field.capture.checkPending', { count: pending.length }) : t('field.capture.checkSynced') },
    { key: 'photos', ok: photos.length > 0, text: t('field.capture.checkPhotos', { count: photos.length }) },
    { key: 'video', ok: hasVideo, text: t('field.capture.checkVideo') },
  ]
  const ready = checks.filter((row) => row.key !== 'video').every((row) => row.ok)

  return (
    <>
      {/* Top: back, title, the four field buttons (R2). */}
      <header className="relative z-20 flex items-center gap-3 bg-[#0b1209]/90 px-3 pt-[max(env(safe-area-inset-top),10px)] pb-2 backdrop-blur">
        <button type="button" onClick={() => navigate(taskId ? `/tasks/${taskId}` : '/tasks')} aria-label={t('field.capture.back')} className="grid size-11 place-items-center rounded-xl bg-white/10">
          <ArrowLeftIcon className="size-5" />
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold">{t('field.capture.title')}</p>
          <p className="truncate text-[12px] text-white/60">
            {capture.property_id} · {capture.capture_id}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${online ? 'bg-success/25 text-[#9be3bd]' : 'bg-gold/25 text-gold-light'}`}>{online ? t('field.capture.online') : t('field.capture.offline')}</span>
      </header>

      <div className="relative min-h-0 flex-1">
        <FieldMap points={points} pendingFrom={capture.corners.length} fix={fix} follow={follow} onPan={() => setFollow(false)} locked={locked} boundary={capture.observed_boundary?.coordinates[0] ?? null} />

        {/* R2's big buttons along the top of the map. */}
        <div className="absolute inset-x-3 top-3 z-[500] grid grid-cols-4 gap-2">
          <FieldButton label={t('field.capture.locate')} onClick={() => setFollow(true)} active={follow}>
            <MapPinIcon className="size-6" />
          </FieldButton>
          <FieldButton label={t('field.capture.undo')} onClick={() => void undo()} disabled={locked || busy !== '' || !points.length}>
            <ResetIcon className="size-6" />
          </FieldButton>
          <FieldButton label={t('field.capture.photos')} onClick={() => setStep('evidence')} active={step === 'evidence'} disabled={locked && step === 'review'}>
            <CameraIcon className="size-6" />
          </FieldButton>
          <FieldButton label={t('field.capture.check')} onClick={() => setStep('review')} active={step === 'review'}>
            <TickIcon className="size-6" />
          </FieldButton>
        </div>

        {/* R1: the area large over the plot. */}
        <AnimatePresence>
          {points.length >= 3 && (
            <motion.div
              initial={reduce ? false : { opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="pointer-events-none absolute top-24 left-1/2 z-[500] -translate-x-1/2 rounded-2xl bg-[#0b1209]/80 px-5 py-2 text-center backdrop-blur"
            >
              <p className="text-[28px] leading-none font-bold tabular-nums">
                {formatNumber(Math.round(area), i18n.language)} m²
              </p>
              <p className="mt-1 text-[11px] text-white/70">{locked ? t('field.capture.measured') : t('field.capture.estimate')}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {gpsError && (
          <div className="absolute inset-x-3 top-20 z-[500] flex items-center gap-2 rounded-xl bg-danger px-4 py-3 text-[13px]">
            <AlertIcon className="size-4 shrink-0" />
            {gpsError}
          </div>
        )}
      </div>

      {/* The bottom sheet: the strip, then the step's own controls. */}
      <section className="relative z-20 rounded-t-3xl bg-white px-4 pt-3 pb-[max(env(safe-area-inset-bottom),14px)] text-navy shadow-[0_-12px_30px_rgba(0,0,0,0.35)]">
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-mist" />
        <div className="grid grid-cols-3 gap-2 rounded-2xl bg-paper px-3 py-2.5 text-center">
          <Stat label={t('field.capture.corners')} value={`${points.length}`} />
          <Stat label={t('field.capture.perimeter')} value={`${formatNumber(Math.round(perimeter), i18n.language)} m`} />
          <Stat label={t('field.capture.accuracy')} value={fix ? `±${formatNumber(Math.round(fix.accuracy), i18n.language)} m` : '-'} tone={fix ? (good ? 'good' : 'bad') : undefined} />
        </div>

        {pending.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-3 flex items-center gap-3 rounded-xl border border-gold/40 bg-[#fdf7ec] px-3.5 py-2.5 text-[13px]">
            <span className="grid size-8 place-items-center rounded-full bg-gold/20 text-[#9a6c12]">
              <UploadIcon className="size-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-semibold">{t('field.capture.savedOnPhone')}</span>
              <span className="block text-[12px] text-muted">{t('field.capture.waitingSync', { count: pending.length })}</span>
            </span>
            <button type="button" disabled={!online || busy === 'sync'} onClick={() => void flush()} className="rounded-lg bg-navy px-3 py-1.5 text-[12px] font-semibold text-white disabled:opacity-40">
              {busy === 'sync' ? t('field.capture.syncing') : t('field.capture.syncNow')}
            </button>
          </motion.div>
        )}

        <AnimatePresence mode="wait" initial={false}>
          {step === 'corners' && (
            <motion.div key="corners" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="mt-3">
              <p className="text-[13px] leading-relaxed text-muted">{good ? t('field.capture.standAt', { number: points.length + 1 }) : t('field.capture.waitAccuracy', { limit })}</p>
              <div className="mt-3 flex gap-2">
                <motion.button
                  type="button"
                  whileTap={{ scale: 0.96 }}
                  onClick={() => void record()}
                  disabled={!good || locked || busy === 'record'}
                  className="relative h-14 flex-1 overflow-hidden rounded-2xl bg-gold text-[16px] font-bold text-navy shadow-[0_10px_24px_-10px_rgba(200,145,40,0.8)] disabled:bg-mist disabled:text-muted disabled:shadow-none"
                >
                  {good && !reduce && <motion.span aria-hidden="true" className="absolute inset-0 rounded-2xl border-2 border-gold" animate={{ scale: [1, 1.06, 1], opacity: [0.7, 0, 0.7] }} transition={{ duration: 1.8, repeat: Infinity }} />}
                  <span className="relative inline-flex items-center gap-2">
                    <MapPinIcon className="size-5" />
                    {busy === 'record' ? t('field.capture.saving') : t('field.capture.record', { number: points.length + 1 })}
                  </span>
                </motion.button>
                <button type="button" disabled={points.length < 3} onClick={() => setStep('evidence')} className="h-14 rounded-2xl border border-mist px-5 text-[15px] font-semibold text-navy disabled:opacity-40">
                  {t('field.capture.next')}
                </button>
              </div>
            </motion.div>
          )}

          {step === 'evidence' && (
            <motion.div key="evidence" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="mt-3">
              <p className="text-[13px] leading-relaxed text-muted">{t('field.capture.evidenceNote')}</p>
              <div className="mt-3 grid grid-cols-3 gap-2">
                <FilePicker label={t('field.capture.takePhoto')} accept="image/*" capture icon={<CameraIcon className="size-5" />} onPick={(files) => void addFiles(files, 'CAMERA')} disabled={locked || busy === 'upload'} />
                <FilePicker label={t('field.capture.recordVideo')} accept="video/*" capture icon={<ImageIcon className="size-5" />} onPick={(files) => void addFiles(files, 'CAMERA')} disabled={locked || busy === 'upload'} />
                <FilePicker label={t('field.capture.fromGallery')} accept="image/*,video/*" multiple icon={<UploadIcon className="size-5" />} onPick={(files) => void addFiles(files, 'UPLOAD')} disabled={locked || busy === 'upload'} />
              </div>
              {busy === 'upload' && <p className="mt-2 text-[12px] text-muted">{t('field.capture.uploading')}</p>}
              {capture.assets.length > 0 && (
                <ul className="mt-3 flex gap-2 overflow-x-auto pb-1">
                  {capture.assets.map((asset) => (
                    <motion.li key={asset.media_id} initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }} className="relative size-16 shrink-0 overflow-hidden rounded-xl bg-paper">
                      {previews[asset.media_id] && !previews[asset.media_id].startsWith('video:') ? <img src={previews[asset.media_id]} alt="" className="size-full object-cover" /> : <ImageIcon className="m-5 size-6 text-muted" />}
                      {asset.flags.length > 0 && <span title={asset.flags.join(', ')} className="absolute top-1 right-1 size-2.5 rounded-full bg-gold ring-2 ring-white" />}
                    </motion.li>
                  ))}
                </ul>
              )}
              <div className="mt-3 flex gap-2">
                <button type="button" onClick={() => setStep('corners')} className="h-12 flex-1 rounded-2xl border border-mist text-[14px] font-semibold">
                  {t('field.capture.backToCorners')}
                </button>
                <button type="button" onClick={() => setStep('review')} className="h-12 flex-1 rounded-2xl bg-navy text-[14px] font-semibold text-white">
                  {t('field.capture.next')}
                </button>
              </div>
            </motion.div>
          )}

          {step === 'review' && (
            <motion.div key="review" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="mt-3">
              {locked ? (
                <div className="flex items-center gap-3 rounded-2xl bg-success-soft px-4 py-3">
                  <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 400, damping: 18 }} className="grid size-10 place-items-center rounded-full bg-success text-white">
                    <CheckIcon className="size-5" />
                  </motion.span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-semibold text-success">{t('field.capture.lockedTitle')}</p>
                    <p className="text-[12px] text-navy-soft">{t('field.capture.lockedBody', { area: formatNumber(Math.round(area), i18n.language) })}</p>
                  </div>
                </div>
              ) : (
                <ul className="space-y-2">
                  {checks.map((row, index) => (
                    <motion.li key={row.key} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.06 }} className="flex items-center gap-3 rounded-xl border border-mist px-3.5 py-2.5 text-[13px]">
                      <span className={`grid size-6 place-items-center rounded-full ${row.ok ? 'bg-success text-white' : 'bg-mist text-muted'}`}>{row.ok ? <CheckIcon className="size-3.5" /> : <span className="size-1.5 rounded-full bg-current" />}</span>
                      <span className="flex-1">{row.text}</span>
                      {row.key === 'video' && !row.ok && <span className="text-[11px] text-muted">{t('field.capture.recommended')}</span>}
                    </motion.li>
                  ))}
                </ul>
              )}
              {!locked && <p className="mt-3 text-[12px] leading-relaxed text-muted">{t('field.capture.lockNote')}</p>}
              <div className="mt-3 flex gap-2">
                {locked ? (
                  <button type="button" onClick={() => navigate(taskId ? `/tasks/${taskId}` : '/tasks')} className="h-14 flex-1 rounded-2xl bg-navy text-[15px] font-semibold text-white">
                    {taskId ? t('field.capture.backToTask') : t('field.capture.done')}
                  </button>
                ) : (
                  <>
                    <button type="button" onClick={() => setStep('evidence')} className="h-14 rounded-2xl border border-mist px-5 text-[14px] font-semibold">
                      {t('field.capture.back')}
                    </button>
                    <motion.button type="button" whileTap={{ scale: 0.97 }} disabled={!ready || busy === 'submit'} onClick={() => void submit()} className="h-14 flex-1 rounded-2xl bg-gold text-[15px] font-bold text-navy disabled:bg-mist disabled:text-muted">
                      {busy === 'submit' ? t('field.capture.submitting') : t('field.capture.submit')}
                    </motion.button>
                  </>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {message && (
          <p role={message.tone === 'error' ? 'alert' : 'status'} className={`mt-3 flex items-center gap-2 text-[13px] ${message.tone === 'error' ? 'text-danger' : 'text-success'}`}>
            {message.tone === 'error' ? <AlertIcon className="size-4 shrink-0" /> : <CheckIcon className="size-4 shrink-0" />}
            {message.text}
          </p>
        )}
        <p className="mt-3 text-center text-[11px] text-muted">{t('field.capture.disclaimer')}</p>
      </section>
    </>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'good' | 'bad' }) {
  return (
    <div>
      <p className="text-[10px] font-semibold tracking-[0.08em] text-muted uppercase">{label}</p>
      <motion.p key={value} initial={{ opacity: 0.4, y: 3 }} animate={{ opacity: 1, y: 0 }} className={`mt-0.5 text-[16px] font-bold tabular-nums ${tone === 'good' ? 'text-success' : tone === 'bad' ? 'text-[#b4640a]' : 'text-navy'}`}>
        {value}
      </motion.p>
    </div>
  )
}

function FieldButton({ label, onClick, children, active = false, disabled = false }: { label: string; onClick: () => void; children: ReactNode; active?: boolean; disabled?: boolean }) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.92 }}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={`flex h-16 flex-col items-center justify-center gap-1 rounded-2xl text-[11px] font-semibold shadow-lg backdrop-blur disabled:opacity-40 ${active ? 'bg-gold text-navy' : 'bg-[#0b1209]/85 text-white'}`}
    >
      {children}
      <span className="max-w-full truncate px-1">{label}</span>
    </motion.button>
  )
}

function FilePicker({ label, accept, icon, onPick, capture = false, multiple = false, disabled = false }: { label: string; accept: string; icon: ReactNode; onPick: (files: FileList | null) => void; capture?: boolean; multiple?: boolean; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <>
      <button type="button" disabled={disabled} onClick={() => input.current?.click()} className="flex h-20 flex-col items-center justify-center gap-1.5 rounded-2xl border border-mist bg-paper text-[12px] font-semibold text-navy disabled:opacity-50">
        {icon}
        {label}
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        {...(capture ? { capture: 'environment' as const } : {})}
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          onPick(event.target.files)
          event.target.value = ''
        }}
      />
    </>
  )
}

const cornerIcon = (number: number, pending: boolean) =>
  L.divIcon({
    className: '',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    html: `<div class="owr-corner" style="width:30px;height:30px;border-radius:999px;background:${pending ? '#e5b972' : '#c89128'};border:3px solid #fff;box-shadow:0 4px 10px rgba(0,0,0,.45);display:grid;place-items:center;font:700 13px Poppins,system-ui;color:#0f172a">${number}</div>`,
  })

// R1's satellite map: the corners numbered, joined into the plot, and the
// phone's position with its accuracy circle.
function FieldMap({ points, pendingFrom, fix, follow, onPan, locked, boundary }: { points: [number, number][]; pendingFrom: number; fix: Fix | null; follow: boolean; onPan: () => void; locked: boolean; boundary: [number, number][] | null }) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const layers = useRef<{ plot: L.LayerGroup; me: L.LayerGroup } | null>(null)
  const followRef = useRef(follow)
  const panRef = useRef(onPan)
  const centred = useRef(false)

  useEffect(() => {
    followRef.current = follow
    panRef.current = onPan
  }, [follow, onPan])

  useEffect(() => {
    if (!element.current) return
    const instance = L.map(element.current, { zoomControl: false, attributionControl: true }).setView([-6.79, 39.21], 6)
    satelliteLayer().addTo(instance)
    placeLabelsLayer().addTo(instance)
    instance.attributionControl.setPosition('bottomright')
    instance.on('dragstart', () => panRef.current())
    layers.current = { plot: L.layerGroup().addTo(instance), me: L.layerGroup().addTo(instance) }
    map.current = instance
    return () => {
      instance.remove()
      map.current = null
    }
  }, [])

  useEffect(() => {
    const current = layers.current
    if (!current) return
    current.plot.clearLayers()
    const ring = locked && boundary ? boundary.slice(0, -1) : points
    if (ring.length >= 2) {
      const shape = ring.length >= 3 ? L.polygon(ring.map(([lng, lat]) => [lat, lng] as L.LatLngTuple)) : L.polyline(ring.map(([lng, lat]) => [lat, lng] as L.LatLngTuple))
      shape.setStyle({ color: '#e5b972', weight: 3, dashArray: locked ? undefined : '8 6', fillColor: '#c89128', fillOpacity: 0.25 }).addTo(current.plot)
    }
    points.forEach(([lng, lat], index) => L.marker([lat, lng], { icon: cornerIcon(index + 1, index >= pendingFrom), keyboard: false }).addTo(current.plot))
  }, [points, pendingFrom, locked, boundary])

  useEffect(() => {
    const current = layers.current
    const instance = map.current
    if (!current || !instance || !fix) return
    current.me.clearLayers()
    L.circle([fix.lat, fix.lng], { radius: fix.accuracy, color: '#60a5fa', weight: 1, fillColor: '#60a5fa', fillOpacity: 0.15 }).addTo(current.me)
    L.circleMarker([fix.lat, fix.lng], { radius: 8, color: '#fff', weight: 3, fillColor: '#2563eb', fillOpacity: 1 }).addTo(current.me)
    if (!centred.current) {
      instance.setView([fix.lat, fix.lng], 19)
      centred.current = true
    } else if (followRef.current) instance.panTo([fix.lat, fix.lng], { animate: true })
  }, [fix])

  return <div ref={element} role="img" aria-label="Satellite map" className="absolute inset-0" />
}
