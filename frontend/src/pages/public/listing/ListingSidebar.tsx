import { AnimatePresence, motion } from 'motion/react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../../auth/useAuth'
import { Alert } from '../../../components/Alert'
import { CalendarIcon, ChatIcon, ShieldIcon, WhatsAppIcon } from '../../../components/icons'
import { isLanguage } from '../../../i18n'
import { whatsappLink } from '../../../lib/config'
import { errorMessage } from '../../../lib/errors'
import { formatDate, formatTsh } from '../../../lib/format'
import { initials } from '../../../lib/initials'
import { marketApi, type LeadSource, type PublicListing } from '../../../lib/marketApi'

type Busy = LeadSource | null
type Message = { tone: 'success' | 'error'; text: string }

// SRC-03 buttons: WhatsApp contact (anyone), enquiry and viewing request
// (signed-in buyers; LEAD-01 creates a lead with their name and WhatsApp).
export function ContactActions({ listing }: { listing: PublicListing }) {
  const { t, i18n } = useTranslation()
  const { status } = useAuth()
  const { pathname } = useLocation()
  const [busy, setBusy] = useState<Busy>(null)
  const [message, setMessage] = useState<Message | null>(null)
  const [askSignIn, setAskSignIn] = useState(false)
  const active = listing.status === 'ACTIVE'
  const signedIn = status === 'authenticated'

  async function openWhatsApp() {
    setMessage(null)
    // Open the tab inside the click so pop-up blockers allow it, then point it at WhatsApp.
    const tab = window.open('about:blank', '_blank')
    if (tab) tab.opener = null
    setBusy('WHATSAPP_CONTACT')
    try {
      const language = isLanguage(i18n.language) ? i18n.language : 'sw'
      const { whatsapp_link: link } = await marketApi.contactLink(listing.listing_id, language)
      if (tab) tab.location.href = link
      else window.location.href = link
      if (signedIn && active) void marketApi.createLead(listing.listing_id, 'WHATSAPP_CONTACT').catch(() => undefined)
    } catch (error) {
      tab?.close()
      setMessage({ tone: 'error', text: errorMessage(t, error) })
    } finally {
      setBusy(null)
    }
  }

  async function sendLead(source: 'ENQUIRY' | 'VIEWING_REQUEST') {
    setMessage(null)
    if (!signedIn) {
      setAskSignIn(true)
      return
    }
    setBusy(source)
    try {
      await marketApi.createLead(listing.listing_id, source)
      setMessage({ tone: 'success', text: source === 'ENQUIRY' ? t('listing.enquirySent') : t('listing.viewingSent') })
    } catch (error) {
      setMessage({ tone: 'error', text: errorMessage(t, error) })
    } finally {
      setBusy(null)
    }
  }

  // `spacing` separates the message from the buttons: above them in the card, below in the phone bar.
  const feedback = (spacing: string) => (
    <AnimatePresence initial={false}>
      {(message || askSignIn) && (
        <motion.div
          key={message?.text ?? 'sign-in'}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="overflow-hidden"
        >
          <div className={spacing}>
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

  return (
    <>
      <section aria-label={t('listing.contact')} className="rounded-md bg-white p-6 shadow-card">
        <p className="hidden text-3xl font-bold text-navy lg:block">{formatTsh(listing.selling_price, i18n.language)}</p>
        <div className="space-y-3 lg:mt-5">
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
        <div className="hidden lg:block">{feedback('pt-4')}</div>
      </section>

      {/* Phones: the two main actions and their feedback stay within thumb reach. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-mist bg-white/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur lg:hidden">
        <div className="mx-auto max-w-xl">{feedback('pb-3')}</div>
        <div className="mx-auto flex max-w-xl gap-3">
          <ActionButton tone="whatsapp" busy={busy === 'WHATSAPP_CONTACT'} disabled={busy !== null} onClick={() => void openWhatsApp()}>
            <WhatsAppIcon className="size-5" />
            <span aria-hidden="true">WhatsApp</span>
            <span className="sr-only">{t('listing.contact')}</span>
          </ActionButton>
          {active && (
            <ActionButton tone="primary" busy={busy === 'ENQUIRY'} disabled={busy !== null} onClick={() => void sendLead('ENQUIRY')}>
              <ChatIcon className="size-5" />
              {t('listing.enquire')}
            </ActionButton>
          )}
        </div>
      </div>
    </>
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

// IDV-06: the agent text is fixed wording.
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

// FUL-01 entry point. Online ordering comes with the buyer screens; until
// then the button opens Oweru's WhatsApp with the property reference.
export function FullCheckCard({ listing }: { listing: PublicListing }) {
  const { t } = useTranslation()
  if (listing.lister.verification.level === 3) return null

  return (
    <section className="relative overflow-hidden rounded-xl bg-navy p-6 text-white">
      <ShieldIcon className="absolute -top-4 -right-4 size-28 text-white/5" />
      <h2 className="font-serif text-xl font-semibold">{t('listing.fullCheckTitle')}</h2>
      <p className="mt-2 text-sm leading-relaxed text-white/75">{t('listing.fullCheckBody')}</p>
      <p className="mt-3 text-xs leading-relaxed text-white/55">{t('listing.fullCheckSoon')}</p>
      <a
        href={whatsappLink(t('listing.fullCheckMessage', { reference: listing.property.property_id }))}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-5 inline-flex h-11 items-center gap-2 rounded-md bg-gold px-4 text-sm font-semibold text-navy hover:bg-gold-light"
      >
        <WhatsAppIcon className="size-4" />
        {t('site.support')}
      </a>
    </section>
  )
}
