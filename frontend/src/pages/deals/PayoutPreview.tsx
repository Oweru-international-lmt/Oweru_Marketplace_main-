import { animate, motion, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BankIcon, HomeIcon, UserIcon } from '../../components/icons'
import { dealsApi, splitFor, type RateTable } from '../../lib/dealsApi'
import { formatNumber, formatTsh } from '../../lib/format'

// LST-09, PAY-02: the live payout preview on the listing form. After D16: the
// price on top, a two by two grid of shares, then the amounts listed, all
// worked out from the published rate table while the lister types.

function Rolling({ value, format }: { value: number; format: (value: number) => string }) {
  const node = useRef<HTMLSpanElement>(null)
  const last = useRef(value)
  const reduce = useReducedMotion()
  useEffect(() => {
    const element = node.current
    if (!element) return
    const from = last.current
    last.current = value
    if (reduce || from === value) {
      element.textContent = format(value)
      return
    }
    const controls = animate(from, value, { duration: 0.5, ease: [0.22, 1, 0.36, 1], onUpdate: (current) => (element.textContent = format(current)) })
    return () => controls.stop()
  }, [value, format, reduce])
  return <span ref={node} className="tabular-nums" />
}

export function PayoutPreview({ kind, price, ownerPrice }: { kind: '' | 'OWNER' | 'AGENT'; price: string; ownerPrice: string }) {
  const { t, i18n } = useTranslation()
  const [table, setTable] = useState<RateTable | null | undefined>(undefined)

  useEffect(() => {
    let live = true
    dealsApi
      .rateTable()
      .then((row) => live && setTable(row))
      .catch(() => live && setTable(null))
    return () => {
      live = false
    }
  }, [])

  if (!kind || table === undefined) return null
  if (table === null) return <p className="rounded-xl bg-paper px-4 py-3 text-[13px] text-muted">{t('deals.preview.noTable')}</p>

  const selling = Number(price) || 0
  const owner = kind === 'AGENT' ? Number(ownerPrice) || 0 : selling
  const split = selling > 0 && owner > 0 ? splitFor(table, owner, selling, kind) : null
  const money = (value: number) => formatTsh(Math.round(value), i18n.language)
  const percent = (value: number) => `${formatNumber(value * 100, i18n.language)} %`

  return (
    <motion.section layout className="overflow-hidden rounded-2xl border border-mist bg-white shadow-[0_10px_30px_-18px_rgba(15,23,42,0.35)]">
      <div className="border-b border-mist px-5 py-4">
        <p className="text-[11px] font-semibold tracking-[0.1em] text-muted uppercase">{t('deals.preview.title')}</p>
        <p className="mt-1 text-[24px] font-semibold text-navy">{selling ? <Rolling value={selling} format={money} /> : t('deals.preview.enterPrice')}</p>
      </div>
      {split ? (
        <>
          <div className="grid grid-cols-2">
            {[
              { label: t('deals.preview.ownerShare'), value: percent(kind === 'AGENT' ? 1 - split.totalRate : 1 - split.oweruRate) },
              { label: t('deals.preview.oweruShare'), value: percent(split.oweruRate) },
              ...(kind === 'AGENT'
                ? [
                    { label: t('deals.preview.agentShare'), value: percent(split.agentRate) },
                    { label: t('deals.preview.difference'), value: money(selling - owner) },
                  ]
                : []),
            ].map((cell, index) => (
              <div key={cell.label} className={`px-5 py-4 ${index % 2 === 0 ? 'border-r border-mist' : ''} border-b border-mist`}>
                <p className="text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">{cell.label}</p>
                <motion.p key={cell.value} initial={{ opacity: 0.3, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-1 text-[20px] font-medium text-navy tabular-nums">
                  {cell.value}
                </motion.p>
              </div>
            ))}
          </div>
          <dl className="space-y-2 px-5 py-4 text-[13px]">
            <div className="flex items-center gap-2.5">
              <HomeIcon className="size-4 text-muted" />
              <dt className="flex-1 text-[12px] font-medium tracking-[0.06em] text-navy-soft uppercase">{t('deals.preview.ownerGets')}</dt>
              <dd className="font-medium text-navy"><Rolling value={split.toOwner} format={money} /></dd>
            </div>
            <div className="flex items-center gap-2.5">
              <BankIcon className="size-4 text-muted" />
              <dt className="flex-1 text-[12px] font-medium tracking-[0.06em] text-navy-soft uppercase">{t('deals.preview.oweruKeeps')}</dt>
              <dd className="font-medium text-navy"><Rolling value={split.oweruKeeps} format={money} /></dd>
            </div>
            {kind === 'AGENT' && (
              <div className="flex items-center gap-2.5 border-t border-mist pt-3">
                <UserIcon className="size-4 text-[#9a6c12]" />
                <dt className="flex-1 text-[12px] font-semibold tracking-[0.06em] text-navy uppercase">{t('deals.preview.youReceive')}</dt>
                <dd className="text-[16px] font-bold text-navy"><Rolling value={split.agent} format={money} /></dd>
              </div>
            )}
          </dl>
          <p className="border-t border-mist bg-paper px-5 py-3 text-[12px] text-muted">{t('deals.preview.note', { version: table.version })}</p>
        </>
      ) : (
        <p className="px-5 py-4 text-[13px] text-muted">{kind === 'AGENT' && owner > selling ? t('deals.preview.belowOwner') : t('deals.preview.waiting')}</p>
      )}
    </motion.section>
  )
}
