import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../../auth/useAuth'
import { isLanguage } from '../../../i18n'
import { errorMessage } from '../../../lib/errors'
import { marketApi, type LeadSource, type PublicListing } from '../../../lib/marketApi'

export type ActionMessage = { tone: 'success' | 'error'; text: string }

// SRC-03 actions, shared by the desktop card, the phone lister row and the
// phone bottom bar so they show one busy state and one message.
// WhatsApp contact works for anyone; enquiry and viewing request need a
// signed-in buyer (LEAD-01 creates a lead with their name and WhatsApp).
export function useListingActions(listing: PublicListing) {
  const { t, i18n } = useTranslation()
  const { status } = useAuth()
  const [busy, setBusy] = useState<LeadSource | null>(null)
  const [message, setMessage] = useState<ActionMessage | null>(null)
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

  return { busy, message, askSignIn, active, openWhatsApp, sendLead }
}

export type ListingActions = ReturnType<typeof useListingActions>
