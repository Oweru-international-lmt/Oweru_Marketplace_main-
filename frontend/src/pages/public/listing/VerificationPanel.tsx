import { useTranslation } from 'react-i18next'
import { AlertIcon, ShieldIcon } from '../../../components/icons'
import { VerificationBadge } from '../../../components/market/VerificationBadge'
import { formatDate } from '../../../lib/format'
import type { PublicListing } from '../../../lib/marketApi'

function notCheckedText(value: unknown): string | null {
  if (Array.isArray(value)) return value.filter((item) => typeof item === 'string').join(', ') || null
  return typeof value === 'string' && value.trim() ? value : null
}

// SRD 10 and 11.4. Labels come from fixed translation strings (LVL-02);
// the API's English label is only a fallback when dates are missing.
export function VerificationPanel({ listing }: { listing: PublicListing }) {
  const { t, i18n } = useTranslation()
  const { verification, display_name: name, lister_kind: kind } = listing.lister
  const { level } = verification
  const date = (value: string) => formatDate(value, i18n.language)

  const label =
    level === 3
      ? verification.completed_at && verification.expires_at
        ? t('levels.label3', { completed: date(verification.completed_at), expires: date(verification.expires_at) })
        : verification.label
      : t(`levels.label${level}`, { name })

  return (
    <section aria-labelledby="verification-title" className="rounded-2xl bg-white p-5 shadow-card sm:rounded-xl sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="verification-title" className="flex items-center gap-2 text-base font-bold text-navy sm:font-serif sm:text-2xl sm:font-semibold">
          <ShieldIcon className="size-5 text-gold sm:size-6" />
          {t('listing.verification')}
        </h2>
        <VerificationBadge level={level} size="md" />
      </div>

      <p className="mt-5 text-[15px] leading-relaxed font-medium text-navy">{label}</p>
      {kind === 'OWNER' && level < 3 && <p className="mt-2 text-sm leading-relaxed text-muted">{t('levels.ownerStatement', { name })}</p>}

      {verification.title_warning && (
        <p className="mt-4 flex gap-2.5 rounded-md bg-gold/10 px-4 py-3 text-sm leading-relaxed text-navy">
          <AlertIcon className="mt-0.5 size-4 shrink-0 text-gold" />
          {t('levels.titleWarning')}
        </p>
      )}

      {verification.checks && verification.checks.length > 0 && (
        <div className="mt-6 border-t border-mist pt-5">
          <h3 className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('listing.checksDone')}</h3>
          <ul className="mt-4 space-y-4">
            {verification.checks.map((check) => {
              const partners = check.partners
                .map((partner) => `${partner.name} (${t(`roleNames.${partner.role}`, { defaultValue: partner.role })})`)
                .join(', ')
              const missing = notCheckedText(check.not_checked)
              return (
                <li key={`${check.name}-${check.date}`} className="rounded-lg bg-paper p-4">
                  <p className="font-semibold text-navy">{check.name}</p>
                  <dl className="mt-2 space-y-1 text-sm text-muted">
                    <div>{t('listing.checkedOn', { date: date(check.date) })}</div>
                    <div>{t('listing.validUntil', { date: date(check.expires_at) })}</div>
                    {partners && <div>{t('listing.carriedOutBy', { names: partners })}</div>}
                    <div>{t('listing.staffReference', { reference: check.staff_reference.slice(0, 8) })}</div>
                    {missing && (
                      <div>
                        <dt className="inline font-medium text-navy">{t('listing.notChecked')}: </dt>
                        <dd className="inline">{missing}</dd>
                      </div>
                    )}
                  </dl>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      <p className="mt-6 text-xs text-muted">{t('listing.mapsNote')}</p>
    </section>
  )
}
