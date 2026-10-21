import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { ChevronRightIcon, HomeIcon } from '../../components/icons'
import { PageHeader } from '../../components/PageHeader'
import { dealsApi, type Deal } from '../../lib/dealsApi'
import { errorMessage } from '../../lib/errors'
import { formatShortDate, formatTsh } from '../../lib/format'
import { PaymentChip } from './ui'

// The buyer's purchases (/purchases) and the lister's deals (/lister/deals):
// one card per deal with the property, the final price and where payment is.

export function DealsListPage({ mode }: { mode: 'buyer' | 'lister' }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const [deals, setDeals] = useState<Deal[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let live = true
    dealsApi
      .list()
      .then((rows) => live && setDeals(rows))
      .catch((failure) => {
        if (!live) return
        setError(errorMessage(t, failure))
        setDeals([])
      })
    return () => {
      live = false
    }
  }, [t])

  const base = mode === 'buyer' ? '/purchases' : '/lister/deals'
  return (
    <div>
      <PageHeader title={t(`deals.list.${mode}.title`)} description={t(`deals.list.${mode}.description`)} />
      {error && <Alert tone="error">{error}</Alert>}
      {!deals ? (
        <FullPageLoader inline />
      ) : deals.length === 0 ? (
        <div className="rounded-xl border border-dashed border-mist bg-white px-6 py-14 text-center">
          <HomeIcon className="mx-auto size-8 text-muted" />
          <p className="mt-3 text-[15px] font-medium text-navy">{t(`deals.list.${mode}.empty`)}</p>
          <p className="mx-auto mt-1 max-w-md text-[13px] text-muted">{t(`deals.list.${mode}.emptyNote`)}</p>
        </div>
      ) : (
        <ul className="grid gap-3">
          {deals.map((deal, index) => (
            <motion.li key={deal.id} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: index * 0.05 }}>
              <Link to={`${base}/${deal.id}`} className="group flex items-center gap-4 rounded-xl border border-mist bg-white p-3 pr-5 transition-shadow hover:shadow-card">
                <span className="size-16 shrink-0 overflow-hidden rounded-lg bg-paper">
                  {deal.property.cover_url ? <img src={deal.property.cover_url} alt="" className="size-full object-cover" /> : <HomeIcon className="m-5 size-6 text-muted" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15px] font-medium text-navy">
                    {t(`deals.categories.${deal.property.category}`)} · {deal.property.area}
                  </span>
                  <span className="mt-0.5 block text-[12px] text-muted">
                    {deal.property.property_id} · {mode === 'buyer' ? deal.lister_name : deal.buyer_name} · {formatShortDate(deal.created_at, i18n.language)}
                  </span>
                </span>
                <span className="hidden text-right sm:block">
                  <span className="block text-[15px] font-semibold text-navy tabular-nums">{formatTsh(deal.final_selling_price, i18n.language)}</span>
                  <span className="mt-1 block">
                    {deal.state === 'CANCELLED' ? (
                      <span className="inline-flex rounded-full bg-mist/70 px-3 py-1 text-[12px] font-medium text-muted">{t('deals.cancelled')}</span>
                    ) : (
                      <PaymentChip status={deal.payment_status} />
                    )}
                  </span>
                </span>
                <ChevronRightIcon className="size-4 text-muted transition-transform group-hover:translate-x-0.5" />
              </Link>
            </motion.li>
          ))}
        </ul>
      )}
    </div>
  )
}
