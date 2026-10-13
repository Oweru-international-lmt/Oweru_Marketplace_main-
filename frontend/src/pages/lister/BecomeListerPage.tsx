import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'
import { can } from '../../auth/access'
import { useAuth } from '../../auth/useAuth'
import { WhatsAppIcon } from '../../components/icons'
import { PageHeader } from '../../components/PageHeader'
import { whatsappLink } from '../../lib/config'
import { StartArt } from './identityArt'

// Owner and Agent roles are granted by Oweru, not chosen at sign-up, so a
// buyer who wants to sell asks Oweru on WhatsApp.
export function BecomeListerPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  if (can(user, 'lister.area')) return <Navigate to="/lister" replace />
  const steps = t('lister.become.steps', { returnObjects: true }) as string[]

  return (
    <>
      <PageHeader title={t('lister.become.title')} />
      <div className="mx-auto max-w-[560px] rounded-2xl border border-mist bg-white px-6 py-9 text-center sm:px-10">
        <div className="mx-auto w-[200px] scale-[0.8]">
          <StartArt />
        </div>
        <h2 className="mt-2 text-[24px] leading-tight font-bold text-navy">{t('lister.become.heading')}</h2>
        <p className="mx-auto mt-3 max-w-[420px] text-[14.5px] leading-relaxed text-navy-soft">{t('lister.become.body')}</p>
        <ol className="mx-auto mt-7 max-w-[400px] space-y-3 text-left">
          {steps.map((step, index) => (
            <li key={step} className="flex gap-3 text-[14px] text-navy">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-gold/15 text-[12px] font-semibold text-[#7a5410]">{index + 1}</span>
              {step}
            </li>
          ))}
        </ol>
        <a
          href={whatsappLink(t('lister.become.message', { name: user?.full_name ?? '' }))}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-8 inline-flex h-12 items-center gap-2.5 rounded-xl bg-gold px-6 text-[15px] font-semibold text-navy hover:bg-gold-light"
        >
          <WhatsAppIcon className="size-5" />
          {t('lister.become.action')}
        </a>
      </div>
    </>
  )
}
