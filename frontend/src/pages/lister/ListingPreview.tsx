import { useTranslation } from 'react-i18next'
import { ClockIcon, ImageIcon, MapPinIcon } from '../../components/icons'
import { formatRelative, formatTsh } from '../../lib/format'
import type { ListingStatus } from '../../lib/listerApi'
import { ListingStatusPill } from './ui'

type PreviewProps = {
  cover: string | null
  badge: string | null
  price: string
  title: string
  facts: string[]
  address: string
  createdAt: string | null
  photoCount: number
  status: ListingStatus | null
}

// After L1's preview: the cover photo with a white tag, the price large with
// the status on its right, the name and facts, a hairline, then icon rows.
export function ListingPreview({ cover, badge, price, title, facts, address, createdAt, photoCount, status }: PreviewProps) {
  const { t, i18n } = useTranslation()
  return (
    <div>
      <h2 className="mb-4 text-[18px] font-medium text-navy">{t('lister.preview.title')}</h2>
      <article className="rounded-lg border border-mist bg-white p-2">
        <div className="relative aspect-[388/202] overflow-hidden rounded-md bg-gradient-to-br from-paper to-mist">
          {cover ? (
            <img src={cover} alt="" className="size-full object-cover" />
          ) : (
            <span className="grid size-full place-items-center text-muted/70">
              <ImageIcon className="size-8" />
            </span>
          )}
          {badge && (
            <span className="absolute top-2.5 left-2.5 rounded-[5px] border border-mist bg-white px-2 py-0.5 text-[13px] text-navy">{badge}</span>
          )}
        </div>
        <div className="px-3 pt-4 pb-3">
          <div className="flex items-center justify-between gap-3">
            <p className="truncate text-[20px] font-medium text-navy tabular-nums">
              {price ? formatTsh(price, i18n.language) : <span className="text-muted/70">TSh -</span>}
            </p>
            {status && <ListingStatusPill status={status} />}
          </div>
          <p className="mt-3 truncate text-[15px] font-medium text-navy-soft">{title}</p>
          {facts.length > 0 && (
            <p className="mt-1.5 flex flex-wrap items-center gap-x-1.5 text-[13px] text-muted">
              {facts.map((fact, index) => (
                <span key={fact} className="inline-flex items-center gap-1.5">
                  {index > 0 && <span className="size-1 rounded-full bg-mist" aria-hidden="true" />}
                  {fact}
                </span>
              ))}
            </p>
          )}
          <div className="mt-4 space-y-2.5 border-t border-mist pt-4 text-[13px] text-navy-soft">
            <p className="flex items-start gap-2">
              <MapPinIcon className="mt-px size-4 shrink-0 text-muted" />
              <span className="min-w-0">{address || <span className="text-muted/70">{t('lister.preview.noAddress')}</span>}</span>
            </p>
            <p className="flex items-center gap-2">
              <ClockIcon className="size-4 shrink-0 text-muted" />
              {createdAt ? t('lister.preview.created', { when: formatRelative(createdAt, i18n.language) }) : t('lister.preview.notSaved')}
            </p>
            <p className="flex items-center gap-2">
              <ImageIcon className="size-4 shrink-0 text-muted" />
              {t('market.photoCount', { count: photoCount })}
            </p>
          </div>
        </div>
      </article>
    </div>
  )
}
