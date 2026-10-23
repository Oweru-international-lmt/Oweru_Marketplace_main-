import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { CameraIcon, CheckIcon, EyeIcon, EyeOffIcon, MapPinIcon, ResetIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatShortDate } from '../../lib/format'
import { registrationApi, type Place, type Position } from '../../lib/partnersApi'

// SRD 14.2 step 4. After R11: the official opens the WhatsApp link on their
// phone, gives their details, takes a live photo inside an oval guide (no
// gallery), photographs the office stamp, then sends it for approval.

type Step = 'details' | 'photo' | 'stamp' | 'review' | 'done'
const STEPS: Step[] = ['details', 'photo', 'stamp', 'review']

export function RegisterOfficialPage() {
  const { token = '' } = useParams()
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  useDocumentTitle(t('officialRegister.title'))
  const [invite, setInvite] = useState<{ locality: Place; phone: string; expires_at: string } | null>(null)
  const [failed, setFailed] = useState('')
  const [step, setStep] = useState<Step>('details')
  const [values, setValues] = useState({ full_name: '', national_id_number: '', email: '', password: '' })
  const [position, setPosition] = useState<Position | ''>('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [stamp, setStamp] = useState<File | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    registrationApi.get(token).then(setInvite, (failure) => setFailed(errorMessage(t, failure)))
  }, [token, t])

  const index = STEPS.indexOf(step)
  const detailsReady = values.full_name.trim().length > 2 && position && values.national_id_number.trim().length > 5 && /\S+@\S+\.\S+/.test(values.email) && values.password.length >= 8

  async function submit() {
    if (!photo || !stamp || !position) return
    setBusy(true)
    setError('')
    try {
      await registrationApi.submit(token, { ...values, full_name: values.full_name.trim(), national_id_number: values.national_id_number.trim(), email: values.email.trim(), position, photo, stamp_photo: stamp })
      setStep('done')
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  const set = (key: keyof typeof values) => (event: React.ChangeEvent<HTMLInputElement>) => setValues((current) => ({ ...current, [key]: event.target.value }))
  const input = 'h-12 w-full rounded-xl border border-mist bg-white px-4 text-[15px] text-navy outline-none focus:border-gold focus:ring-2 focus:ring-gold/20'
  const slide = reduce ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } } : { initial: { opacity: 0, x: 24 }, animate: { opacity: 1, x: 0 }, exit: { opacity: 0, x: -24 } }

  return (
    <div className="min-h-dvh bg-paper">
      <header className="bg-navy px-5 pt-6 pb-16 text-white">
        <div className="mx-auto max-w-md">
          <p className="text-[13px] font-semibold tracking-[0.18em] text-gold uppercase">Oweru</p>
          <h1 className="mt-3 text-[24px] leading-tight font-semibold">{t('officialRegister.title')}</h1>
          {invite && (
            <p className="mt-2 flex items-start gap-2 text-[14px] text-white/75">
              <MapPinIcon className="mt-0.5 size-4 shrink-0 text-gold" />
              {t('officialRegister.for', { place: invite.locality.name, ward: invite.locality.ward, district: invite.locality.district })}
            </p>
          )}
        </div>
      </header>

      <main className="mx-auto -mt-10 max-w-md px-4 pb-12">
        <div className="rounded-2xl bg-white p-5 shadow-lift">
          {failed ? (
            <div className="py-6 text-center">
              <p className="text-[16px] font-semibold text-navy">{t('officialRegister.invalidTitle')}</p>
              <p className="mt-2 text-[14px] text-muted">{failed}</p>
            </div>
          ) : !invite ? (
            <div className="space-y-3 py-4">
              <div className="h-4 w-2/3 animate-pulse rounded bg-paper" />
              <div className="h-12 animate-pulse rounded-xl bg-paper" />
              <div className="h-12 animate-pulse rounded-xl bg-paper" />
            </div>
          ) : (
            <>
              {step !== 'done' && (
                <ol className="mb-5 flex items-center gap-2" aria-label={t('officialRegister.progress')}>
                  {STEPS.map((item, position) => (
                    <li key={item} className="flex flex-1 flex-col gap-1.5">
                      <span className="h-1 overflow-hidden rounded-full bg-mist">
                        <motion.span className="block h-full bg-gold" initial={false} animate={{ width: position <= index ? '100%' : '0%' }} transition={{ duration: 0.35 }} />
                      </span>
                      <span className={`text-[11px] ${position === index ? 'font-semibold text-navy' : 'text-muted'}`}>{t(`officialRegister.steps.${item}`)}</span>
                    </li>
                  ))}
                </ol>
              )}

              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={step} {...slide} transition={{ duration: 0.25 }}>
                  {step === 'details' && (
                    <div className="space-y-4">
                      <p className="text-[13px] text-muted">{t('officialRegister.detailsNote', { phone: invite.phone, date: formatShortDate(invite.expires_at, i18n.language) })}</p>
                      <label className="block">
                        <span className="mb-1.5 block text-[13px] font-medium text-navy">{t('officialRegister.fullName')}</span>
                        <input className={input} autoComplete="name" value={values.full_name} onChange={set('full_name')} />
                      </label>
                      <div>
                        <span className="mb-1.5 block text-[13px] font-medium text-navy">{t('officialRegister.position')}</span>
                        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label={t('officialRegister.position')}>
                          {(['MWENYEKITI', 'MTENDAJI'] as Position[]).map((item) => (
                            <button key={item} type="button" role="radio" aria-checked={position === item} onClick={() => setPosition(item)} className={`rounded-xl border px-3 py-3 text-left transition-colors ${position === item ? 'border-gold bg-gold/10' : 'border-mist'}`}>
                              <span className="block text-[14px] font-semibold text-navy">{t(`partners.positions.${item}`)}</span>
                              <span className="block text-[11px] text-muted">{t(`officialRegister.positionHint.${item}`)}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                      <label className="block">
                        <span className="mb-1.5 block text-[13px] font-medium text-navy">{t('officialRegister.nationalId')}</span>
                        <input className={input} inputMode="numeric" autoComplete="off" placeholder="19800101-12345-00001-1" value={values.national_id_number} onChange={set('national_id_number')} />
                      </label>
                      <label className="block">
                        <span className="mb-1.5 block text-[13px] font-medium text-navy">{t('officialRegister.email')}</span>
                        <input className={input} type="email" autoComplete="email" value={values.email} onChange={set('email')} />
                      </label>
                      <label className="block">
                        <span className="mb-1.5 block text-[13px] font-medium text-navy">{t('officialRegister.password')}</span>
                        <span className="relative block">
                          <input className={`${input} pr-12`} type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={values.password} onChange={set('password')} />
                          <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={t(showPassword ? 'officialRegister.hidePassword' : 'officialRegister.showPassword')} className="absolute top-1/2 right-3 -translate-y-1/2 text-muted">
                            {showPassword ? <EyeOffIcon className="size-5" /> : <EyeIcon className="size-5" />}
                          </button>
                        </span>
                        <span className="mt-1 block text-[12px] text-muted">{t('officialRegister.passwordHint')}</span>
                      </label>
                      <button type="button" disabled={!detailsReady} onClick={() => setStep('photo')} className="h-12 w-full rounded-full bg-gold text-[15px] font-semibold text-navy disabled:opacity-50">
                        {t('officialRegister.next')}
                      </button>
                    </div>
                  )}

                  {step === 'photo' && (
                    <Camera
                      key="photo"
                      facing="user"
                      title={t('officialRegister.photoTitle')}
                      hint={t('officialRegister.photoHint')}
                      file={photo}
                      fileName="photo.jpg"
                      onFile={setPhoto}
                      onBack={() => setStep('details')}
                      onNext={() => setStep('stamp')}
                    />
                  )}

                  {step === 'stamp' && (
                    <Camera
                      key="stamp"
                      facing="environment"
                      title={t('officialRegister.stampTitle')}
                      hint={t('officialRegister.stampHint')}
                      file={stamp}
                      fileName="stamp.jpg"
                      onFile={setStamp}
                      onBack={() => setStep('photo')}
                      onNext={() => setStep('review')}
                    />
                  )}

                  {step === 'review' && (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-3">
                        {[photo, stamp].map((file, position) => (
                          <Preview key={position} file={file} label={position === 0 ? t('officialRegister.steps.photo') : t('officialRegister.steps.stamp')} round={position === 0} />
                        ))}
                      </div>
                      <dl className="divide-y divide-mist/70 rounded-xl border border-mist px-4 text-[14px]">
                        {[
                          [t('officialRegister.fullName'), values.full_name],
                          [t('officialRegister.position'), position ? t(`partners.positions.${position}`) : ''],
                          [t('officialRegister.nationalId'), values.national_id_number],
                          [t('officialRegister.email'), values.email],
                          [t('officialRegister.place'), `${invite.locality.name}, ${invite.locality.ward}`],
                        ].map(([label, value]) => (
                          <div key={label} className="flex justify-between gap-4 py-3">
                            <dt className="shrink-0 text-muted">{label}</dt>
                            <dd className="min-w-0 text-right font-medium [overflow-wrap:anywhere] text-navy">{value}</dd>
                          </div>
                        ))}
                      </dl>
                      <p className="rounded-xl bg-paper px-4 py-3 text-[13px] text-navy-soft">{t('officialRegister.reviewNote')}</p>
                      {error && <Alert tone="error">{error}</Alert>}
                      <div className="grid grid-cols-[auto_1fr] gap-2">
                        <button type="button" onClick={() => setStep('stamp')} className="h-12 rounded-full border border-mist px-5 text-[14px] font-medium text-navy">{t('officialRegister.back')}</button>
                        <button type="button" disabled={busy} onClick={() => void submit()} className="h-12 rounded-full bg-gold text-[15px] font-semibold text-navy disabled:opacity-60">
                          {busy ? t('officialRegister.sending') : t('officialRegister.submit')}
                        </button>
                      </div>
                    </div>
                  )}

                  {step === 'done' && (
                    <div className="py-6 text-center">
                      <motion.span initial={reduce ? false : { scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 18 }} className="mx-auto grid size-16 place-items-center rounded-full bg-success-soft text-success">
                        <CheckIcon className="size-8" />
                      </motion.span>
                      <p className="mt-4 text-[18px] font-semibold text-navy">{t('officialRegister.doneTitle')}</p>
                      <p className="mt-2 text-[14px] text-muted">{t('officialRegister.doneBody')}</p>
                    </div>
                  )}
                </motion.div>
              </AnimatePresence>
            </>
          )}
        </div>
        <p className="mt-4 text-center text-[12px] text-muted">{t('officialRegister.privacy')}</p>
      </main>
    </div>
  )
}

function useObjectUrl(file: File | null) {
  const url = useMemo(() => (file ? URL.createObjectURL(file) : ''), [file])
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url)
  }, [url])
  return url
}

function Preview({ file, label, round }: { file: File | null; label: string; round: boolean }) {
  const url = useObjectUrl(file)
  return (
    <figure className="rounded-xl border border-mist p-2 text-center">
      {url && <img src={url} alt={label} className={`mx-auto h-28 w-full object-cover ${round ? 'rounded-[999px]' : 'rounded-lg'}`} />}
      <figcaption className="mt-1.5 text-[12px] text-muted">{label}</figcaption>
    </figure>
  )
}

// R11: a live camera frame with a guide. The front camera shows a dashed oval
// for the face; the back camera a rectangle for the stamp. No gallery.
function Camera({ facing, title, hint, file, fileName, onFile, onBack, onNext }: {
  facing: 'user' | 'environment'
  title: string
  hint: string
  file: File | null
  fileName: string
  onFile: (file: File | null) => void
  onBack: () => void
  onNext: () => void
}) {
  const { t } = useTranslation()
  const video = useRef<HTMLVideoElement>(null)
  const [state, setState] = useState<'starting' | 'live' | 'denied'>('starting')
  const shot = useObjectUrl(file)
  const [flash, setFlash] = useState(false)

  useEffect(() => {
    if (file) return
    let stream: MediaStream | null = null
    let live = true
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 1280 } }, audio: false })
      .then((media) => {
        if (!live) {
          media.getTracks().forEach((track) => track.stop())
          return
        }
        stream = media
        if (video.current) {
          video.current.srcObject = media
          void video.current.play().catch(() => undefined)
        }
        setState('live')
      })
      .catch(() => live && setState('denied'))
    if (!navigator.mediaDevices) queueMicrotask(() => live && setState('denied'))
    return () => {
      live = false
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [facing, file])

  function capture() {
    const element = video.current
    if (!element || !element.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = element.videoWidth
    canvas.height = element.videoHeight
    const context = canvas.getContext('2d')
    if (!context) return
    if (facing === 'user') {
      context.translate(canvas.width, 0)
      context.scale(-1, 1)
    }
    context.drawImage(element, 0, 0)
    setFlash(true)
    window.setTimeout(() => setFlash(false), 180)
    canvas.toBlob((blob) => blob && onFile(new File([blob], fileName, { type: 'image/jpeg' })), 'image/jpeg', 0.9)
  }

  return (
    <div>
      <p className="text-[16px] font-semibold text-navy">{title}</p>
      <p className="mt-1 text-[13px] text-muted">{hint}</p>
      <div className="relative mt-4 aspect-[3/4] overflow-hidden rounded-2xl bg-[#0b1220]">
        {file ? (
          shot && <img src={shot} alt={title} className="absolute inset-0 size-full object-cover" />
        ) : (
          <video ref={video} playsInline muted className={`absolute inset-0 size-full object-cover ${facing === 'user' ? '-scale-x-100' : ''}`} />
        )}
        {!file && (
          <>
            <svg viewBox="0 0 300 400" className="pointer-events-none absolute inset-0 size-full" aria-hidden="true">
              <defs>
                <mask id={`guide-${facing}`}>
                  <rect width="300" height="400" fill="white" />
                  {facing === 'user' ? <ellipse cx="150" cy="180" rx="92" ry="122" fill="black" /> : <rect x="40" y="110" width="220" height="180" rx="14" fill="black" />}
                </mask>
              </defs>
              <rect width="300" height="400" fill="rgba(11,18,32,0.55)" mask={`url(#guide-${facing})`} />
              {facing === 'user' ? (
                <ellipse cx="150" cy="180" rx="92" ry="122" fill="none" stroke="#fff" strokeWidth="2.5" strokeDasharray="7 6" />
              ) : (
                <rect x="40" y="110" width="220" height="180" rx="14" fill="none" stroke="#fff" strokeWidth="2.5" strokeDasharray="7 6" />
              )}
              {[
                [24, 24, 1, 1],
                [276, 24, -1, 1],
                [24, 376, 1, -1],
                [276, 376, -1, -1],
              ].map(([x, y, dx, dy]) => (
                <path key={`${x}-${y}`} d={`M${x} ${y + 26 * dy} V${y} H${x + 26 * dx}`} fill="none" stroke="#c89128" strokeWidth="3" strokeLinecap="round" />
              ))}
            </svg>
            <span className="absolute inset-x-0 bottom-4 mx-auto w-max rounded-full bg-white/90 px-3 py-1 text-[12px] font-medium text-navy">
              {state === 'live' ? t('officialRegister.camera.ready') : state === 'denied' ? t('officialRegister.camera.denied') : t('officialRegister.camera.starting')}
            </span>
          </>
        )}
        <AnimatePresence>{flash && <motion.span initial={{ opacity: 0.9 }} animate={{ opacity: 0 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-white" />}</AnimatePresence>
      </div>

      {state === 'denied' && !file && <p className="mt-3 rounded-xl bg-danger-soft px-4 py-3 text-[13px] text-danger">{t('officialRegister.camera.deniedBody')}</p>}

      <div className="mt-4 flex items-center justify-between gap-3">
        <button type="button" onClick={onBack} className="h-12 rounded-full border border-mist px-5 text-[14px] font-medium text-navy">{t('officialRegister.back')}</button>
        {file ? (
          <>
            <button type="button" onClick={() => { onFile(null); setState('starting') }} className="inline-flex h-12 items-center gap-2 rounded-full border border-mist px-4 text-[14px] font-medium text-navy">
              <ResetIcon className="size-4" />
              {t('officialRegister.camera.retake')}
            </button>
            <button type="button" onClick={onNext} className="h-12 flex-1 rounded-full bg-gold text-[15px] font-semibold text-navy">{t('officialRegister.camera.use')}</button>
          </>
        ) : (
          <button type="button" disabled={state !== 'live'} onClick={capture} aria-label={t('officialRegister.camera.capture')} className="grid size-16 place-items-center rounded-full border-4 border-gold/40 bg-gold text-navy shadow-lift transition-transform active:scale-95 disabled:opacity-40">
            <CameraIcon className="size-7" />
          </button>
        )}
        {!file && <span className="w-[86px]" />}
      </div>
    </div>
  )
}
