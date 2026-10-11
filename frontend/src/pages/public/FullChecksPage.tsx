import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { ChevronRightIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatDate, formatTsh } from '../../lib/format'
import { servicesApi, type FullCheck, type FullCheckStatus } from '../../lib/servicesApi'

// Status chip colours, after S13: green when done well, amber while it runs,
// red for a problem, grey and faded when it could not be finished.
const CHIP: Record<FullCheckStatus, string> = {
  AWAITING_PAYMENT: 'bg-gold/20 text-[#7a5410]',
  AWAITING_CONSENT: 'bg-gold/20 text-[#7a5410]',
  IN_PROGRESS: 'bg-gold/20 text-[#7a5410]',
  UNDER_REVIEW: 'bg-gold/20 text-[#7a5410]',
  PASSED: 'bg-success-soft text-success',
  PROBLEM_FOUND: 'bg-danger-soft text-danger',
  NOT_COMPLETED: 'bg-danger-soft text-danger',
}

type Loaded = { checks?: FullCheck[]; error?: string }

export function FullChecksPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('fullCheck.listTitle'))
  const [loaded, setLoaded] = useState<Loaded | null>(null)

  useEffect(() => {
    let cancelled = false
    servicesApi
      .fullChecks()
      .then((page) => !cancelled && setLoaded({ checks: page.results }))
      .catch((error: unknown) => !cancelled && setLoaded({ error: errorMessage(t, error) }))
    return () => {
      cancelled = true
    }
  }, [t])

  return (
    <div className="mx-auto max-w-[640px] px-4 pt-6 pb-16 sm:pt-10">
      <h1 className="text-[28px] leading-tight font-bold text-navy">{t('fullCheck.listTitle')}</h1>
      <div className="mt-6">
        {!loaded ? (
          <FullPageLoader inline />
        ) : loaded.error ? (
          <Alert tone="error">{loaded.error}</Alert>
        ) : loaded.checks && loaded.checks.length > 0 ? (
          <ul className="space-y-5">
            {loaded.checks.map((check, index) => (
              <motion.li key={check.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06, duration: 0.35 }}>
                <CheckCard check={check} />
              </motion.li>
            ))}
          </ul>
        ) : (
          <div className="rounded-[22px] bg-white p-6 text-center shadow-card">
            <p className="text-[15px] leading-relaxed text-muted">{t('fullCheck.listEmpty')}</p>
            <Link to="/listings" className="mt-5 inline-flex h-11 items-center rounded-full bg-navy px-5 text-sm font-semibold text-white hover:bg-navy-soft">
              {t('site.browse')}
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}

// One S13 card: a small label over the reference, the status chip top right,
// two facts on a dotted line, and the link at the bottom right.
function CheckCard({ check }: { check: FullCheck }) {
  const { t, i18n } = useTranslation()
  const faded = check.status === 'NOT_COMPLETED'
  const finished = Boolean(check.completed_at)

  return (
    <article className={`rounded-[22px] px-6 pt-5 pb-5 shadow-card ${faded ? 'bg-white/70' : 'bg-white'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="shrink-0">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">{t('listing.propertyId')}</p>
          <p className={`mt-1 font-mono text-lg font-semibold whitespace-nowrap ${faded ? 'text-navy/60' : 'text-navy'}`}>{check.property_id}</p>
        </div>
        {/* Long Swahili statuses wrap rather than cut the property number. */}
        <span className={`min-w-0 rounded-2xl px-3 py-1 text-center text-xs leading-snug font-semibold tracking-[0.04em] uppercase ${CHIP[check.status]}`}>
          {t(`fullCheck.statuses.${check.status}`)}
        </span>
      </div>

      <div className="mt-4 flex items-end justify-between gap-4">
        <dl className="relative space-y-3 pl-6">
          <span aria-hidden="true" className="absolute top-[7px] bottom-[26px] left-[4px] border-l border-dashed border-mist" />
          <div className="relative">
            <span aria-hidden="true" className={`absolute top-1.5 -left-6 size-2.5 rounded-full ${faded ? 'bg-mist' : 'bg-navy ring-4 ring-navy/10'}`} />
            <dt className="text-[13px] text-muted">{t('fullCheck.fee')}</dt>
            <dd className={`text-[15px] font-medium ${faded ? 'text-navy/60' : 'text-navy'}`}>{formatTsh(check.fee, i18n.language)}</dd>
          </div>
          <div className="relative">
            <span aria-hidden="true" className="absolute top-1.5 -left-[22px] size-1.5 rounded-full bg-mist" />
            <dt className="text-[13px] text-muted">{finished ? t('fullCheck.completedOn') : t('fullCheck.orderedOn')}</dt>
            <dd className={`text-[15px] font-medium ${faded ? 'text-navy/60' : 'text-navy'}`}>{formatDate(check.completed_at ?? check.created_at, i18n.language)}</dd>
          </div>
        </dl>
        <Link to={`/full-checks/${check.id}`} className="group inline-flex shrink-0 items-center gap-1 text-[15px] font-semibold text-gold hover:text-[#a87816]">
          {t('fullCheck.details')}
          <ChevronRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </article>
  )
}
