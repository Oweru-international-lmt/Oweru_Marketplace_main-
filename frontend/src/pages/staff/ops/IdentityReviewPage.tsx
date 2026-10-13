import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { ArrowLeftIcon, ClockIcon, CloseIcon, IdCardIcon, ImageIcon, SelfieIcon, TickIcon, UsersIcon, WhatsAppIcon } from '../../../components/icons'
import { PageHeader } from '../../../components/PageHeader'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'
import { initials } from '../../../lib/initials'
import { staffApi, type IdentityPhoto, type IdentityQueueItem, type IdentityReview } from '../../../lib/staffApi'
import { useMediaQuery } from '../../../lib/useMediaQuery'
import { SearchBox } from './ui'

const DAY = 86_400_000
const PHOTOS: IdentityPhoto[] = ['national_id_photo', 'live_selfie']

// IDV-03 after R1: the queue on the left and the open record on the right,
// with R2's count cards above, R7's person column and check cards, the two
// photos large side by side, and R6's decision box with its history.
export function IdentityReviewPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { identityId } = useParams()
  const wide = useMediaQuery('(min-width: 1280px)')
  const [queue, setQueue] = useState<IdentityQueueItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [oldestFirst, setOldestFirst] = useState(true)
  const [now] = useState(() => Date.now())

  const load = useCallback(() => {
    staffApi.identities().then(setQueue, (caught) => setError(errorMessage(t, caught)))
  }, [t])

  useEffect(() => {
    load()
  }, [load])

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (queue ?? [])
      .filter((item) => !needle || `${item.user_full_name} ${item.id}`.toLowerCase().includes(needle))
      .sort((a, b) => (oldestFirst ? 1 : -1) * a.submitted_at.localeCompare(b.submitted_at))
  }, [queue, query, oldestFirst])

  // On wide screens the first in line opens by itself.
  const selected = identityId ?? (wide ? shown[0]?.id : undefined)
  const waitedDays = (item: IdentityQueueItem) => Math.floor((now - new Date(item.submitted_at).getTime()) / DAY)
  const list = queue ?? []

  const showList = wide || !identityId
  const showDetail = wide || Boolean(identityId)

  return (
    <>
      <PageHeader title={t('staff.identity.title')} description={t('staff.identity.subtitle')} />
      {error && <Alert tone="error">{error}</Alert>}

      {showList && (
        <div className="mb-5 grid gap-4 sm:grid-cols-3">
          <CountCard label={t('staff.identity.counts.waiting')} value={queue ? list.length : '-'} note={t('staff.identity.counts.waitingNote')} />
          <CountCard
            label={t('staff.identity.counts.late')}
            value={queue ? list.filter((item) => waitedDays(item) >= 2).length : '-'}
            note={t('staff.identity.counts.lateNote')}
            warn={list.some((item) => waitedDays(item) >= 2)}
          />
          <CountCard
            label={t('staff.identity.counts.week')}
            value={queue ? list.filter((item) => now - new Date(item.submitted_at).getTime() < 7 * DAY).length : '-'}
            note={t('staff.identity.counts.weekNote')}
          />
        </div>
      )}

      <div className={`grid items-start gap-5 ${wide ? 'grid-cols-[380px_minmax(0,1fr)]' : 'grid-cols-[minmax(0,1fr)]'}`}>
        {showList && (
          <section className="rounded-2xl border border-mist/70 bg-white p-4">
            <div className="flex items-end gap-3">
              <label className="block min-w-0 flex-1">
                <span className="mb-1 block text-[12px] text-muted">{t('staff.identity.order')}</span>
                <select
                  value={oldestFirst ? 'oldest' : 'newest'}
                  onChange={(event) => setOldestFirst(event.target.value === 'oldest')}
                  className="h-10 w-full rounded-lg border border-mist bg-white px-3 text-[13px] text-navy outline-none focus:border-gold"
                >
                  <option value="oldest">{t('staff.identity.oldest')}</option>
                  <option value="newest">{t('staff.identity.newest')}</option>
                </select>
              </label>
            </div>
            <div className="mt-3 [&_label]:w-full">
              <SearchBox label={t('staff.identity.search')} value={query} onChange={setQuery} />
            </div>
            <table className="mt-4 w-full text-left">
              <caption className="sr-only">{t('staff.identity.queue')}</caption>
              <thead>
                <tr className="bg-paper text-[11px] tracking-[0.06em] text-navy-soft uppercase">
                  <th scope="col" className="rounded-l-md px-3 py-2.5 font-medium">{t('staff.identity.columns.name')}</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">{t('staff.identity.columns.sent')}</th>
                  <th scope="col" className="rounded-r-md px-3 py-2.5 text-right font-medium">{t('staff.identity.columns.waiting')}</th>
                </tr>
              </thead>
              <tbody>
                {queue === null &&
                  [0, 1, 2].map((row) => (
                    <tr key={row}>
                      <td colSpan={3} className="px-3 py-3">
                        <div className="h-8 animate-pulse rounded bg-paper" />
                      </td>
                    </tr>
                  ))}
                {queue !== null && shown.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-3 py-10 text-center text-[13px] text-muted">
                      {list.length === 0 ? t('staff.identity.empty') : t('staff.identity.noMatch')}
                    </td>
                  </tr>
                )}
                {shown.map((item) => {
                  const on = item.id === selected
                  const days = waitedDays(item)
                  return (
                    <tr
                      key={item.id}
                      onClick={() => navigate(`/staff/identities/${item.id}`)}
                      className={`cursor-pointer border-b border-mist/60 text-[13px] text-navy transition-colors last:border-0 ${on ? 'bg-gold/10' : 'hover:bg-paper'}`}
                    >
                      <td className="px-3 py-3">
                        <Link to={`/staff/identities/${item.id}`} className="flex items-center gap-2.5" aria-current={on ? 'true' : undefined}>
                          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-gold/15 text-[11px] font-semibold text-[#7a5410]">
                            {initials(item.user_full_name)}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{item.user_full_name}</span>
                            <span className="block text-[11px] text-muted">#{item.id.slice(0, 6).toUpperCase()}</span>
                          </span>
                        </Link>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap text-navy-soft">{formatShortDate(item.submitted_at, i18n.language)}</td>
                      <td className="px-3 py-3 text-right">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] whitespace-nowrap ${
                            days >= 2 ? 'border-danger/30 bg-danger-soft text-danger' : 'border-gold/40 bg-gold/10 text-[#7a5410]'
                          }`}
                        >
                          {days === 0 ? t('staff.identity.today') : t('staff.identity.days', { count: days })}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </section>
        )}

        {showDetail &&
          (selected ? (
            <Review
              key={selected}
              identityId={selected}
              showBack={!wide}
              onDecided={() => {
                // Keep the decided record open (it leaves the queue) until the next is picked.
                navigate(`/staff/identities/${selected}`, { replace: true })
                load()
              }}
            />
          ) : (
            <section className="grid min-h-[420px] place-items-center rounded-2xl border border-mist/70 bg-white p-8 text-center">
              <div>
                <span className="mx-auto grid size-14 place-items-center rounded-full bg-paper text-navy-soft">
                  <UsersIcon className="size-6" />
                </span>
                <p className="mt-4 text-[15px] text-navy">{queue !== null && list.length === 0 ? t('staff.identity.allDone') : t('staff.identity.pick')}</p>
              </div>
            </section>
          ))}
      </div>
    </>
  )
}

// R2: a label, a large figure and one line under it.
function CountCard({ label, value, note, warn = false }: { label: string; value: ReactNode; note: string; warn?: boolean }) {
  return (
    <div className="rounded-2xl border border-mist/70 bg-white px-5 py-4">
      <p className="text-[14px] text-navy">{label}</p>
      <p className={`mt-3 text-[34px] leading-none font-medium tabular-nums ${warn ? 'text-danger' : 'text-navy'}`}>{value}</p>
      <p className="mt-3 text-[12.5px] text-muted">{note}</p>
    </div>
  )
}

function Review({ identityId, onDecided, showBack }: { identityId: string; onDecided: () => void; showBack: boolean }) {
  const { t, i18n } = useTranslation()
  const [identity, setIdentity] = useState<IdentityReview | null>(null)
  const [photos, setPhotos] = useState<Partial<Record<IdentityPhoto, string | null>>>({})
  const [error, setError] = useState<string | null>(null)
  const [zoom, setZoom] = useState<IdentityPhoto | null>(null)

  useEffect(() => {
    let live = true
    staffApi.identity(identityId).then(
      (found) => live && setIdentity(found),
      (caught) => live && setError(errorMessage(t, caught)),
    )
    for (const kind of PHOTOS) {
      staffApi.identityPhoto(identityId, kind).then(
        (link) => live && setPhotos((current) => ({ ...current, [kind]: link.url })),
        () => live && setPhotos((current) => ({ ...current, [kind]: null })),
      )
    }
    return () => {
      live = false
    }
  }, [identityId, t])

  if (error) return <Alert tone="error">{error}</Alert>
  if (!identity) return <section className="min-h-[520px] animate-pulse rounded-2xl border border-mist/70 bg-white" aria-busy="true" />

  const decided = identity.status !== 'PENDING'
  const checks: { key: string; label: string; ok: boolean; icon: typeof IdCardIcon; detail: string }[] = [
    { key: 'number', label: t('staff.identity.checks.number'), ok: Boolean(identity.national_id_number), icon: IdCardIcon, detail: identity.national_id_number || t('staff.identity.checks.missing') },
    { key: 'photo', label: t('staff.identity.checks.photo'), ok: Boolean(identity.national_id_photo_ref), icon: ImageIcon, detail: t('staff.identity.checks.attached') },
    { key: 'selfie', label: t('staff.identity.checks.selfie'), ok: Boolean(identity.live_selfie_ref), icon: SelfieIcon, detail: t('staff.identity.checks.camera') },
    {
      key: 'whatsapp',
      label: t('staff.identity.checks.whatsapp'),
      ok: identity.whatsapp_confirmed,
      icon: WhatsAppIcon,
      detail: identity.whatsapp_confirmed ? t('staff.identity.checks.confirmed') : t('staff.identity.checks.linkPending'),
    },
  ]

  return (
    <section className="rounded-2xl border border-mist/70 bg-white p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3 border-b border-mist pb-4">
        <div className="flex items-center gap-3">
          {showBack && (
            <Link to="/staff/identities" aria-label={t('staff.identity.back')} className="grid size-9 place-items-center rounded-full border border-mist text-navy hover:border-navy/30">
              <ArrowLeftIcon className="size-4" />
            </Link>
          )}
          <h2 className="text-[18px] font-semibold text-navy">{t('staff.identity.review')}</h2>
        </div>
        <StatusChip status={identity.status} />
      </div>

      {/* R1 and R7: the person, then one card per check. */}
      <div className="mt-5 flex items-center gap-4 rounded-xl border border-mist px-4 py-4">
        <span className="grid size-14 shrink-0 place-items-center rounded-full bg-gold/15 text-[18px] font-semibold text-[#7a5410]">{initials(identity.user_full_name)}</span>
        <div className="min-w-0">
          <p className="truncate text-[19px] font-medium text-navy">{identity.user_full_name}</p>
          <p className="mt-0.5 text-[13px] text-muted">
            {identity.submitted_at ? t('staff.identity.sentOn', { date: formatShortDate(identity.submitted_at, i18n.language) }) : ''} · #{identity.id.slice(0, 6).toUpperCase()}
          </p>
        </div>
      </div>

      <ul className="mt-4 grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
        {checks.map(({ key, label, ok, icon: Icon, detail }) => (
          <li key={key} className="rounded-xl border border-mist px-4 py-3.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
            <p className="flex items-center gap-2 text-[14px] font-medium text-navy">
              <Icon className="size-4 text-navy-soft" />
              {label}
            </p>
            <p className="mt-1 truncate text-[12.5px] text-muted">{detail}</p>
            <span className={`mt-2.5 inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium ${ok ? 'bg-success-soft text-success' : 'bg-gold/15 text-[#7a5410]'}`}>
              {ok ? t('staff.identity.checks.passed') : t('staff.identity.checks.review')}
            </span>
          </li>
        ))}
      </ul>

      {/* IDV-03: the two photos side by side. */}
      <div className="mt-6 flex items-center justify-between border-b border-mist pb-2.5">
        <h3 className="text-[16px] font-semibold text-navy">{t('staff.identity.photos')}</h3>
        <span className="rounded-md bg-paper px-2.5 py-1 text-[12px] text-navy-soft">{t('staff.identity.compare')}</span>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {PHOTOS.map((kind) => (
          <figure key={kind}>
            <figcaption className="mb-2 text-[13px] text-navy">{t(`staff.identity.kinds.${kind}`)}</figcaption>
            <div className="relative aspect-[4/3] overflow-hidden rounded-xl border border-mist bg-paper">
              {photos[kind] ? (
                <img src={photos[kind] ?? ''} alt={t(`staff.identity.kinds.${kind}`)} className="size-full object-contain" />
              ) : (
                <span className="grid size-full place-items-center text-[13px] text-muted">
                  {photos[kind] === null ? t('staff.identity.photoMissing') : <span className="size-5 animate-spin rounded-full border-2 border-gold/25 border-t-gold" />}
                </span>
              )}
              {photos[kind] && (
                <button
                  type="button"
                  onClick={() => setZoom(kind)}
                  className="absolute top-3 right-3 inline-flex h-8 items-center gap-1.5 rounded-lg bg-white/95 px-3 text-[12.5px] font-medium text-navy shadow-sm hover:bg-white"
                >
                  {t('staff.identity.viewFull')}
                </button>
              )}
            </div>
          </figure>
        ))}
      </div>

      {/* R6: the decision box, with the history beside it on wide screens. */}
      <div className="mt-6 grid gap-5 border-t border-mist pt-5 2xl:grid-cols-[minmax(0,1fr)_260px]">
        {decided ? <Outcome identity={identity} /> : <Decision identity={identity} onDone={(updated) => { setIdentity(updated); onDecided() }} />}
        <History identity={identity} />
      </div>

      <AnimatePresence>
        {zoom && photos[zoom] && <Zoom src={photos[zoom] ?? ''} title={t(`staff.identity.kinds.${zoom}`)} onClose={() => setZoom(null)} />}
      </AnimatePresence>
    </section>
  )
}

function StatusChip({ status }: { status: IdentityReview['status'] }) {
  const { t } = useTranslation()
  const tone = { PENDING: 'border-gold/40 bg-gold/10 text-[#7a5410]', APPROVED: 'border-success/35 bg-success-soft text-success', REJECTED: 'border-danger/30 bg-danger-soft text-danger', EXPIRED: 'border-mist bg-paper text-muted' }[status]
  return <span className={`rounded-full border px-2.5 py-0.5 text-[12px] ${tone}`}>{t(`staff.identity.statuses.${status}`)}</span>
}

function Decision({ identity, onDone }: { identity: IdentityReview; onDone: (identity: IdentityReview) => void }) {
  const { t } = useTranslation()
  const [choice, setChoice] = useState<'approve' | 'reject' | ''>('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!choice) {
      setError(t('staff.identity.chooseFirst'))
      return
    }
    if (choice === 'reject' && !reason.trim()) {
      setError(t('staff.identity.reasonNeeded'))
      return
    }
    setBusy(true)
    try {
      onDone(choice === 'approve' ? await staffApi.approveIdentity(identity.id) : await staffApi.rejectIdentity(identity.id, reason.trim()))
    } catch (caught) {
      setError(errorMessage(t, caught))
      setBusy(false)
    }
  }

  const tiles = [
    { value: 'approve' as const, label: t('staff.identity.approve'), on: 'border-success bg-success-soft text-success', dot: 'border-success', fill: 'bg-success' },
    { value: 'reject' as const, label: t('staff.identity.reject'), on: 'border-danger bg-danger-soft text-danger', dot: 'border-danger', fill: 'bg-danger' },
  ]

  return (
    <form onSubmit={(event) => void submit(event)}>
      <h3 className="text-[16px] font-semibold text-navy">{t('staff.identity.decision')}</h3>
      <p className="mt-1 text-[13px] text-muted">{t('staff.identity.decisionBody')}</p>
      <div role="radiogroup" aria-label={t('staff.identity.decision')} className="mt-4 flex flex-wrap gap-3">
        {tiles.map((tile) => {
          const on = choice === tile.value
          return (
            <button
              key={tile.value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => setChoice(tile.value)}
              className={`inline-flex h-10 items-center gap-2.5 rounded-lg border px-4 text-[13.5px] font-medium transition-colors ${on ? tile.on : 'border-mist text-navy hover:border-navy/30'}`}
            >
              <span className={`grid size-4 place-items-center rounded-full border ${on ? tile.dot : 'border-[#b8c0cc]'}`}>{on && <span className={`size-2 rounded-full ${tile.fill}`} />}</span>
              {tile.label}
            </button>
          )
        })}
      </div>
      <label htmlFor="identity-reason" className="mt-5 block text-[13.5px] font-medium text-navy">
        {choice === 'reject' ? t('staff.identity.reason') : t('staff.identity.reasonOptional')}
      </label>
      <textarea
        id="identity-reason"
        rows={3}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        placeholder={t('staff.identity.reasonPlaceholder')}
        disabled={choice === 'approve'}
        className="mt-2 block w-full rounded-lg border border-mist px-3.5 py-3 text-[14px] text-navy outline-none placeholder:text-muted/70 focus:border-gold focus:ring-2 focus:ring-gold/20 disabled:bg-paper"
      />
      <p className="mt-1.5 text-[12px] text-muted">{t('staff.identity.reasonHint')}</p>
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      <div className="mt-5 flex justify-end">
        <button type="submit" disabled={busy} className="inline-flex h-11 items-center gap-2 rounded-lg bg-gold px-5 text-[14px] font-semibold text-navy hover:bg-gold-light disabled:opacity-60">
          {busy && <span className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" aria-hidden="true" />}
          {t('staff.identity.submit')}
        </button>
      </div>
    </form>
  )
}

function Outcome({ identity }: { identity: IdentityReview }) {
  const { t, i18n } = useTranslation()
  const approved = identity.status === 'APPROVED'
  return (
    <div className={`rounded-xl border px-5 py-4 ${approved ? 'border-success/30 bg-success-soft' : 'border-danger/25 bg-danger-soft'}`}>
      <p className={`flex items-center gap-2 text-[15px] font-semibold ${approved ? 'text-success' : 'text-danger'}`}>
        {approved ? <TickIcon className="size-4" /> : <CloseIcon className="size-4" />}
        {approved ? t('staff.identity.approvedTitle') : t('staff.identity.rejectedTitle')}
      </p>
      <p className="mt-1.5 text-[13.5px] text-navy-soft">
        {approved && identity.expires_at
          ? t('staff.identity.approvedBody', { date: formatShortDate(identity.expires_at, i18n.language) })
          : identity.review_reason}
      </p>
    </div>
  )
}

// R6's approval history, reduced to the three moments the API records.
function History({ identity }: { identity: IdentityReview }) {
  const { t, i18n } = useTranslation()
  const steps = [
    { key: 'started', at: identity.created_at, done: true },
    { key: 'sent', at: identity.submitted_at, done: Boolean(identity.submitted_at) },
    { key: identity.status === 'REJECTED' ? 'rejected' : 'approved', at: identity.reviewed_at, done: Boolean(identity.reviewed_at) },
  ]
  return (
    <div>
      <h3 className="text-[14px] font-semibold text-navy">{t('staff.identity.history')}</h3>
      <ol className="mt-3">
        {steps.map((step, index) => (
          <li key={step.key} className="relative flex gap-3 pb-4 last:pb-0">
            {index < steps.length - 1 && <span aria-hidden="true" className="absolute top-5 left-[9px] h-[calc(100%-12px)] w-px bg-mist" />}
            <span className={`relative mt-0.5 grid size-[19px] shrink-0 place-items-center rounded-full ${step.done ? 'bg-success text-white' : 'border border-mist bg-white text-muted'}`}>
              {step.done ? <TickIcon className="size-3" /> : <ClockIcon className="size-3" />}
            </span>
            <span>
              <span className={`block text-[13px] ${step.done ? 'font-medium text-navy' : 'text-muted'}`}>{t(`staff.identity.steps.${step.key}`)}</span>
              <span className="block text-[12px] text-muted">{step.at ? formatShortDate(step.at, i18n.language) : t('staff.identity.steps.waiting')}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function Zoom({ src, title, onClose }: { src: string; title: string; onClose: () => void }) {
  const { t } = useTranslation()
  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [onClose])
  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 grid place-items-center bg-navy/85 p-4"
      onClick={onClose}
    >
      <img src={src} alt={title} className="max-h-[88vh] max-w-full rounded-lg object-contain" onClick={(event) => event.stopPropagation()} />
      <button type="button" onClick={onClose} aria-label={t('staff.identity.close')} className="absolute top-4 right-4 grid size-11 place-items-center rounded-full bg-white/15 text-white hover:bg-white/25">
        <CloseIcon className="size-5" />
      </button>
    </motion.div>
  )
}
