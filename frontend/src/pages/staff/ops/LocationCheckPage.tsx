import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState, type ComponentType, type ReactNode, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import {
  AlertIcon,
  ArrowRightIcon,
  ChevronRightIcon,
  ClockIcon,
  CloseIcon,
  DocumentIcon,
  ImageIcon,
  MapPinIcon,
  PlusIcon,
  TickIcon,
  UsersIcon,
} from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { formatNumber, formatRelative, formatShortDate } from '../../../lib/format'
import { initials } from '../../../lib/initials'
import { staffApi, type CheckPoint, type Checklist, type LocationCheck } from '../../../lib/staffApi'
import { CheckMap, type CheckMapHandle, type MapView } from './CheckMap'

type Answers = Partial<Record<CheckPoint, boolean>>
type PanelTab = 'document' | 'duplicates' | 'listing' | 'history'
type Viewer = { src: string; title: string }

// VER-02 check screen, after C5, C6 and C9: the trail and title with the two
// decisions on top; the four checks on the left (C9: counts, then one card
// each with a cross and a tick); the satellite view in the middle with a tool
// rail and C6's strip of details and photos; the document, duplicates,
// listing and history on the right where C5 keeps its comments.
export function LocationCheckPage() {
  const { checkId = '' } = useParams()
  // A fresh desk for each check, so answers never carry over to the next one.
  return <CheckDesk key={checkId} checkId={checkId} />
}

function CheckDesk({ checkId }: { checkId: string }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [check, setCheck] = useState<LocationCheck | null>(null)
  const [photos, setPhotos] = useState<{ position: number; url: string }[]>([])
  const [error, setError] = useState<string | null>(null)
  const [answers, setAnswers] = useState<Answers>({})
  const [view, setView] = useState<MapView>('satellite')
  const [showDuplicates, setShowDuplicates] = useState(true)
  const [showStrip, setShowStrip] = useState(true)
  const [panel, setPanel] = useState<PanelTab>('document')
  const [viewer, setViewer] = useState<Viewer | null>(null)
  const [failing, setFailing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [nextId, setNextId] = useState<string | null>(null)
  const map = useRef<CheckMapHandle>(null)
  useDocumentTitle(check ? `${t('staff.locationChecks.title')} · ${check.property_id}` : t('staff.locationChecks.title'))

  useEffect(() => {
    let live = true
    staffApi.check(checkId).then(
      (loaded) => live && setCheck(loaded),
      (caught) => live && setError(errorMessage(t, caught)),
    )
    staffApi.checkPhotos(checkId).then(
      (loaded) => live && setPhotos(loaded),
      () => live && setPhotos([]),
    )
    return () => {
      live = false
    }
  }, [checkId, t])

  const decided = check !== null && check.status !== 'PENDING'
  const points = check?.checklist ?? []
  const unanswered = points.filter((point) => answers[point] === undefined).length
  const unmet = points.filter((point) => answers[point] === false).length
  const allMet = points.length > 0 && unanswered === 0 && unmet === 0

  const answer = useCallback((point: CheckPoint, value: boolean) => {
    setAnswers((current) => ({ ...current, [point]: current[point] === value ? undefined : value }))
  }, [])

  async function findNext() {
    const page = await staffApi.checks('waiting').catch(() => null)
    setNextId(page?.results.find((row) => row.id !== checkId)?.id ?? null)
  }

  async function pass() {
    if (!check || !allMet) return
    setBusy(true)
    setError(null)
    try {
      setCheck(await staffApi.passCheck(check.id, answers as Checklist))
      setNotice(t('staff.locationChecks.desk.passedNotice'))
      void findNext()
    } catch (caught) {
      setError(errorMessage(t, caught))
    } finally {
      setBusy(false)
    }
  }

  async function fail(reason: string) {
    if (!check) return
    setBusy(true)
    setError(null)
    try {
      setCheck(await staffApi.failCheck(check.id, reason, unanswered === 0 ? (answers as Checklist) : undefined))
      setFailing(false)
      setNotice(t('staff.locationChecks.desk.failedNotice'))
      void findNext()
    } catch (caught) {
      setError(errorMessage(t, caught))
    } finally {
      setBusy(false)
    }
  }

  if (!check) return error ? <Alert tone="error">{error}</Alert> : <FullPageLoader inline />

  const [place] = check.area.split(', ')
  const nearest = check.duplicates.reduce<number | null>((best, row) => (row.distance_meters !== null && (best === null || row.distance_meters < best) ? row.distance_meters : best), null)

  return (
    <div className="space-y-4">
      {/* C5: grey trail pills, the title with the lister, then the views and the decisions. */}
      <header>
        <nav aria-label={t('nav.breadcrumb')}>
          <ol className="flex flex-wrap items-center gap-1.5 text-[13px]">
            <li>
              <Link to="/staff/checks" className="inline-flex h-7 items-center rounded-full bg-[#ececef] px-3 text-navy-soft hover:text-navy">
                {t('staff.locationChecks.title')}
              </Link>
            </li>
            <li aria-hidden="true">
              <ChevronRightIcon className="size-3.5 text-muted" />
            </li>
            <li>
              <span aria-current="page" className="inline-flex h-7 items-center rounded-full bg-[#ececef] px-3 text-navy tabular-nums">
                {check.property_id}
              </span>
            </li>
          </ol>
        </nav>
        <h1 className="mt-3 text-[22px] leading-tight font-semibold text-navy sm:text-[24px]">
          {t('staff.locationChecks.desk.heading', { category: t(`market.category.${check.category}`), place })}
          <span className="ml-2 align-middle text-[14px] font-normal text-muted">
            · {t('staff.locationChecks.desk.lister')} <span className="text-[#9a6c12]">{check.lister_name}</span>
          </span>
        </h1>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div role="radiogroup" aria-label={t('staff.locationChecks.desk.views.label')} className="flex rounded-lg border border-mist bg-white p-0.5">
            {(['satellite', 'map'] as const).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={view === value}
                onClick={() => setView(value)}
                className={`h-8 rounded-md px-4 text-[13.5px] transition-colors ${view === value ? 'bg-[#ececef] font-medium text-navy' : 'text-navy-soft hover:text-navy'}`}
              >
                {t(`staff.locationChecks.desk.views.${value}`)}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-[12.5px] text-muted">{t('staff.locationChecks.desk.submitted', { time: formatRelative(check.submitted_at, i18n.language) })}</span>
            {decided ? (
              <DecisionChip check={check} />
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setFailing(true)}
                  disabled={busy}
                  className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#8a5a0b] px-4 text-[13.5px] font-semibold text-white hover:bg-[#744b08] disabled:opacity-60"
                >
                  <AlertIcon className="size-4" />
                  {t('staff.locationChecks.desk.fail')}
                </button>
                <button
                  type="button"
                  onClick={pass}
                  disabled={busy || !allMet}
                  aria-describedby={allMet ? undefined : 'pass-blocked'}
                  className="inline-flex h-10 items-center gap-2 rounded-lg bg-navy px-4 text-[13.5px] font-semibold text-white hover:bg-navy-soft disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <TickIcon className="size-4" />
                  {t('staff.locationChecks.desk.pass')}
                </button>
              </>
            )}
          </div>
        </div>
        {!decided && !allMet && (
          <p id="pass-blocked" className="mt-2 text-right text-[12px] text-muted">
            {t('staff.locationChecks.desk.passBlocked')}
          </p>
        )}
      </header>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && (
        <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 text-[14px] ${check.status === 'REJECTED' ? 'border-gold/30 bg-[#fdf6e7] text-[#7a5410]' : 'border-success/25 bg-success-soft text-success'}`}>
          <span className="font-medium">{notice}</span>
          <span className="flex gap-2">
            <Link to="/staff/checks" className="inline-flex h-9 items-center rounded-lg border border-mist bg-white px-3 text-[13px] font-semibold text-navy">
              {t('staff.locationChecks.desk.back')}
            </Link>
            {nextId && (
              <button type="button" onClick={() => navigate(`/staff/checks/${nextId}`)} className="inline-flex h-9 items-center rounded-lg bg-navy px-3 text-[13px] font-semibold text-white">
                {t('staff.locationChecks.desk.openNext')}
              </button>
            )}
          </span>
        </div>
      )}

      <div className="grid gap-4 xl:h-[calc(100vh-15rem)] xl:min-h-[640px] xl:grid-cols-[300px_minmax(0,1fr)_280px]">
        <Checks points={points} answers={answers} onAnswer={answer} decided={decided} unanswered={unanswered} unmet={unmet} allMet={allMet} />

        {/* C5's canvas, holding C6's satellite view and strip. */}
        <section className="relative isolate min-h-[520px] overflow-hidden rounded-2xl border border-mist bg-white xl:min-h-0">
          {check.pin ? (
            <CheckMap
              ref={map}
              pin={check.pin}
              boundary={check.boundary}
              duplicates={check.duplicates}
              showDuplicates={showDuplicates}
              view={view}
              pinLabel={`${check.property_id} · ${t(`market.category.${check.category}`)}`}
              label={t('staff.locationChecks.desk.pinLabel')}
            />
          ) : (
            <p className="grid h-full place-items-center text-sm text-muted">{t('staff.locationChecks.desk.noPin')}</p>
          )}
          <ToolRail
            tools={[
              { key: 'zoomIn', icon: PlusIcon, onClick: () => map.current?.zoomIn() },
              { key: 'zoomOut', icon: MinusIcon, onClick: () => map.current?.zoomOut() },
              { key: 'recenter', icon: MapPinIcon, onClick: () => map.current?.recenter() },
              { key: 'duplicates', icon: UsersIcon, onClick: () => setShowDuplicates((value) => !value), pressed: showDuplicates },
              { key: 'photos', icon: ImageIcon, onClick: () => setShowStrip((value) => !value), pressed: showStrip },
            ]}
          />
          <AnimatePresence>
            {showStrip && (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 16 }}
                transition={{ duration: 0.22 }}
                className="absolute inset-x-3 bottom-3 z-[500] rounded-2xl bg-white/97 p-3 shadow-[0_10px_30px_rgba(15,23,42,0.25)] sm:inset-x-4 sm:bottom-4 sm:p-4"
              >
                <Strip check={check} photos={photos} nearest={nearest} onPhoto={(src, index) => setViewer({ src, title: `${check.property_id} · ${index + 1}` })} />
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        <Panel check={check} tab={panel} onTab={setPanel} onView={setViewer} />
      </div>

      <AnimatePresence>{viewer && <ImageViewer viewer={viewer} onClose={() => setViewer(null)} />}</AnimatePresence>
      <AnimatePresence>{failing && <FailDialog busy={busy} onCancel={() => setFailing(false)} onConfirm={fail} />}</AnimatePresence>
    </div>
  )
}

function MinusIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true" {...props}>
      <path d="M5 12h14" />
    </svg>
  )
}

function DecisionChip({ check }: { check: LocationCheck }) {
  const { t, i18n } = useTranslation()
  const passed = check.status === 'APPROVED'
  return (
    <span className={`inline-flex h-10 items-center gap-2 rounded-lg px-4 text-[13.5px] font-semibold ${passed ? 'bg-success-soft text-success' : 'bg-gold/15 text-[#7a5410]'}`}>
      {passed ? <TickIcon className="size-4" /> : <AlertIcon className="size-4" />}
      {t(passed ? 'staff.locationChecks.desk.decidedPassed' : 'staff.locationChecks.desk.decidedFailed', {
        date: check.reviewed_at ? formatShortDate(check.reviewed_at, i18n.language) : '',
        name: check.reviewer_name ?? '',
      })}
    </span>
  )
}

// C9: "List of checks" with its count, the two count boxes, then a card per point.
function Checks({ points, answers, onAnswer, decided, unanswered, unmet, allMet }: {
  points: CheckPoint[]
  answers: Answers
  onAnswer: (point: CheckPoint, value: boolean) => void
  decided: boolean
  unanswered: number
  unmet: number
  allMet: boolean
}) {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="checks-title" className="flex flex-col rounded-2xl border border-mist bg-white p-4 xl:overflow-y-auto">
      <h2 id="checks-title" className="flex items-center gap-2 text-[15px] font-medium text-navy">
        {t('staff.locationChecks.desk.listTitle')}
        <span className="grid h-5 min-w-5 place-items-center rounded-md bg-paper px-1.5 text-[11.5px] text-navy-soft">{points.length}</span>
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-2.5">
        <p className="grid place-items-center gap-1.5 rounded-xl bg-[#eef2f8] px-2 py-4 text-center text-[13px] font-medium text-navy">
          <span className="grid size-7 place-items-center rounded-full bg-white/80">
            <ClockIcon className="size-4 text-navy" />
          </span>
          {t('staff.locationChecks.desk.unanswered', { count: decided ? 0 : unanswered })}
        </p>
        <p className="grid place-items-center gap-1.5 rounded-xl bg-[#fdf1dc] px-2 py-4 text-center text-[13px] font-medium text-[#7a5410]">
          <span className="grid size-7 place-items-center rounded-full bg-white/70">
            <AlertIcon className="size-4 text-[#8a5a0b]" />
          </span>
          {t('staff.locationChecks.desk.unmet', { count: unmet })}
        </p>
      </div>
      <ul className="mt-3 space-y-2.5">
        {points.map((point) => {
          const value = answers[point]
          return (
            <li key={point} className={`rounded-xl border px-3.5 py-3 transition-colors ${value === false ? 'border-gold/40 bg-[#fffaf0]' : value ? 'border-success/30 bg-success-soft/40' : 'border-mist bg-white'}`}>
              <div className="flex items-start gap-3">
                <span
                  className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ${
                    value === false ? 'bg-[#fdf1dc] text-[#8a5a0b]' : value ? 'bg-success-soft text-success' : 'bg-[#eef2f8] text-navy'
                  }`}
                >
                  {value === false ? <AlertIcon className="size-3.5" /> : value ? <TickIcon className="size-3.5" /> : <ClockIcon className="size-3.5" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold text-navy">{t(`staff.locationChecks.desk.points.${point}.title`)}</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-navy-soft">{t(`staff.locationChecks.desk.points.${point}.body`)}</p>
                </div>
              </div>
              {!decided && (
                <div role="group" aria-label={t(`staff.locationChecks.desk.points.${point}.title`)} className="mt-2.5 flex justify-end">
                  <span className="inline-flex overflow-hidden rounded-lg border border-mist bg-white">
                    <button
                      type="button"
                      aria-pressed={value === false}
                      aria-label={t('staff.locationChecks.desk.notMet')}
                      onClick={() => onAnswer(point, false)}
                      className={`grid h-8 w-10 place-items-center transition-colors ${value === false ? 'bg-[#8a5a0b] text-white' : 'text-navy-soft hover:bg-paper'}`}
                    >
                      <CloseIcon className="size-4" />
                    </button>
                    <button
                      type="button"
                      aria-pressed={value === true}
                      aria-label={t('staff.locationChecks.desk.met')}
                      onClick={() => onAnswer(point, true)}
                      className={`grid h-8 w-10 place-items-center border-l border-mist transition-colors ${value ? 'bg-navy text-white' : 'text-navy-soft hover:bg-paper'}`}
                    >
                      <TickIcon className="size-4" />
                    </button>
                  </span>
                </div>
              )}
            </li>
          )
        })}
      </ul>
      {!decided && (
        <p className="mt-auto flex items-center gap-2 border-t border-mist pt-3 text-[12.5px] text-navy-soft max-xl:mt-3">
          {allMet ? <TickIcon className="size-4 text-success" /> : unmet ? <AlertIcon className="size-4 text-[#8a5a0b]" /> : <ClockIcon className="size-4 text-muted" />}
          {t(allMet ? 'staff.locationChecks.desk.summaryReady' : unmet ? 'staff.locationChecks.desk.summaryFail' : 'staff.locationChecks.desk.summaryPending')}
        </p>
      )}
    </section>
  )
}

// C5's floating tool column on the left of the canvas.
function ToolRail({ tools }: { tools: { key: string; icon: ComponentType<SVGProps<SVGSVGElement>>; onClick: () => void; pressed?: boolean }[] }) {
  const { t } = useTranslation()
  return (
    <div className="absolute top-3 left-3 z-[500] flex flex-col gap-1 rounded-xl bg-white p-1.5 shadow-[0_4px_16px_rgba(15,23,42,0.18)] sm:top-4 sm:left-4">
      {tools.map(({ key, icon: Icon, onClick, pressed }, index) => (
        <span key={key} className="contents">
          {index === 3 && <span aria-hidden="true" className="mx-1.5 my-0.5 h-px bg-mist" />}
          <button
            type="button"
            onClick={onClick}
            aria-pressed={pressed}
            aria-label={t(`staff.locationChecks.desk.tools.${key}`)}
            title={t(`staff.locationChecks.desk.tools.${key}`)}
            className={`grid size-9 place-items-center rounded-lg transition-colors ${pressed ? 'bg-navy text-white' : 'text-navy hover:bg-paper'}`}
          >
            <Icon className="size-[18px]" />
          </button>
        </span>
      ))}
    </div>
  )
}

// Hairlines between the facts: two columns on a narrow canvas, four when wide.
const FACT_EDGE = ['', 'border-l border-mist pl-3', '@lg:border-l @lg:border-mist @lg:pl-3', 'border-l border-mist pl-3']

// C6: the name, a row of facts split by hairlines, one button, and the photos.
function Strip({ check, photos, nearest, onPhoto }: { check: LocationCheck; photos: { url: string }[]; nearest: number | null; onPhoto: (src: string, index: number) => void }) {
  const { t, i18n } = useTranslation()
  const facts = [
    { key: 'size', value: `${formatNumber(check.stated_size, i18n.language)} ${check.size_unit}` },
    { key: 'title', value: t(`market.titleType.${check.title_type}`) },
    { key: 'category', value: t(`market.category.${check.category}`) },
    { key: 'nearest', value: nearest === null ? t('staff.locationChecks.desk.strip.none') : `${Math.round(nearest)} m` },
  ]
  return (
    <div className="@container">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[18px] leading-tight font-semibold text-navy">{check.area.split(', ').slice(0, 2).join(', ')}</p>
          <p className="text-[12.5px] text-muted tabular-nums">{check.property_id}</p>
        </div>
        {check.listing?.status === 'ACTIVE' && (
          <Link
            to={`/listings/${check.listing.listing_id}`}
            target="_blank"
            className="inline-flex h-9 shrink-0 items-center gap-2 rounded-lg bg-navy px-3.5 text-[13px] font-semibold text-white hover:bg-navy-soft"
          >
            {t('staff.locationChecks.desk.strip.viewListing')}
            <ArrowRightIcon className="size-4" />
          </Link>
        )}
      </div>
      <dl className="mt-2.5 grid grid-cols-2 gap-y-2 border-t border-mist pt-2.5 @lg:grid-cols-4">
        {facts.map((fact, index) => (
          <div key={fact.key} className={`min-w-0 pr-3 ${FACT_EDGE[index]}`}>
            <dd title={fact.value} className="truncate text-[14px] font-semibold text-navy">{fact.value}</dd>
            <dt className="text-[11.5px] text-muted">{t(`staff.locationChecks.desk.strip.${fact.key}`)}</dt>
          </div>
        ))}
      </dl>
      {photos.length > 0 ? (
        <ul className="mt-2.5 grid grid-cols-4 gap-2">
          {photos.slice(0, 4).map((photo, index) => (
            <li key={photo.url}>
              <button type="button" onClick={() => onPhoto(photo.url, index)} className="block aspect-[16/10] w-full overflow-hidden rounded-lg bg-paper">
                <img src={photo.url} alt={`${check.property_id} · ${index + 1}`} className="size-full object-cover transition-transform duration-300 hover:scale-[1.03]" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-[13px] text-muted">{t('staff.locationChecks.desk.strip.noPhotos')}</p>
      )}
    </div>
  )
}

// C5's comments column: a title with a count, a segmented switch, then cards.
function Panel({ check, tab, onTab, onView }: { check: LocationCheck; tab: PanelTab; onTab: (tab: PanelTab) => void; onView: (viewer: Viewer) => void }) {
  const { t } = useTranslation()
  const counts: Record<PanelTab, number | null> = { document: check.documents.length, duplicates: check.duplicates.length, listing: null, history: null }
  return (
    <section aria-label={t('staff.locationChecks.desk.panel.label')} className="flex flex-col rounded-2xl border border-mist bg-white xl:overflow-hidden">
      <div className="border-b border-mist px-4 pt-4 pb-3">
        <h2 className="flex items-center gap-2 text-[16px] font-semibold text-navy">
          {t('staff.locationChecks.desk.panel.label')}
          <span className="grid h-5 min-w-5 place-items-center rounded-md bg-paper px-1.5 text-[11.5px] font-normal text-navy-soft">{check.documents.length + check.duplicates.length}</span>
        </h2>
        <div role="tablist" className="mt-3 grid grid-cols-4 rounded-lg border border-mist p-0.5">
          {(['document', 'duplicates', 'listing', 'history'] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => onTab(value)}
              className={`h-8 truncate rounded-md px-1 text-[12px] transition-colors ${tab === value ? 'bg-[#ececef] font-medium text-navy' : 'text-navy-soft hover:text-navy'}`}
            >
              {t(`staff.locationChecks.desk.panel.${value}`)}
              {counts[value] ? ` ${counts[value]}` : ''}
            </button>
          ))}
        </div>
      </div>
      <div role="tabpanel" className="flex-1 space-y-3 p-4 xl:overflow-y-auto">
        {tab === 'document' && <DocumentCards check={check} onView={onView} />}
        {tab === 'duplicates' && <DuplicateCards check={check} />}
        {tab === 'listing' && <ListingCard check={check} />}
        {tab === 'history' && <History check={check} />}
      </div>
    </section>
  )
}

function PanelCard({ name, role, children }: { name: string; role: string; children: ReactNode }) {
  return (
    <article className="rounded-xl border border-mist p-3.5">
      <header className="flex items-center gap-2.5">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-gold/15 text-[11.5px] font-semibold text-[#7a5410]">{initials(name)}</span>
        <span className="min-w-0">
          <span className="block truncate text-[14px] font-semibold text-navy">{name}</span>
          <span className="block text-[12px] text-muted">{role}</span>
        </span>
      </header>
      <div className="mt-2.5 text-[13.5px] leading-relaxed text-navy">{children}</div>
    </article>
  )
}

function DocumentCards({ check, onView }: { check: LocationCheck; onView: (viewer: Viewer) => void }) {
  const { t, i18n } = useTranslation()
  const [opening, setOpening] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function open(documentId: string) {
    setOpening(documentId)
    setError(null)
    try {
      const { url } = await staffApi.checkDocument(check.id, documentId)
      onView({ src: url, title: t('staff.locationChecks.desk.document.title') })
    } catch (caught) {
      setError(errorMessage(t, caught))
    } finally {
      setOpening(null)
    }
  }

  if (check.documents.length === 0) return <p className="text-[13px] text-muted">{t('staff.locationChecks.desk.document.none')}</p>
  return (
    <>
      {check.documents.map((document) => (
        <PanelCard key={document.id} name={check.lister_name} role={t(`staff.locationChecks.desk.listing.${check.listing?.lister_kind === 'AGENT' ? 'agent' : 'owner'}`)}>
          <p className="flex items-center gap-2 font-medium">
            <DocumentIcon className="size-4 text-gold" />
            {t('staff.locationChecks.desk.document.title')}
          </p>
          <p className="mt-0.5 text-[12.5px] text-muted">{t('staff.locationChecks.desk.document.uploaded', { time: formatRelative(document.created_at, i18n.language) })}</p>
          <button
            type="button"
            onClick={() => open(document.id)}
            disabled={opening !== null}
            className="mt-3 inline-flex h-8 items-center rounded-full border border-mist px-3.5 text-[12.5px] font-medium text-navy hover:border-navy/30 disabled:opacity-60"
          >
            {opening === document.id ? t('staff.locationChecks.desk.document.opening') : t('staff.locationChecks.desk.document.open')}
          </button>
        </PanelCard>
      ))}
      {error && <p className="text-[12.5px] text-danger">{error}</p>}
      <p className="text-[12px] text-muted">{t('staff.locationChecks.desk.document.recorded')}</p>
    </>
  )
}

const DUPLICATE_CHIP: Record<string, string> = {
  PENDING: 'bg-[#eef2f8] text-navy',
  CONFIRMED_DUPLICATE: 'bg-danger-soft text-danger',
  NOT_DUPLICATE: 'bg-success-soft text-success',
}

function DuplicateCards({ check }: { check: LocationCheck }) {
  const { t, i18n } = useTranslation()
  if (check.duplicates.length === 0) return <p className="text-[13px] text-muted">{t('staff.locationChecks.desk.duplicates.none')}</p>
  return (
    <>
      {check.duplicates.map((row) => (
        <article key={row.id} className="overflow-hidden rounded-xl border border-mist">
          <div className="aspect-[16/8] bg-paper">
            {row.cover_url ? <img src={row.cover_url} alt="" className="size-full object-cover" /> : <span className="grid size-full place-items-center"><ImageIcon className="size-5 text-muted" /></span>}
          </div>
          <div className="p-3.5">
            <p className="flex items-center justify-between gap-2">
              <span className="text-[14px] font-semibold whitespace-nowrap text-navy tabular-nums">{row.property_id}</span>
              <span className={`truncate rounded-md px-2 py-0.5 text-[11.5px] font-medium ${DUPLICATE_CHIP[row.status]}`}>{t(`staff.locationChecks.desk.duplicates.statuses.${row.status}`)}</span>
            </p>
            <p className="mt-0.5 truncate text-[12.5px] text-muted">{row.area}</p>
            <p className="mt-2 text-[13px] text-navy">
              {row.distance_meters !== null && t('staff.locationChecks.desk.duplicates.distance', { metres: Math.round(row.distance_meters) })}
              {row.size_difference_percent !== null && (
                <span className="block text-navy-soft">{t('staff.locationChecks.desk.duplicates.sizeGap', { percent: formatNumber(row.size_difference_percent, i18n.language) })}</span>
              )}
            </p>
            <p className="mt-2 flex flex-wrap gap-1.5">
              {row.signals.map((signal) => (
                <span key={signal} className="rounded-full bg-[#f1f1f3] px-2 py-0.5 text-[11.5px] text-navy">{t(`staff.locationChecks.desk.duplicates.signals.${signal}`, { defaultValue: signal })}</span>
              ))}
            </p>
          </div>
        </article>
      ))}
    </>
  )
}

function ListingCard({ check }: { check: LocationCheck }) {
  const { t } = useTranslation()
  const listing = check.listing
  return (
    <PanelCard name={check.lister_name} role={t(`staff.locationChecks.desk.listing.${listing?.lister_kind === 'AGENT' ? 'agent' : 'owner'}`)}>
      <p className="text-[12px] font-medium tracking-wide text-muted uppercase">{t('staff.locationChecks.desk.listing.description')}</p>
      <p className="mt-1 whitespace-pre-line">{listing?.description || t('staff.locationChecks.desk.listing.noDescription')}</p>
      {listing && listing.features.length > 0 && (
        <>
          <p className="mt-3 text-[12px] font-medium tracking-wide text-muted uppercase">{t('staff.locationChecks.desk.listing.features')}</p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {listing.features.map((feature) => (
              <li key={feature} className="rounded-full bg-[#f1f1f3] px-2.5 py-0.5 text-[12px] text-navy">{feature}</li>
            ))}
          </ul>
        </>
      )}
    </PanelCard>
  )
}

function History({ check }: { check: LocationCheck }) {
  const { t, i18n } = useTranslation()
  const entries = [
    { key: 'submitted', when: check.submitted_at, text: t('staff.locationChecks.desk.history.submitted', { name: check.lister_name }) },
    ...(check.reviewed_at && check.status !== 'PENDING'
      ? [{
          key: 'decided',
          when: check.reviewed_at,
          text: t(check.status === 'APPROVED' ? 'staff.locationChecks.desk.history.approved' : 'staff.locationChecks.desk.history.rejected', { name: check.reviewer_name ?? '' }),
          note: check.reason ?? undefined,
        }]
      : []),
    ...(check.expires_at ? [{ key: 'expires', when: check.expires_at, text: t('staff.locationChecks.desk.history.expires', { date: formatShortDate(check.expires_at, i18n.language) }) }] : []),
  ]
  return (
    <ol className="relative space-y-4 pl-5 before:absolute before:top-1.5 before:bottom-1.5 before:left-[5px] before:w-px before:bg-mist">
      {entries.map((entry) => (
        <li key={entry.key} className="relative">
          <span className="absolute top-1.5 -left-5 size-[11px] rounded-full border-2 border-white bg-gold ring-1 ring-gold/40" />
          <p className="text-[13.5px] font-medium text-navy">{entry.text}</p>
          <p className="text-[12px] text-muted">{formatShortDate(entry.when, i18n.language)}</p>
          {'note' in entry && entry.note && <p className="mt-1.5 rounded-lg bg-paper px-3 py-2 text-[13px] text-navy">{entry.note}</p>}
        </li>
      ))}
    </ol>
  )
}

function ImageViewer({ viewer, onClose }: { viewer: Viewer; onClose: () => void }) {
  const { t } = useTranslation()
  const [zoom, setZoom] = useState(1)
  const close = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    close.current?.focus()
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label={viewer.title}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[1000] flex flex-col bg-navy/90 backdrop-blur-sm"
    >
      <div className="flex items-center justify-between gap-3 px-4 py-3 text-white">
        <p className="truncate text-[14px] font-medium">{viewer.title}</p>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => setZoom((value) => Math.max(1, value - 0.5))} aria-label={t('staff.locationChecks.desk.document.zoomOut')} className="grid size-10 place-items-center rounded-lg hover:bg-white/10">
            <MinusIcon className="size-5" />
          </button>
          <span className="w-12 text-center text-[13px] tabular-nums">{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => setZoom((value) => Math.min(4, value + 0.5))} aria-label={t('staff.locationChecks.desk.document.zoomIn')} className="grid size-10 place-items-center rounded-lg hover:bg-white/10">
            <PlusIcon className="size-5" />
          </button>
          <button ref={close} type="button" onClick={onClose} aria-label={t('staff.locationChecks.desk.document.close')} className="ml-2 grid size-10 place-items-center rounded-lg hover:bg-white/10">
            <CloseIcon className="size-5" />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {/* At 100% the whole page fits the screen; zooming in widens it. */}
        <img
          src={viewer.src}
          alt={viewer.title}
          style={zoom > 1 ? { width: `${zoom * 50}%` } : undefined}
          className={`mx-auto rounded-lg bg-white object-contain ${zoom > 1 ? 'max-w-none' : 'max-h-[calc(100vh-6.5rem)] max-w-full'}`}
        />
      </div>
    </motion.div>
  )
}

function FailDialog({ busy, onCancel, onConfirm }: { busy: boolean; onCancel: () => void; onConfirm: (reason: string) => void }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[1000] grid place-items-center bg-navy/50 p-4">
      <motion.form
        role="dialog"
        aria-modal="true"
        aria-labelledby="fail-title"
        initial={{ y: 12, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 12, opacity: 0 }}
        onSubmit={(event) => {
          event.preventDefault()
          if (reason.trim()) onConfirm(reason.trim())
        }}
        className="w-full max-w-md rounded-2xl bg-white p-5 shadow-[0_20px_50px_rgba(15,23,42,0.3)]"
      >
        <h2 id="fail-title" className="text-[17px] font-semibold text-navy">{t('staff.locationChecks.desk.failDialog.title')}</h2>
        <p className="mt-1 text-[13.5px] text-navy-soft">{t('staff.locationChecks.desk.failDialog.hint')}</p>
        <label className="mt-4 block">
          <span className="text-[13px] font-medium text-navy">{t('staff.locationChecks.desk.failDialog.label')}</span>
          <textarea
            autoFocus
            required
            maxLength={1000}
            rows={4}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className="mt-1.5 w-full rounded-lg border border-mist px-3 py-2.5 text-[14px] text-navy outline-none focus:border-gold focus:ring-2 focus:ring-gold/20"
          />
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="inline-flex h-10 items-center rounded-lg border border-mist px-4 text-[13.5px] font-medium text-navy">
            {t('staff.locationChecks.desk.failDialog.cancel')}
          </button>
          <button
            type="submit"
            disabled={busy || !reason.trim()}
            className="inline-flex h-10 items-center rounded-lg bg-[#8a5a0b] px-4 text-[13.5px] font-semibold text-white disabled:opacity-50"
          >
            {t('staff.locationChecks.desk.failDialog.confirm')}
          </button>
        </div>
      </motion.form>
    </motion.div>
  )
}
