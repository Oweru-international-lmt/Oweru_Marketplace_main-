import { motion } from 'motion/react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LockIcon, WhatsAppIcon } from '../../components/icons'
import { whatsappTo } from '../../lib/config'

type Props = {
  name: string
  password: string
  // Known when the account was just created; lookups carry no contact details.
  email?: string
  phone?: string
  onDone: () => void
}

// ACC-06: the temporary password is shown once, to be passed on by WhatsApp.
export function TemporaryPasswordPanel({ name, password, email, phone, onDone }: Props) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}/login`
  const message = email
    ? t('staffAccount.newAccountMessage', { name, email, password, url })
    : t('staffAccount.resetMessage', { name, password, url })

  async function copy() {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-gold/40 bg-gold/10 p-5"
      role="status"
    >
      <p className="flex items-center gap-2 font-display text-base font-semibold text-navy">
        <LockIcon className="size-5" />
        {t('staffAccount.tempTitle')}
      </p>
      <p className="mt-1 text-sm text-muted">{t('staffAccount.tempBody')}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <code className="rounded-lg bg-white px-4 py-2.5 font-mono text-lg tracking-wide text-navy ring-1 ring-mist select-all">
          {password}
        </code>
        <button
          type="button"
          onClick={() => void copy()}
          className="h-10 rounded-lg bg-white px-4 text-sm font-medium text-navy ring-1 ring-mist hover:bg-paper"
        >
          {copied ? t('staffAccount.copied') : t('staffAccount.copy')}
        </button>
        <a
          href={whatsappTo(phone ?? null, message)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#1f7a4d] px-4 text-sm font-semibold text-white hover:bg-[#186440]"
        >
          <WhatsAppIcon className="size-4" />
          {t('staffAccount.sendWhatsApp')}
        </a>
        <button type="button" onClick={onDone} className="text-link ml-auto text-sm">
          {t('staffAccount.done')}
        </button>
      </div>
    </motion.div>
  )
}
