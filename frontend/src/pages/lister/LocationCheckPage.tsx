import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import {
  AlertIcon,
  CameraIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClockIcon,
  DocumentIcon,
  IdCardIcon,
  MapPinIcon,
  ShieldIcon,
  TrashIcon,
  WhatsAppIcon,
} from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { whatsappLink } from '../../lib/config'
import { errorMessage } from '../../lib/errors'
import { formatShortDate, formatTime } from '../../lib/format'
import { listerApi, type PropertyCheck, type PropertyCheckStatus } from '../../lib/listerApi'
import type { TitleType } from '../../lib/marketApi'
import { loadListingRows, rowTitle, type ListingRow } from './rows'

type Upload = { file: File; preview: string; mediaId: string | null; size: number; at: string | null; error: string | null }

const MAX_BYTES = 5 * 1024 * 1024
const TITLE_TILES: TitleType[] = ['REGISTERED_TITLE', 'RESIDENTIAL_LICENCE', 'SALE_AGREEMENT', 'CCRO', 'VILLAGE_RECORDS']

// VER-02, the lister's side, after L1, L5, L7 and L9: the property picked in
// the title (L7's "name ⌄"), the Level 2 block with what buyers see before
// and after and what the check needs (L1), the request with a step bar, the
// title type tiles, a dashed upload area opening a two-choice sheet and the
// uploaded row (L5, L7), then the check as a status card with a timeline (L9).
export function LocationCheckPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('lister.checks.title'))
  const [params, setParams] = useSearchParams()
  const [rows, setRows] = useState<ListingRow[] | null>(null)
  const [identityOk, setIdentityOk] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadListingRows().then(setRows, (caught) => setError(errorMessage(t, caught)))
    listerApi.identity().then(
      (identity) => setIdentityOk(identity.status === 'APPROVED' && (!identity.expires_at || new Date(identity.expires_at) > new Date())),
      () => setIdentityOk(false),
    )
  }, [t])

  // One entry per property: its latest listing carries the name and photo.
  const properties = useMemo(() => {
    const seen = new Map<string, ListingRow>()
    for (const row of rows ?? []) if (row.property && !seen.has(row.property.property_id)) seen.set(row.property.property_id, row)
    return [...seen.values()]
  }, [rows])

  if (error) return <Alert tone="error">{error}</Alert>
  if (!rows) return <FullPageLoader inline />

  const chosen = properties.find((row) => row.property?.property_id === params.get('property')) ?? properties[0]

  return (
    <div className="mx-auto max-w-[1180px]">
      {properties.length === 0 ? (
        <>
          <h1 className="text-[30px] leading-tight font-semibold text-navy sm:text-[36px]">{t('lister.checks.title')}</h1>
          <div className="mt-6 rounded-2xl border border-mist bg-white px-6 py-10 text-center">
            <p className="text-[15px] text-navy-soft">{t('lister.checks.noProperties')}</p>
            <Link to="/lister/listings/new" className="mt-4 inline-flex h-11 items-center rounded-xl bg-navy px-5 text-[14px] font-semibold text-white">
              {t('lister.checks.addListing')}
            </Link>
          </div>
        </>
      ) : (
        <PropertyPanel
          key={chosen.property!.property_id}
          row={chosen}
          properties={properties}
          onChoose={(id) => setParams({ property: id }, { replace: true })}
          identityOk={identityOk}
        />
      )}
    </div>
  )
}

function PropertyPanel({ row, properties, onChoose, identityOk }: {
  row: ListingRow
  properties: ListingRow[]
  onChoose: (propertyId: string) => void
  identityOk: boolean | null
}) {
  const { t } = useTranslation()
  const property = row.property!
  const [status, setStatus] = useState<PropertyCheckStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [requesting, setRequesting] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(() => {
    listerApi.checkStatus(property.property_id).then(setStatus, (caught) => setError(errorMessage(t, caught)))
  }, [property.property_id, t])

  useEffect(() => {
    load()
  }, [load])

  const latest = status?.verifications.find((check) => check.kind === 'DOCUMENT') ?? null
  const canRequest = !latest || ['REJECTED', 'EXPIRED', 'REVOKED'].includes(latest.status)
  const name = rowTitle(t, row)

  return (
    <>
      {/* L1: back, the screen name centred, and help on the right. */}
      <div className="mb-6 grid grid-cols-[40px_1fr_40px] items-center">
        <Link to="/lister" aria-label={t('lister.checks.back')} className="grid size-10 place-items-center rounded-full text-navy hover:bg-white">
          <ChevronLeftIcon className="size-6" />
        </Link>
        <p className="text-center text-[17px] font-semibold text-navy">{t('lister.checks.title')}</p>
        <a
          href={whatsappLink(t('lister.checks.helpMessage', { property: property.property_id }))}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={t('lister.checks.help')}
          className="grid size-10 place-items-center rounded-full text-navy hover:bg-white"
        >
          <HelpIcon className="size-6" />
        </a>
      </div>

      {/* L7: the subject in the title, with a chevron to switch. */}
      <header>
        <label className="relative inline-flex max-w-full items-center gap-2">
          <span className="sr-only">{t('lister.checks.choose')}</span>
          <h1 className="truncate text-[28px] leading-tight font-semibold text-navy sm:text-[36px]">{name}</h1>
          <ChevronDownIcon className="size-6 shrink-0 text-navy" />
          <select
            value={property.property_id}
            onChange={(event) => onChoose(event.target.value)}
            className="absolute inset-0 cursor-pointer opacity-0"
            aria-label={t('lister.checks.choose')}
          >
            {properties.map((item) => (
              <option key={item.property!.property_id} value={item.property!.property_id}>
                {rowTitle(t, item)} · {item.property!.property_id}
              </option>
            ))}
          </select>
        </label>
        <p className="mt-1 text-[14px] text-navy-soft">
          <span className="tabular-nums">{property.property_id}</span>
          {status && <> · {t('lister.checks.currentLevel', { level: t(`levels.short.${status.effective_verification_level}`) })}</>}
        </p>
      </header>

      {error && <div className="mt-5"><Alert tone="error">{error}</Alert></div>}
      {notice && <div className="mt-5"><Alert tone="success">{notice}</Alert></div>}

      {!status ? (
        <FullPageLoader inline />
      ) : requesting ? (
        <RequestFlow
          row={row}
          onCancel={() => setRequesting(false)}
          onSent={() => {
            setRequesting(false)
            setNotice(t('lister.checks.sent'))
            load()
          }}
        />
      ) : (
        <div className="mt-8 grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <LevelBlock
            check={latest}
            row={row}
            identityOk={identityOk}
            canRequest={canRequest}
            onRequest={() => {
              setNotice(null)
              setRequesting(true)
            }}
          />
          {latest && <CheckStatusPanel check={latest} row={row} canRequest={canRequest} onRequest={() => setRequesting(true)} />}
        </div>
      )}
    </>
  )
}

const TAG: Record<string, string> = {
  none: 'bg-mist/70 text-navy-soft',
  PENDING: 'bg-gold text-white',
  APPROVED: 'bg-success text-white',
  REJECTED: 'bg-danger text-white',
  EXPIRED: 'bg-navy-soft text-white',
  REVOKED: 'bg-navy-soft text-white',
}

// L1: the numbered level, its tag, then one card with the perks table and the requirements.
function LevelBlock({ check, row, identityOk, canRequest, onRequest }: {
  check: PropertyCheck | null
  row: ListingRow
  identityOk: boolean | null
  canRequest: boolean
  onRequest: () => void
}) {
  const { t } = useTranslation()
  const tag = check?.status ?? 'none'
  const hasPin = Boolean(row.property?.pin)
  const requirements = [
    { key: 'document', icon: DocumentIcon },
    { key: 'pin', icon: MapPinIcon },
    { key: 'identity', icon: IdCardIcon },
  ] as const
  return (
    <section aria-labelledby="level-title">
      <div className="flex items-center gap-3 sm:gap-4">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-navy text-[17px] font-semibold text-white sm:size-12 sm:text-[18px]">2</span>
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <h2 id="level-title" className="text-[18px] leading-snug font-semibold text-navy sm:text-[22px]">{t('lister.checks.levelTitle')}</h2>
          <span className={`rounded-md px-2.5 py-1 text-[13px] font-medium ${TAG[tag]}`}>{t(`lister.checks.tags.${tag}`)}</span>
        </div>
      </div>

      <div className="mt-5 rounded-2xl bg-navy px-6 py-6 text-white sm:ml-16 sm:px-7">
        <table className="w-full text-left">
          <thead>
            <tr className="align-bottom text-[17px] font-medium">
              <th scope="col" className="pb-2 font-medium">{t('lister.checks.perksNow')}</th>
              <th scope="col" className="pb-2 text-right font-medium">{t('lister.checks.perksAfter')}</th>
            </tr>
          </thead>
          <tbody className="text-[15px] text-white/70">
            <tr>
              <td className="py-2">{t('lister.checks.perks.badge')}</td>
              <td className="py-2 text-right text-white">{t('lister.checks.perks.badgeValue')}</td>
            </tr>
            {(['checked', 'filter', 'sort'] as const).map((key) => (
              <tr key={key}>
                <td className="py-2">{t(`lister.checks.perks.${key}`)}</td>
                <td className="py-2 text-right">
                  <span className="inline-grid size-6 place-items-center rounded-full border-2 border-gold-light text-gold-light">
                    <CheckIcon className="size-3.5" />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 className="mt-10 text-[17px] font-medium">{t('lister.checks.requirementsTitle')}</h3>
        <ul className="mt-3 space-y-3 text-[15px]">
          {requirements.map(({ key, icon: Icon }) => (
            <li key={key} className="flex items-center gap-3">
              <Icon className="size-5 shrink-0 text-white/80" />
              {t(`lister.checks.requirements.${key}`)}
            </li>
          ))}
          <li className="flex items-center gap-3">
            <ClockIcon className="size-5 shrink-0 text-white/80" />
            {t('lister.checks.requirements.time')}
          </li>
        </ul>
      </div>

      {canRequest && (
        <div className="mt-5 space-y-3 sm:ml-16">
          {identityOk === false && (
            <Gate icon={IdCardIcon} title={t('lister.checks.identityNeeded.title')} body={t('lister.checks.identityNeeded.body')} to="/lister/identity" action={t('lister.checks.identityNeeded.action')} />
          )}
          {!hasPin && (
            <Gate icon={MapPinIcon} title={t('lister.checks.pinNeeded.title')} body={t('lister.checks.pinNeeded.body')} to={`/lister/listings/${row.listing.listing_id}`} action={t('lister.checks.pinNeeded.action')} />
          )}
          {identityOk !== false && hasPin && !check && (
            <button
              type="button"
              onClick={onRequest}
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-navy px-6 text-[15px] font-semibold text-white transition-colors hover:bg-navy-soft sm:w-auto"
            >
              {check ? t('lister.checks.again') : t('lister.checks.start')}
              <ChevronRightIcon className="size-4" />
            </button>
          )}
        </div>
      )}
    </section>
  )
}

function Gate({ icon: Icon, title, body, to, action }: { icon: ComponentType<SVGProps<SVGSVGElement>>; title: string; body: string; to: string; action: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-gold/35 bg-[#fdf7ec] px-5 py-4 text-[#7a5410]">
      <Icon className="size-5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold">{title}</p>
        <p className="mt-0.5 text-[13px] text-navy-soft">{body}</p>
      </div>
      <Link to={to} className="inline-flex h-10 items-center rounded-lg bg-navy px-4 text-[13.5px] font-semibold text-white">{action}</Link>
    </div>
  )
}

function HelpIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true" {...props}>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.6M12 17h.01" />
    </svg>
  )
}

function Sparkle(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 12 12" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M6 0c.4 3.2 2.8 5.6 6 6-3.2.4-5.6 2.8-6 6-.4-3.2-2.8-5.6-6-6 3.2-.4 5.6-2.8 6-6Z" />
    </svg>
  )
}

// L9's wavy badge.
function Rosette(props: SVGProps<SVGSVGElement>) {
  const points = Array.from({ length: 24 }, (_, index) => {
    const angle = (index / 24) * Math.PI * 2
    const radius = index % 2 ? 21 : 24
    return `${24 + radius * Math.cos(angle)},${24 + radius * Math.sin(angle)}`
  }).join(' ')
  return (
    <svg viewBox="0 0 48 48" fill="currentColor" aria-hidden="true" {...props}>
      <polygon points={points} strokeLinejoin="round" stroke="currentColor" strokeWidth="3" />
    </svg>
  )
}

function UploadIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 8a4 4 0 0 1 .5 7.97" />
      <path d="M12 12v8M8.5 15.5 12 12l3.5 3.5" />
    </svg>
  )
}

function formatSize(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

// L5: the step trail, the title type tiles, the dashed area, the uploaded row and the privacy note.
function RequestFlow({ row, onCancel, onSent }: { row: ListingRow; onCancel: () => void; onSent: () => void }) {
  const { t, i18n } = useTranslation()
  const property = row.property!
  const [sheet, setSheet] = useState(false)
  const [upload, setUpload] = useState<Upload | null>(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const camera = useRef<HTMLInputElement>(null)
  const library = useRef<HTMLInputElement>(null)

  useEffect(() => () => {
    if (upload?.preview) URL.revokeObjectURL(upload.preview)
  }, [upload])

  async function choose(file: File | undefined) {
    setSheet(false)
    if (!file) return
    setError(null)
    if (file.size > MAX_BYTES) {
      setError(t('lister.checks.upload.tooBig'))
      return
    }
    const next: Upload = { file, preview: file.type === 'application/pdf' ? '' : URL.createObjectURL(file), mediaId: null, size: file.size, at: null, error: null }
    setUpload(next)
    try {
      const media = await listerApi.uploadTitleDocument(property.property_id, file)
      setUpload((current) => (current?.file === file ? { ...current, mediaId: media.media_id, at: media.created_at } : current))
    } catch (caught) {
      setUpload((current) => (current?.file === file ? { ...current, error: errorMessage(t, caught) } : current))
    }
  }

  async function send() {
    if (!upload?.mediaId) return
    setSending(true)
    setError(null)
    try {
      await listerApi.requestCheck(property.property_id, upload.mediaId)
      onSent()
    } catch (caught) {
      setError(errorMessage(t, caught))
      setSending(false)
    }
  }

  const steps = [
    { key: 'property', icon: MapPinIcon, done: true },
    { key: 'document', icon: DocumentIcon, done: Boolean(upload?.mediaId) },
    { key: 'send', icon: ShieldIcon, done: false },
  ] as const
  const current = upload?.mediaId ? 'send' : 'document'

  return (
    <section className="mx-auto mt-8 max-w-[640px]">
      <div className="mb-4 flex items-center justify-end">
        <span className="h-2 w-[42%] overflow-hidden rounded-full bg-mist">
          <span className="block h-full rounded-full bg-gold transition-[width] duration-500" style={{ width: upload?.mediaId ? '90%' : '60%' }} />
        </span>
      </div>
      <nav aria-label={t('lister.checks.steps.label')} className="rounded-2xl border border-mist bg-white p-2.5 shadow-[0_2px_10px_rgba(15,23,42,0.05)]">
        <ol className="flex items-center justify-between gap-1">
          {steps.map(({ key, icon: Icon, done }, index) => (
            <li key={key} className="flex min-w-0 flex-1 items-center gap-1">
              <span
                aria-current={key === current ? 'step' : undefined}
                className={`inline-flex min-w-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] whitespace-nowrap ${
                  key === current ? 'bg-gold/15 font-semibold text-[#7a5410]' : done ? 'bg-success-soft text-success' : 'text-navy-soft'
                }`}
              >
                {done && key !== current ? <CheckIcon className="size-4 shrink-0" /> : <Icon className="size-4 shrink-0" />}
                <span className="truncate">{t(`lister.checks.steps.${key}`)}</span>
              </span>
              {index < steps.length - 1 && <ChevronRightIcon className="mx-auto size-4 shrink-0 text-muted" />}
            </li>
          ))}
        </ol>
      </nav>

      <h2 className="mt-7 text-[22px] font-semibold text-navy">{t('lister.checks.upload.title')}</h2>
      <p className="mt-1 text-[14px] text-navy-soft">{t('lister.checks.upload.subtitle')}</p>

      <ul className="-mx-4 mt-5 flex gap-3 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:grid sm:grid-cols-5 sm:px-0">
        {TITLE_TILES.map((type) => {
          const on = property.title_type === type
          return (
            <li
              key={type}
              aria-current={on ? 'true' : undefined}
              className={`flex w-[104px] shrink-0 flex-col items-center gap-2 rounded-2xl border px-2 py-4 text-center sm:w-auto ${on ? 'border-gold bg-gold/10 text-navy' : 'border-mist bg-paper/60 text-muted'}`}
            >
              <span className={`grid size-11 place-items-center rounded-full ${on ? 'bg-white text-[#9a6c12]' : 'bg-white/80 text-muted'}`}>
                <DocumentIcon className="size-5" />
              </span>
              <span className={`text-[12px] leading-snug ${on ? 'font-semibold' : ''}`}>{t(`market.titleType.${type}`)}</span>
            </li>
          )
        })}
      </ul>
      <p className="mt-2 text-[12.5px] text-muted">{t('lister.checks.upload.tilesNote')}</p>

      <button
        type="button"
        onClick={() => setSheet(true)}
        className="mt-5 flex w-full flex-col items-center rounded-2xl border-2 border-dashed border-gold/50 bg-white px-6 py-9 text-center transition-colors hover:bg-[#fffaf1]"
      >
        <span className="relative grid size-24 place-items-center">
          <span aria-hidden="true" className="absolute inset-0 rounded-full bg-gold/10" />
          <span className="relative grid size-16 place-items-center rounded-full bg-gold/20 text-[#9a6c12]">
            <UploadIcon className="size-9" />
          </span>
          {[['-left-5 top-7', 'size-2.5'], ['-right-4 top-3', 'size-3'], ['-right-6 bottom-6', 'size-2'], ['-left-2 -top-1', 'size-1.5'], ['left-1 bottom-0', 'size-1.5']].map(([where, size]) => (
            <Sparkle key={where} className={`absolute text-gold/60 ${where} ${size}`} />
          ))}
        </span>
        <span className="mt-4 text-[17px] font-semibold text-navy">{t('lister.checks.upload.dropTitle')}</span>
        <span className="mt-1 text-[13.5px] text-muted">{t('lister.checks.upload.dropHint')}</span>
      </button>
      <input ref={camera} type="file" accept="image/*" capture="environment" className="hidden" onChange={(event) => void choose(event.target.files?.[0])} />
      <input ref={library} type="file" accept="application/pdf,image/jpeg,image/png,image/webp" className="hidden" onChange={(event) => void choose(event.target.files?.[0])} />

      <div className="mt-6 flex items-baseline justify-between">
        <h3 className="text-[17px] font-semibold text-navy">{t('lister.checks.upload.listTitle')}</h3>
        <p className="text-[13.5px] text-[#9a6c12]">
          <span className="text-[16px] font-semibold">{upload?.mediaId ? 1 : 0}/1</span> {t('lister.checks.upload.uploaded')}
        </p>
      </div>
      {upload && (
        <div className="mt-3 flex items-center gap-4 rounded-2xl border border-mist bg-white p-3.5 shadow-[0_2px_10px_rgba(15,23,42,0.05)]">
          {upload.preview ? (
            <img src={upload.preview} alt="" className="h-[72px] w-[104px] shrink-0 rounded-lg border border-mist object-cover" />
          ) : (
            <span className="grid h-[72px] w-[104px] shrink-0 place-items-center rounded-lg border border-mist bg-paper text-danger">
              <span className="flex flex-col items-center gap-1">
                <DocumentIcon className="size-6" />
                <span className="text-[11px] font-semibold tracking-wide">PDF</span>
              </span>
            </span>
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-[15px] font-medium text-navy">{upload.file.name}</p>
            <p className="text-[12.5px] text-navy-soft">
              {upload.at
                ? t('lister.checks.upload.uploadedOn', { date: `${formatShortDate(upload.at, i18n.language)} ${formatTime(upload.at, i18n.language)}`, size: formatSize(upload.size) })
                : formatSize(upload.size)}
            </p>
            {upload.error ? (
              <p className="mt-1.5 text-[12.5px] text-danger">{upload.error}</p>
            ) : upload.mediaId ? (
              <span className="mt-1.5 inline-flex items-center gap-1.5 rounded-full bg-success-soft px-2.5 py-0.5 text-[12px] font-medium text-success">
                <CheckIcon className="size-3.5" />
                {t('lister.checks.upload.uploaded')}
              </span>
            ) : (
              <span className="mt-2 block">
                <span className="block h-1.5 overflow-hidden rounded-full bg-mist">
                  <span className="block h-full w-1/2 animate-[pulse_1.2s_ease-in-out_infinite] rounded-full bg-gold" />
                </span>
                <span className="mt-1 block text-[12px] text-muted">{t('lister.checks.upload.uploading')}</span>
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setUpload(null)}
            aria-label={t('lister.checks.upload.remove')}
            className="grid size-11 shrink-0 place-items-center rounded-xl border border-mist bg-paper text-danger hover:bg-danger-soft"
          >
            <TrashIcon className="size-[18px]" />
          </button>
        </div>
      )}

      <p className="mt-5 flex items-center gap-3 rounded-2xl bg-[#fdf1dc] px-4 py-3.5 text-[14px] text-[#5c3f0b]">
        <ShieldIcon className="size-7 shrink-0 text-gold" />
        {t('lister.checks.upload.privacy')}
      </p>

      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}

      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button type="button" onClick={onCancel} className="inline-flex h-12 items-center justify-center rounded-xl border border-mist bg-white px-6 text-[15px] font-medium text-navy">
          {t('lister.checks.upload.cancel')}
        </button>
        <button
          type="button"
          onClick={send}
          disabled={!upload?.mediaId || sending}
          className="inline-flex h-12 items-center justify-center rounded-xl bg-navy px-6 text-[15px] font-semibold text-white transition-colors hover:bg-navy-soft disabled:cursor-not-allowed disabled:opacity-45"
        >
          {sending ? t('lister.checks.upload.sending') : t('lister.checks.upload.send')}
        </button>
      </div>

      <AnimatePresence>
        {sheet && (
          <AddSheet
            onClose={() => setSheet(false)}
            onCamera={() => camera.current?.click()}
            onLibrary={() => library.current?.click()}
          />
        )}
      </AnimatePresence>
    </section>
  )
}

// L7: a sheet with a handle, a title, one line, and two side-by-side choices.
function AddSheet({ onClose, onCamera, onLibrary }: { onClose: () => void; onCamera: () => void; onLibrary: () => void }) {
  const { t } = useTranslation()
  const first = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    first.current?.focus()
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  const choice = 'flex flex-col items-center rounded-2xl border-2 border-navy px-4 py-5 text-center transition-colors hover:bg-paper'
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[1000] flex items-end justify-center bg-navy/40 sm:items-center" onClick={onClose}>
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby="sheet-title"
        initial={{ y: 40 }}
        animate={{ y: 0 }}
        exit={{ y: 40 }}
        transition={{ duration: 0.22 }}
        onClick={(event) => event.stopPropagation()}
        className="relative w-full max-w-[460px] rounded-t-[28px] bg-white px-6 pt-3 pb-8 shadow-[0_-10px_40px_rgba(15,23,42,0.2)] sm:rounded-[28px]"
      >
        <span aria-hidden="true" className="mx-auto block h-1.5 w-11 rounded-full bg-mist" />
        <h2 id="sheet-title" className="mt-5 text-center text-[22px] font-semibold text-navy">{t('lister.checks.sheet.title')}</h2>
        <p className="mt-2 text-center text-[15px] leading-relaxed text-navy-soft">{t('lister.checks.sheet.body')}</p>
        <div className="mt-6 grid grid-cols-2 gap-3">
          <button ref={first} type="button" onClick={onLibrary} className={choice}>
            <UploadIcon className="size-7 text-navy" />
            <span className="mt-3 text-[16px] font-semibold text-navy">{t('lister.checks.sheet.files')}</span>
            <span className="mt-1.5 text-[13px] leading-snug text-muted">{t('lister.checks.sheet.filesBody')}</span>
          </button>
          <button type="button" onClick={onCamera} className={choice}>
            <CameraIcon className="size-7 text-navy" />
            <span className="mt-3 text-[16px] font-semibold text-navy">{t('lister.checks.sheet.camera')}</span>
            <span className="mt-1.5 text-[13px] leading-snug text-muted">{t('lister.checks.sheet.cameraBody')}</span>
          </button>
        </div>
        <p className="mt-6 flex items-center gap-3 text-[12px] font-medium tracking-[0.08em] text-muted uppercase">
          <span className="h-px flex-1 bg-mist" />
          {t('lister.checks.sheet.or')}
          <span className="h-px flex-1 bg-mist" />
        </p>
        <p className="mt-4 text-center text-[15px] leading-relaxed text-navy">
          {t('lister.checks.sheet.whatsappBefore')}{' '}
          <a href={whatsappLink(t('lister.checks.sheet.whatsappMessage'))} target="_blank" rel="noopener noreferrer" className="font-medium text-[#9a6c12] underline-offset-2 hover:underline">
            {t('lister.checks.sheet.whatsappLink')}
          </a>{' '}
          {t('lister.checks.sheet.whatsappAfter')}
        </p>
      </motion.div>
    </motion.div>
  )
}

// L9: the status card with a progress bar, the timeline, the details and help.
function CheckStatusPanel({ check, row, canRequest, onRequest }: { check: PropertyCheck; row: ListingRow; canRequest: boolean; onRequest: () => void }) {
  const { t, i18n } = useTranslation()
  const when = (value: string) => `${formatShortDate(value, i18n.language)} · ${formatTime(value, i18n.language)}`
  const decided = check.status !== 'PENDING'
  const passed = check.status === 'APPROVED'
  const progress = decided ? 100 : 66
  const steps = [
    { key: 'sent', at: check.submitted_at, done: true },
    { key: 'received', at: check.submitted_at, done: true },
    { key: 'review', at: check.reviewed_at, done: Boolean(check.reviewed_at), active: !decided },
    { key: check.status === 'REJECTED' ? 'failed' : check.reviewed_at ? 'passed' : 'decision', at: check.reviewed_at, done: Boolean(check.reviewed_at) },
    { key: 'level', at: passed ? check.reviewed_at : null, done: passed, note: passed && check.expires_at ? t('lister.checks.timeline.validUntil', { date: formatShortDate(check.expires_at, i18n.language) }) : null },
  ]
  const failed = check.status === 'REJECTED'
  const tone = passed ? 'from-success to-[#34a36b]' : failed ? 'from-danger to-[#e0675a]' : 'from-navy to-gold'

  return (
    <section className="space-y-5">
      <h2 className="text-center text-[19px] font-semibold text-navy tabular-nums">{t('lister.checks.requestNumber', { number: check.id.slice(0, 8).toUpperCase() })}</h2>
      <div className="rounded-3xl border border-mist bg-white p-5 shadow-[0_2px_14px_rgba(15,23,42,0.06)]">
        <div className="flex items-start gap-4">
          <span className={`relative grid size-12 shrink-0 place-items-center ${passed ? 'text-success' : failed ? 'text-danger' : 'text-gold'}`}>
            <Rosette className="absolute inset-0 size-full" />
            <span className="relative text-white">
              {passed ? <CheckIcon className="size-5" /> : failed ? <AlertIcon className="size-5" /> : <ClockIcon className="size-5" />}
            </span>
          </span>
          <div>
            <h3 className="text-[20px] font-semibold text-navy">{t(`lister.checks.status.${check.status}.title`)}</h3>
            <p className="mt-0.5 text-[14px] text-navy-soft">{t(`lister.checks.status.${check.status}.body`)}</p>
          </div>
        </div>
        <div className="mt-5 flex items-center gap-3">
          <div className="relative h-2.5 flex-1 rounded-full bg-mist/70">
            <div className={`h-full rounded-full bg-gradient-to-r ${tone}`} style={{ width: `${progress}%` }} />
            <span className="absolute top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-navy shadow" style={{ left: `${progress}%` }} />
          </div>
          <span className="text-[14px] font-medium text-navy tabular-nums">{progress}%</span>
        </div>
      </div>

      {failed && check.reason && (
        <div className="rounded-2xl border border-danger/25 bg-danger-soft/60 px-5 py-4">
          <p className="text-[13px] font-semibold text-danger">{t('lister.checks.reasonTitle')}</p>
          <p className="mt-1 text-[15px] text-navy">{check.reason}</p>
        </div>
      )}

      <div>
        <h3 className="text-[18px] font-semibold text-navy">{t('lister.checks.timelineTitle')}</h3>
        <ol className="mt-3 rounded-3xl border border-mist bg-white px-5 py-4">
          {steps.map((step, index) => (
            <li key={step.key} className="relative flex gap-4 pb-4 last:pb-0">
              {index < steps.length - 1 && <span aria-hidden="true" className="absolute top-6 bottom-0 left-[11px] w-px bg-mist" />}
              <span
                className={`relative mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border-2 ${
                  step.done ? 'border-navy bg-navy' : step.active ? 'border-gold bg-gold/20' : 'border-mist bg-white'
                }`}
              >
                {(step.done || step.active) && <span className={`size-2 rounded-full ${step.done ? 'bg-gold-light' : 'bg-gold'}`} />}
              </span>
              <div>
                <p className={`text-[15px] ${step.done || step.active ? 'font-medium text-navy' : 'text-navy-soft'}`}>{t(`lister.checks.timeline.${step.key}`)}</p>
                <p className="text-[12.5px] text-muted">
                  {step.at ? when(step.at) : step.active ? t('lister.checks.requirements.time') : t('lister.checks.timeline.pending')}
                </p>
                {step.note && <p className="text-[12.5px] text-success">{step.note}</p>}
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="rounded-3xl border border-mist bg-white px-5 py-4">
        <h3 className="text-[16px] font-semibold text-navy">{t('lister.checks.detailsTitle')}</h3>
        <dl className="mt-3 space-y-2.5 text-[14px]">
          {[
            ['property', rowTitle(t, row)],
            ['titleType', t(`market.titleType.${row.property!.title_type}`)],
            ['sent', when(check.submitted_at)],
            ['reference', check.id.slice(0, 8).toUpperCase()],
          ].map(([key, value]) => (
            <div key={key} className="flex justify-between gap-4">
              <dt className="text-navy-soft">{t(`lister.checks.details.${key}`)}</dt>
              <dd className="text-right font-medium text-navy tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="space-y-3">
        {canRequest && (
          <button type="button" onClick={onRequest} className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-navy text-[15px] font-semibold text-white hover:bg-navy-soft">
            <DocumentIcon className="size-5" />
            {t('lister.checks.again')}
          </button>
        )}
        <a
          href={whatsappLink(t('lister.checks.helpMessage', { property: row.property!.property_id }))}
          target="_blank"
          rel="noopener noreferrer"
          className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl border border-navy/25 bg-white text-[15px] font-medium text-navy hover:border-navy/50"
        >
          <WhatsAppIcon className="size-5" />
          {t('lister.checks.help')}
        </a>
      </div>
    </section>
  )
}
