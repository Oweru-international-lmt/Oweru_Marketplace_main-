import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/Alert'
import { ArrowLeftIcon, ChevronRightIcon, ClockIcon, CloseIcon, IdCardIcon, LockIcon, SelfieIcon, TickIcon, WhatsAppIcon } from '../../components/icons'
import { PageHeader } from '../../components/PageHeader'
import { ApiError } from '../../lib/api'
import { whatsappLink } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { firstFileProblem, PHOTO_TYPES } from '../../lib/files'
import { formatDate } from '../../lib/format'
import { listerApi, type EvidenceKind, type ListerIdentity } from '../../lib/listerApi'
import { FaceSample, IdSample, StartArt } from './identityArt'

type View = 'start' | 'idGuide' | 'idConfirm' | 'selfieGuide' | 'selfieConfirm'

// After L7 and L9, as one phone-sized panel: the start screen lists the two
// photos with "Why is this needed?" under them; each photo first shows how
// to take it well (good and bad examples with ticks and crosses), then the
// picture itself, the ID in a framed card and the selfie in a dark oval.
export function IdentityPage() {
  const { t } = useTranslation()
  const [identity, setIdentity] = useState<ListerIdentity | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [number, setNumber] = useState('')
  const [numberError, setNumberError] = useState<string | null>(null)
  const [view, setView] = useState<View>('start')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listerApi
      .identity()
      .then((found) => {
        setIdentity(found)
        setNumber(found.national_id_number)
      })
      .catch((caught) => {
        if (!(caught instanceof ApiError && caught.status === 404)) setError(errorMessage(t, caught))
      })
      .finally(() => setLoaded(true))
  }, [t])

  // The record exists from the first photo on, with the number saved first.
  async function ensureIdentity(): Promise<ListerIdentity | null> {
    if (!number.trim()) {
      setNumberError(t('lister.identity.numberMissing'))
      setView('start')
      return null
    }
    if (!identity) return listerApi.startIdentity(number.trim())
    if (identity.national_id_number !== number.trim()) return listerApi.updateIdentity(number.trim())
    return identity
  }

  async function upload(kind: EvidenceKind) {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const ready = await ensureIdentity()
      if (!ready) return
      setIdentity(ready)
      setIdentity(await listerApi.uploadEvidence(kind, file))
      setFile(null)
      setView('start')
    } catch (caught) {
      setError(errorMessage(t, caught))
    } finally {
      setBusy(false)
    }
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const ready = await ensureIdentity()
      if (!ready) return
      setIdentity(await listerApi.submitIdentity())
    } catch (caught) {
      setError(errorMessage(t, caught))
    } finally {
      setBusy(false)
    }
  }

  function pick(next: File | null, confirm: View) {
    if (!next) return
    const problem = firstFileProblem([next], PHOTO_TYPES)
    if (problem) {
      setError(t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name }))
      return
    }
    setError(null)
    setFile(next)
    setView(confirm)
  }

  const submitted = identity !== null && (identity.submitted_at !== null || identity.status !== 'PENDING')

  return (
    <>
      <PageHeader title={t('lister.identity.title')} />
      <div className="mx-auto w-full max-w-[420px]">
        <div className="relative min-h-[680px] overflow-hidden rounded-[28px] bg-white shadow-[0_20px_50px_-24px_rgba(15,23,42,0.35)] ring-1 ring-mist">
          {!loaded ? (
            <div className="grid min-h-[680px] place-items-center">
              <span className="size-6 animate-spin rounded-full border-2 border-gold/25 border-t-gold" aria-label={t('common.loading')} />
            </div>
          ) : submitted ? (
            <Status identity={identity} />
          ) : (
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={view}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.22 }}
                className="min-h-[680px]"
              >
                {view === 'start' && (
                  <Start
                    identity={identity}
                    number={number}
                    numberError={numberError}
                    onNumber={(value) => {
                      setNumber(value)
                      setNumberError(null)
                    }}
                    onOpen={(kind) => setView(kind === 'national_id_photo' ? 'idGuide' : 'selfieGuide')}
                    onSubmit={() => void submit()}
                    busy={busy}
                    error={error}
                  />
                )}
                {view === 'idGuide' && <IdGuide onClose={() => setView('start')} onPick={(next) => pick(next, 'idConfirm')} error={error} />}
                {view === 'selfieGuide' && <SelfieGuide onClose={() => setView('start')} onPick={(next) => pick(next, 'selfieConfirm')} error={error} />}
                {view === 'idConfirm' && file && (
                  <IdConfirm file={file} busy={busy} error={error} onBack={() => setView('idGuide')} onUse={() => void upload('national_id_photo')} />
                )}
                {view === 'selfieConfirm' && file && (
                  <SelfieConfirm file={file} busy={busy} error={error} onBack={() => setView('selfieGuide')} onUse={() => void upload('live_selfie')} />
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </div>
    </>
  )
}

function Start({ identity, number, numberError, onNumber, onOpen, onSubmit, busy, error }: {
  identity: ListerIdentity | null
  number: string
  numberError: string | null
  onNumber: (value: string) => void
  onOpen: (kind: EvidenceKind) => void
  onSubmit: () => void
  busy: boolean
  error: string | null
}) {
  const { t } = useTranslation()
  const [why, setWhy] = useState(false)
  const hasId = Boolean(identity?.national_id_photo_ref)
  const hasSelfie = Boolean(identity?.live_selfie_ref)
  const ready = hasId && hasSelfie && number.trim() !== ''

  return (
    <div className="flex min-h-[680px] flex-col px-6 pt-8 pb-7">
      <StartArt />
      <h2 className="mt-8 text-center text-[26px] leading-tight font-bold tracking-tight text-navy">{t('lister.identity.startTitle')}</h2>
      <p className="mx-auto mt-2.5 max-w-[300px] text-center text-[14.5px] leading-relaxed text-navy-soft">{t('lister.identity.startBody')}</p>

      <div className="mt-7">
        <label htmlFor="nida" className="mb-1.5 block text-[13px] font-medium text-navy">
          {t('lister.identity.number')}
        </label>
        <input
          id="nida"
          inputMode="numeric"
          autoComplete="off"
          value={number}
          onChange={(event) => onNumber(event.target.value.replace(/[^\d-]/g, '').slice(0, 30))}
          placeholder="19900101-12345-00001-23"
          aria-invalid={numberError ? true : undefined}
          aria-describedby="nida-note"
          className={`h-11 w-full rounded-lg border px-3.5 text-[14px] text-navy tabular-nums outline-none placeholder:text-muted/60 focus:ring-[3px] ${
            numberError ? 'border-danger focus:ring-danger/15' : 'border-[#cfd5df] focus:border-gold focus:ring-gold/20'
          }`}
        />
        <p id="nida-note" className={`mt-1.5 text-[12px] ${numberError ? 'text-danger' : 'text-muted'}`}>
          {numberError ?? t('lister.identity.numberHint')}
        </p>
      </div>

      <ul className="mt-5 divide-y divide-mist/70">
        <StepRow icon={IdCardIcon} title={t('lister.identity.idRow')} body={t('lister.identity.idRowBody')} done={hasId} onOpen={() => onOpen('national_id_photo')} />
        <StepRow icon={SelfieIcon} title={t('lister.identity.selfieRow')} body={t('lister.identity.selfieRowBody')} done={hasSelfie} onOpen={() => onOpen('live_selfie')} />
      </ul>

      {error && (
        <div className="mt-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <div className="mt-auto pt-6 text-center">
        {ready && (
          <button
            type="button"
            onClick={onSubmit}
            disabled={busy}
            className="mb-5 inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light disabled:opacity-70"
          >
            {busy && <span className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" aria-hidden="true" />}
            {t('lister.identity.submit')}
          </button>
        )}
        <button type="button" onClick={() => setWhy((value) => !value)} aria-expanded={why} className="text-[14.5px] font-medium text-navy underline underline-offset-4">
          {t('lister.identity.why')}
        </button>
        <AnimatePresence initial={false}>
          {why && (
            <motion.p
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden text-left text-[13px] leading-relaxed text-navy-soft"
            >
              <span className="mt-3 block rounded-lg bg-paper px-4 py-3">{t('lister.identity.whyBody')}</span>
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function StepRow({ icon: Icon, title, body, done, onOpen }: { icon: typeof IdCardIcon; title: string; body: string; done: boolean; onOpen: () => void }) {
  const { t } = useTranslation()
  return (
    <li>
      <button type="button" onClick={onOpen} className="flex w-full items-start gap-3.5 py-4 text-left">
        <span className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-md border ${done ? 'border-success bg-success text-white' : 'border-[#b8c0cc] text-navy-soft'}`}>
          {done ? <TickIcon className="size-4" /> : <Icon className="size-4" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[15.5px] text-navy">{title}</span>
          <span className="mt-1 block text-[13px] leading-snug text-muted">{done ? t('lister.identity.added') : body}</span>
        </span>
        <ChevronRightIcon className="mt-3 size-4 shrink-0 text-navy-soft" />
      </button>
    </li>
  )
}

// L9's guide screens: close top left, a centred title and rule, a 2x2 grid of
// examples, then the privacy line and a full-width "Proceed".
function Guide({ title, body, examples, capture, onClose, onPick, error }: {
  title: string
  body: string
  examples: { art: ReactNode; label: string; good: boolean }[]
  capture: 'user' | 'environment'
  onClose: () => void
  onPick: (file: File | null) => void
  error: string | null
}) {
  const { t } = useTranslation()
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  return (
    <div className="flex min-h-[680px] flex-col bg-gradient-to-b from-gold/10 via-white to-white px-5 pt-5 pb-6">
      <button type="button" onClick={onClose} aria-label={t('lister.identity.close')} className="grid size-10 place-items-center rounded-full text-navy hover:bg-white">
        <CloseIcon className="size-5" />
      </button>
      <h2 className="mt-8 text-center text-[21px] font-semibold text-navy">{title}</h2>
      <p className="mx-auto mt-2 max-w-[310px] text-center text-[14px] leading-snug text-navy-soft">{body}</p>
      <ul className="mt-6 grid grid-cols-2 gap-x-3.5 gap-y-4">
        {examples.map((example) => (
          <li key={example.label} className="text-center">
            <div className="relative overflow-hidden rounded-lg border border-mist bg-paper">
              {example.art}
              <span className={`absolute top-2 left-2 grid size-[18px] place-items-center rounded-full text-white ${example.good ? 'bg-success' : 'bg-danger'}`}>
                {example.good ? <TickIcon className="size-3" /> : <CloseIcon className="size-3" />}
                <span className="sr-only">{example.good ? t('lister.identity.good') : t('lister.identity.bad')}</span>
              </span>
            </div>
            <p className="mt-1.5 text-[13px] text-navy-soft">{example.label}</p>
          </li>
        ))}
      </ul>
      {error && (
        <div className="mt-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <div className="mt-auto pt-6">
        <p className="flex items-start gap-3 text-[12.5px] leading-snug text-navy-soft">
          <LockIcon className="size-5 shrink-0 text-gold" />
          <span>{t('lister.identity.privacy')}</span>
        </p>
        <input
          ref={input}
          id={id}
          type="file"
          accept={PHOTO_TYPES.join(',')}
          capture={capture}
          className="sr-only"
          onChange={(event) => {
            onPick(event.target.files?.[0] ?? null)
            event.target.value = ''
          }}
        />
        <label htmlFor={id} className="mt-4 flex h-11 cursor-pointer items-center justify-center rounded-md bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light">
          {t('lister.identity.proceed')}
        </label>
      </div>
    </div>
  )
}

function IdGuide({ onClose, onPick, error }: { onClose: () => void; onPick: (file: File | null) => void; error: string | null }) {
  const { t } = useTranslation()
  return (
    <Guide
      title={t('lister.identity.idGuideTitle')}
      body={t('lister.identity.idGuideBody')}
      capture="environment"
      onClose={onClose}
      onPick={onPick}
      error={error}
      examples={[
        { art: <IdSample variant="good" />, label: t('lister.identity.idGood'), good: true },
        { art: <IdSample variant="glare" />, label: t('lister.identity.idGlare'), good: false },
        { art: <IdSample variant="copy" />, label: t('lister.identity.idCopy'), good: false },
        { art: <IdSample variant="half" />, label: t('lister.identity.idHalf'), good: false },
      ]}
    />
  )
}

function SelfieGuide({ onClose, onPick, error }: { onClose: () => void; onPick: (file: File | null) => void; error: string | null }) {
  const { t } = useTranslation()
  return (
    <Guide
      title={t('lister.identity.selfieGuideTitle')}
      body={t('lister.identity.selfieGuideBody')}
      capture="user"
      onClose={onClose}
      onPick={onPick}
      error={error}
      examples={[
        { art: <FaceSample variant="good" />, label: t('lister.identity.faceGood'), good: true },
        { art: <FaceSample variant="glasses" />, label: t('lister.identity.faceGlasses'), good: false },
        { art: <FaceSample variant="dark" />, label: t('lister.identity.faceDark'), good: false },
        { art: <FaceSample variant="partial" />, label: t('lister.identity.facePartial'), good: false },
      ]}
    />
  )
}

function usePreview(file: File): string {
  const [url] = useState(() => URL.createObjectURL(file))
  useEffect(() => () => URL.revokeObjectURL(url), [url])
  return url
}

// L7's third screen: the picture inside corner brackets, title and actions.
function IdConfirm({ file, busy, error, onBack, onUse }: { file: File; busy: boolean; error: string | null; onBack: () => void; onUse: () => void }) {
  const { t } = useTranslation()
  const url = usePreview(file)
  return (
    <div className="flex min-h-[680px] flex-col px-6 pt-6 pb-7">
      <button type="button" onClick={onBack} aria-label={t('lister.identity.back')} className="grid size-10 place-items-center rounded-full bg-paper text-navy hover:bg-mist/60">
        <ArrowLeftIcon className="size-5" />
      </button>
      <div className="relative mx-auto mt-10 w-full max-w-[270px] p-3">
        {['top-0 left-0 border-t-2 border-l-2', 'top-0 right-0 border-t-2 border-r-2', 'bottom-0 left-0 border-b-2 border-l-2', 'bottom-0 right-0 border-r-2 border-b-2'].map((corner) => (
          <span key={corner} aria-hidden="true" className={`absolute size-4 border-navy-soft ${corner}`} />
        ))}
        <img src={url} alt={t('lister.identity.idPreview')} className="aspect-[1.58] w-full rounded-lg object-cover" />
      </div>
      <h2 className="mt-9 text-[26px] leading-tight font-bold tracking-tight text-navy">{t('lister.identity.idConfirmTitle')}</h2>
      <p className="mt-2.5 text-[14.5px] text-navy-soft">{t('lister.identity.idConfirmBody')}</p>
      {error && (
        <div className="mt-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <div className="mt-auto space-y-3 pt-6">
        <button type="button" onClick={onUse} disabled={busy} className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light disabled:opacity-70">
          {busy && <span className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" aria-hidden="true" />}
          {t('lister.identity.usePhoto')}
        </button>
        <button type="button" onClick={onBack} disabled={busy} className="h-11 w-full text-[14.5px] font-medium text-navy underline underline-offset-4">
          {t('lister.identity.retake')}
        </button>
      </div>
    </div>
  )
}

// L7's middle screen: dark, the face in a dashed oval, a line of guidance,
// and a round shutter-style button to use the picture.
function SelfieConfirm({ file, busy, error, onBack, onUse }: { file: File; busy: boolean; error: string | null; onBack: () => void; onUse: () => void }) {
  const { t } = useTranslation()
  const url = usePreview(file)
  return (
    <div className="relative flex min-h-[680px] flex-col items-center bg-[#140e0b] px-6 pt-6 pb-8 text-white">
      <div className="flex w-full items-center">
        <button type="button" onClick={onBack} aria-label={t('lister.identity.back')} className="grid size-10 place-items-center rounded-full bg-white/10 hover:bg-white/20">
          <CloseIcon className="size-5" />
        </button>
        <h2 className="flex-1 pr-10 text-center text-[21px] font-semibold">{t('lister.identity.selfieConfirmTitle')}</h2>
      </div>
      <div className="relative mt-10 h-[330px] w-[250px]">
        <img src={url} alt={t('lister.identity.selfiePreview')} className="size-full rounded-[50%] object-cover" />
        <span aria-hidden="true" className="absolute inset-0 rounded-[50%] border-2 border-dashed border-white/90" />
      </div>
      <p className="mt-8 max-w-[300px] text-center text-[16px] leading-snug">{t('lister.identity.selfieConfirmBody')}</p>
      {error && (
        <div className="mt-4 w-full">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <div className="mt-auto flex w-full items-center justify-center gap-10 pt-6">
        <button type="button" onClick={onBack} disabled={busy} className="w-20 whitespace-nowrap text-[13px] text-white/75 hover:text-white">
          {t('lister.identity.retake')}
        </button>
        <button
          type="button"
          onClick={onUse}
          disabled={busy}
          aria-label={t('lister.identity.usePhoto')}
          className="grid size-[60px] place-items-center rounded-full border-[3px] border-white/90 disabled:opacity-60"
        >
          <span className={`size-[46px] rounded-full ${busy ? 'animate-pulse bg-gold' : 'bg-white'}`} />
        </button>
        <span className="w-20 whitespace-nowrap text-[13px] text-white/75">{t('lister.identity.use')}</span>
      </div>
    </div>
  )
}

function Status({ identity }: { identity: ListerIdentity | null }) {
  const { t, i18n } = useTranslation()
  if (!identity) return null
  const approved = identity.status === 'APPROVED'
  const waiting = identity.status === 'PENDING'
  return (
    <div className="flex min-h-[680px] flex-col items-center px-6 pt-16 pb-8 text-center">
      <span className={`grid size-20 place-items-center rounded-full ${approved ? 'bg-success-soft text-success' : waiting ? 'bg-gold/15 text-[#9a6c12]' : 'bg-danger-soft text-danger'}`}>
        {approved ? <TickIcon className="size-9" /> : waiting ? <ClockIcon className="size-9" /> : <CloseIcon className="size-9" />}
      </span>
      <h2 className="mt-7 text-[24px] leading-tight font-bold text-navy">{t(`lister.identity.status.${identity.status}.title`)}</h2>
      <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{t(`lister.identity.status.${identity.status}.body`)}</p>
      <dl className="mt-7 w-full divide-y divide-mist/80 rounded-xl border border-mist text-left text-[13.5px]">
        {identity.submitted_at && <Row label={t('lister.identity.sentOn')} value={formatDate(identity.submitted_at, i18n.language)} />}
        {identity.expires_at && approved && <Row label={t('lister.identity.validUntil')} value={formatDate(identity.expires_at, i18n.language)} />}
        {identity.review_reason && !approved && <Row label={t('lister.identity.reason')} value={identity.review_reason} />}
      </dl>
      {!approved && (
        <a
          href={whatsappLink(t('lister.identity.helpMessage'))}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-auto inline-flex h-11 items-center gap-2 rounded-xl border border-mist px-5 text-[14px] font-medium text-navy hover:border-navy-soft/40"
        >
          <WhatsAppIcon className="size-4" />
          {t('nav.helpAction')}
        </a>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 px-4 py-3">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right text-navy">{value}</dd>
    </div>
  )
}
