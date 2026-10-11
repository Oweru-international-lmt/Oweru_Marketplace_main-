import { AnimatePresence, motion } from 'motion/react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { AlertIcon, ArrowRightIcon, CalendarIcon, ChatIcon, ShieldIcon, TickIcon, WhatsAppIcon } from '../../../components/icons'
import { formatDate, formatTsh } from '../../../lib/format'
import { initials } from '../../../lib/initials'
import type { PublicListing } from '../../../lib/marketApi'
import type { ListingActions } from './useListingActions'

// The result of the last action, or the sign-in prompt for guests.
export function ActionFeedback({ actions, className = '' }: { actions: ListingActions; className?: string }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const { message, askSignIn } = actions

  return (
    <AnimatePresence initial={false}>
      {(message || askSignIn) && (
        <motion.div
          key={message?.text ?? 'sign-in'}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="overflow-hidden"
        >
          <div className={className}>
            {message ? (
              <Alert tone={message.tone}>{message.text}</Alert>
            ) : (
              <div className="rounded-md bg-paper p-4 text-sm leading-relaxed text-navy">
                <p>{t('listing.signInPrompt')}</p>
                <Link to="/login" state={{ from: pathname }} className="text-link mt-2 inline-block">
                  {t('listing.signInAction')}
                </Link>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Desktop: price and the three actions in one card.
export function ContactActions({ listing, actions }: { listing: PublicListing; actions: ListingActions }) {
  const { t, i18n } = useTranslation()
  const { busy, active, openWhatsApp, sendLead } = actions

  return (
    <section aria-label={t('listing.contact')} className="rounded-md bg-white p-6 shadow-card">
      <p className="text-3xl font-bold text-navy">{formatTsh(listing.selling_price, i18n.language)}</p>
      <div className="mt-5 space-y-3">
        <ActionButton tone="whatsapp" busy={busy === 'WHATSAPP_CONTACT'} disabled={busy !== null} onClick={() => void openWhatsApp()}>
          <WhatsAppIcon className="size-5" />
          {busy === 'WHATSAPP_CONTACT' ? t('listing.contacting') : t('listing.contact')}
        </ActionButton>
        {active ? (
          <>
            <ActionButton tone="primary" busy={busy === 'ENQUIRY'} disabled={busy !== null} onClick={() => void sendLead('ENQUIRY')}>
              <ChatIcon className="size-5" />
              {busy === 'ENQUIRY' ? t('listing.sending') : t('listing.enquire')}
            </ActionButton>
            <ActionButton tone="secondary" busy={busy === 'VIEWING_REQUEST'} disabled={busy !== null} onClick={() => void sendLead('VIEWING_REQUEST')}>
              <CalendarIcon className="size-5" />
              {busy === 'VIEWING_REQUEST' ? t('listing.sending') : t('listing.viewing')}
            </ActionButton>
          </>
        ) : (
          <p className="rounded-md bg-paper px-4 py-3 text-sm leading-relaxed text-muted">{t('listing.underOfferNote')}</p>
        )}
      </div>
      <ActionFeedback actions={actions} className="pt-4" />
    </section>
  )
}

function ActionButton({
  tone,
  busy,
  disabled,
  onClick,
  children,
}: {
  tone: 'whatsapp' | 'primary' | 'secondary'
  busy: boolean
  disabled: boolean
  onClick: () => void
  children: ReactNode
}) {
  const styles = {
    whatsapp: 'bg-[#1f7a4d] text-white hover:bg-[#186440]',
    primary: 'bg-navy text-white hover:bg-navy-soft shadow-[0_10px_24px_-12px_rgba(15,23,42,0.8)]',
    secondary: 'bg-white text-navy ring-1 ring-mist hover:ring-navy/30',
  }
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-busy={busy || undefined}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      className={`inline-flex h-12 w-full items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-70 ${styles[tone]}`}
    >
      {children}
    </motion.button>
  )
}

// Desktop lister card. IDV-06: the agent text is fixed wording.
export function ListerCard({ listing }: { listing: PublicListing }) {
  const { t, i18n } = useTranslation()
  const { display_name: name, lister_kind: kind, member_since: since } = listing.lister

  return (
    <section aria-labelledby="lister-title" className="rounded-md bg-white p-6 shadow-card">
      <h2 id="lister-title" className="text-xs font-semibold tracking-[0.2em] text-gold uppercase">
        {t('listing.lister')}
      </h2>
      <div className="mt-4 flex items-center gap-4">
        <span className="grid size-14 shrink-0 place-items-center rounded-lg bg-navy font-serif text-lg font-semibold text-gold-light">
          {initials(name)}
        </span>
        <div className="min-w-0">
          <p className="truncate font-serif text-xl font-semibold text-navy">{name}</p>
          <p className="text-sm text-muted">{kind === 'AGENT' ? t('listing.agent') : t('listing.owner')}</p>
        </div>
      </div>
      <p className="mt-4 text-sm text-muted">{t('listing.memberSince', { date: formatDate(since, i18n.language) })}</p>
      {kind === 'AGENT' && <p className="mt-3 rounded-md bg-paper px-4 py-3 text-sm leading-relaxed text-navy">{t('levels.agentNote')}</p>}
    </section>
  )
}

// Phones, after the M8 reference: avatar, name with a tick when the identity
// is verified, role, and round chat and WhatsApp buttons on the right.
export function ListerRow({ listing, actions }: { listing: PublicListing; actions: ListingActions }) {
  const { t } = useTranslation()
  const { display_name: name, lister_kind: kind, verification } = listing.lister
  const { busy, active, openWhatsApp, sendLead } = actions

  return (
    <section aria-label={t('listing.lister')}>
      <div className="flex items-center gap-3">
        <span className="grid size-12 shrink-0 place-items-center rounded-full bg-navy text-sm font-semibold text-gold-light">{initials(name)}</span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 truncate text-[15px] font-semibold text-navy">
            <span className="truncate">{name}</span>
            {verification.level >= 1 && (
              <>
                <TickIcon className="size-4 shrink-0 text-gold" />
                <span className="sr-only">{t('levels.short.1')}</span>
              </>
            )}
          </p>
          <p className="text-xs text-muted">{kind === 'AGENT' ? t('listing.agent') : t('listing.owner')}</p>
        </div>
        {active && (
          <RoundButton label={t('listing.enquire')} busy={busy === 'ENQUIRY'} disabled={busy !== null} onClick={() => void sendLead('ENQUIRY')}>
            <ChatIcon className="size-5" />
          </RoundButton>
        )}
        <RoundButton label={t('listing.contact')} busy={busy === 'WHATSAPP_CONTACT'} disabled={busy !== null} onClick={() => void openWhatsApp()}>
          <WhatsAppIcon className="size-5" />
        </RoundButton>
      </div>
      {kind === 'AGENT' && <p className="mt-3 rounded-xl bg-white px-4 py-3 text-xs leading-relaxed text-muted shadow-card">{t('levels.agentNote')}</p>}
    </section>
  )
}

function RoundButton({ label, busy, disabled, onClick, children }: { label: string; busy: boolean; disabled: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <motion.button
      type="button"
      aria-label={label}
      title={label}
      aria-busy={busy || undefined}
      disabled={disabled}
      onClick={onClick}
      whileTap={disabled ? undefined : { scale: 0.92 }}
      className="grid size-11 shrink-0 place-items-center rounded-full bg-gold/15 text-navy transition-colors hover:bg-gold/25 disabled:opacity-60"
    >
      {children}
    </motion.button>
  )
}

// Phones, after the M8 reference: a white bar with the price on the left and
// one dark pill on the right ("Schedule tour" there, a viewing request here).
export function MobileActionBar({ listing, actions }: { listing: PublicListing; actions: ListingActions }) {
  const { t, i18n } = useTranslation()
  const { busy, active, openWhatsApp, sendLead } = actions

  return (
    <div className="fixed inset-x-0 bottom-0 z-30 rounded-t-[28px] bg-white px-5 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-[0_-12px_32px_-16px_rgba(15,23,42,0.35)] lg:hidden">
      <ActionFeedback actions={actions} className="pb-3" />
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0 shrink-0">
          <p className="text-xs text-muted">{active ? t('listing.price') : t('market.underOffer')}</p>
          <p className="text-lg font-bold whitespace-nowrap text-navy">{formatTsh(listing.selling_price, i18n.language)}</p>
        </div>
        <motion.button
          type="button"
          whileTap={busy ? undefined : { scale: 0.97 }}
          disabled={busy !== null}
          aria-busy={busy === 'VIEWING_REQUEST' || busy === 'WHATSAPP_CONTACT' || undefined}
          onClick={() => void (active ? sendLead('VIEWING_REQUEST') : openWhatsApp())}
          className="inline-flex h-13 min-w-0 items-center justify-center rounded-full bg-navy px-5 text-[13px] leading-tight font-semibold text-white disabled:opacity-70"
        >
          {busy === 'VIEWING_REQUEST' ? t('listing.sending') : active ? t('listing.viewing') : 'WhatsApp'}
        </motion.button>
      </div>
    </div>
  )
}

// FUL-01 entry point: the fee and scope come first on the order page, which
// asks guests to sign in.
export function FullCheckCard({ listing }: { listing: PublicListing }) {
  const { t } = useTranslation()
  if (listing.lister.verification.level === 3) return null

  return (
    <section className="relative overflow-hidden rounded-xl bg-navy p-6 text-white">
      <ShieldIcon className="absolute -top-4 -right-4 size-28 text-white/5" />
      <h2 className="font-serif text-xl font-semibold">{t('listing.fullCheckTitle')}</h2>
      <p className="mt-2 text-sm leading-relaxed text-white/75">{t('listing.fullCheckBody')}</p>
      <Link
        to={`/listings/${encodeURIComponent(listing.listing_id)}/full-check`}
        className="group mt-5 inline-flex h-11 items-center gap-2 rounded-md bg-gold px-4 text-sm font-semibold text-navy hover:bg-gold-light"
      >
        {t('listing.fullCheckCta')}
        <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" />
      </Link>
    </section>
  )
}

// CMP-01: the complaint form opens with this property's number filled in.
export function ReportLink({ listing }: { listing: PublicListing }) {
  const { t } = useTranslation()
  const query = new URLSearchParams({ property: listing.property.property_id, type: 'FAKE_LISTING' })
  return (
    <Link
      to={`/complaints/new?${query}`}
      className="inline-flex h-11 items-center gap-2 text-sm font-medium text-muted underline decoration-mist underline-offset-4 hover:text-navy hover:decoration-navy/40"
    >
      <AlertIcon className="size-4" />
      {t('listing.report')}
    </Link>
  )
}
