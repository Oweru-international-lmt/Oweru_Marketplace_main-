import { useTranslation } from 'react-i18next'
import { whatsappLink } from '../lib/config'
import { WhatsAppIcon } from './icons'

// For people who can't reach their email inbox: the user opens WhatsApp with a
// ready-made message to Oweru support (SRD section 20 self-service).
export function WhatsAppHelp({ email }: { email?: string }) {
  const { t } = useTranslation()
  const message = email ? t('forgot.whatsappMessageWithEmail', { email }) : t('forgot.whatsappMessage')

  return (
    <div className="rounded-2xl border border-mist bg-white p-5">
      <p className="font-display text-base font-semibold text-navy">{t('forgot.noEmailTitle')}</p>
      <p className="mt-1 text-sm leading-relaxed text-muted">{t('forgot.noEmailBody')}</p>
      <a
        href={whatsappLink(message)}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-4 inline-flex h-11 items-center gap-2.5 rounded-xl bg-[#1f7a4d] px-5 font-display text-sm font-semibold text-white transition-colors hover:bg-[#186440]"
      >
        <WhatsAppIcon className="size-5" />
        {t('forgot.whatsapp')}
      </a>
    </div>
  )
}
