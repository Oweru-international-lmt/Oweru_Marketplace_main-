import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { CalendarIcon, ChatIcon, ChevronRightIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatShortDate } from '../../lib/format'
import { peopleApi, type MyEnquiry } from '../../lib/peopleApi'

// SRD 24: the properties a buyer has asked about. The lister's own pipeline
// stage stays private; a purchase opens once a deal exists.

export function MyEnquiriesPage() {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  useDocumentTitle(t('myEnquiries.title'))
  const [rows, setRows] = useState<MyEnquiry[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    peopleApi.myEnquiries().then(setRows, (failure) => {
      setError(errorMessage(t, failure))
      setRows([])
    })
  }, [t])

  if (!rows) return <FullPageLoader inline />
  return (
    <div className="mx-auto max-w-[760px] pb-10">
      <h1 className="text-[24px] font-semibold text-navy">{t('myEnquiries.title')}</h1>
      <p className="mt-1 text-[13px] text-muted">{t('myEnquiries.subtitle')}</p>
      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
      {rows.length === 0 ? (
        <div className="mt-6 rounded-2xl border border-mist bg-white px-6 py-12 text-center">
          <p className="text-[14px] text-navy-soft">{t('myEnquiries.empty')}</p>
          <Link to="/listings" className="mt-4 inline-flex rounded-full bg-gold px-5 py-2 text-[13px] font-semibold text-navy">{t('myEnquiries.browse')}</Link>
        </div>
      ) : (
        <ul className="mt-5 space-y-2.5">
          {rows.map((row, index) => (
            <motion.li key={row.id} initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index, 8) * 0.05 }}>
              <Link to={row.deal_id ? `/purchases/${row.deal_id}` : `/listings/${row.listing_id}`} className="flex items-center gap-3 rounded-xl border border-mist bg-white px-4 py-3.5 hover:border-gold/60">
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-gold/15 text-[#9a6c12]">
                  {row.source === 'VIEWING_REQUEST' ? <CalendarIcon className="size-5" /> : row.source === 'WHATSAPP_CONTACT' ? <WhatsAppIcon className="size-5" /> : <ChatIcon className="size-5" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-medium text-navy">{`${t(`market.category.${row.category}`)} · ${row.area}`}</span>
                  <span className="block text-[12px] text-muted">{`${t(`lister.sources.${row.source}`)} · ${formatShortDate(row.created_at, i18n.language)}`}</span>
                </span>
                {row.deal_id && <span className="rounded-full bg-navy px-2.5 py-0.5 text-[11px] font-medium text-gold">{t('myEnquiries.purchase')}</span>}
                <ChevronRightIcon className="size-4 text-muted" />
              </Link>
            </motion.li>
          ))}
        </ul>
      )}
    </div>
  )
}
