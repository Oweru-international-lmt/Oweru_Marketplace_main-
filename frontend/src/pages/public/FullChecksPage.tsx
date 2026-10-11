import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { ChevronRightIcon, ShieldIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatDate, formatTsh } from '../../lib/format'
import { servicesApi, type FullCheck, type FullCheckStatus } from '../../lib/servicesApi'
import { ServiceHeader, ServicePage } from './services/ServiceUi'

const CHIP: Record<FullCheckStatus, string> = {
  AWAITING_PAYMENT: 'bg-gold/15 text-[#8a5f12]',
  AWAITING_CONSENT: 'bg-paper text-navy ring-1 ring-mist',
  IN_PROGRESS: 'bg-paper text-navy ring-1 ring-mist',
  UNDER_REVIEW: 'bg-paper text-navy ring-1 ring-mist',
  PASSED: 'bg-success-soft text-success',
  PROBLEM_FOUND: 'bg-danger-soft text-danger',
  NOT_COMPLETED: 'bg-danger-soft text-danger',
}

type Loaded = { checks?: FullCheck[]; error?: string }

export function FullChecksPage() {
  const { t, i18n } = useTranslation()
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
    <ServicePage>
      <ServiceHeader kicker={t('fullCheck.kicker')} lead={t('fullCheck.listTitle')} />
      <div className="mt-6 px-4 sm:mt-10 sm:max-w-3xl sm:px-0">
        {!loaded ? (
          <FullPageLoader inline />
        ) : loaded.error ? (
          <Alert tone="error">{loaded.error}</Alert>
        ) : loaded.checks && loaded.checks.length > 0 ? (
          <ul className="space-y-3">
            {loaded.checks.map((check, index) => (
              <motion.li key={check.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05, duration: 0.35 }}>
                <Link
                  to={`/full-checks/${check.id}`}
                  className="group flex items-center gap-4 rounded-2xl bg-white p-4 shadow-card transition-shadow hover:shadow-lift sm:rounded-md sm:p-5"
                >
                  <span className="grid size-11 shrink-0 place-items-center rounded-full bg-navy text-gold-light">
                    <ShieldIcon className="size-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-navy">{check.property_id}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {t('fullCheck.ordered', { date: formatDate(check.created_at, i18n.language) })} · {formatTsh(check.fee, i18n.language)}
                    </p>
                    <span className={`mt-2 inline-flex rounded-full px-3 py-1 text-xs font-semibold sm:hidden ${CHIP[check.status]}`}>
                      {t(`fullCheck.statuses.${check.status}`)}
                    </span>
                  </div>
                  <span className={`hidden rounded-full px-3 py-1 text-xs font-semibold whitespace-nowrap sm:inline-flex ${CHIP[check.status]}`}>
                    {t(`fullCheck.statuses.${check.status}`)}
                  </span>
                  <ChevronRightIcon className="size-5 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
                </Link>
              </motion.li>
            ))}
          </ul>
        ) : (
          <div className="rounded-2xl bg-white p-6 text-center shadow-card sm:rounded-md">
            <p className="text-[15px] leading-relaxed text-muted">{t('fullCheck.listEmpty')}</p>
            <Link to="/listings" className="mt-5 inline-flex h-11 items-center rounded-md bg-navy px-5 text-sm font-semibold text-white hover:bg-navy-soft">
              {t('site.browse')}
            </Link>
          </div>
        )}
      </div>
    </ServicePage>
  )
}
