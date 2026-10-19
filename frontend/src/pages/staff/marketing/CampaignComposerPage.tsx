import { AnimatePresence, motion } from 'motion/react'
import { useRef, useState, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { ChevronRightIcon, DocumentIcon, EyeIcon, LockIcon, MailIcon, UsersIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { panelApi, type CampaignInput } from '../../../lib/panelApi'

type Lang = 'sw' | 'en'
const DRAFT_KEY = 'oweru.campaignDraft'
const EMPTY: CampaignInput = { subject_sw: '', subject_en: '', body_sw: '', body_en: '', target_path: '/listings', source_tag: '' }

function SendIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M21 3 10 14M21 3l-7 18-4-7-7-4 18-7Z" />
    </svg>
  )
}

function SaveIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M5 3h11l3 3v15H5z" />
      <path d="M8 3v5h7V3M8 21v-7h8v7" />
    </svg>
  )
}

function loadDraft(): CampaignInput {
  try {
    const saved = localStorage.getItem(DRAFT_KEY)
    return saved ? { ...EMPTY, ...(JSON.parse(saved) as Partial<CampaignInput>) } : EMPTY
  } catch {
    return EMPTY
  }
}

// MAR-03 and MAR-04, after M9: the trail and title with Preview, Save draft
// and Send; the parts and starter templates on the left, the email itself in
// the middle, and its link and source tag on the right.
export function CampaignComposerPage() {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('staff.marketing.composer.title'))
  const navigate = useNavigate()
  const [values, setValues] = useState<CampaignInput>(loadDraft)
  const [lang, setLang] = useState<Lang>(i18n.language === 'en' ? 'en' : 'sw')
  const [template, setTemplate] = useState<string | null>(null)
  const [preview, setPreview] = useState(false)
  const [saved, setSaved] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const subject = useRef<HTMLInputElement>(null)
  const body = useRef<HTMLTextAreaElement>(null)
  const link = useRef<HTMLInputElement>(null)

  const set = (key: keyof CampaignInput, value: string) => {
    setSaved(false)
    setValues((current) => ({ ...current, [key]: value }))
  }
  const ready = Boolean(values.subject_sw.trim() && values.subject_en.trim() && values.body_sw.trim() && values.body_en.trim() && values.target_path.startsWith('/') && /^[a-z0-9-]{1,100}$/.test(values.source_tag))

  function applyTemplate(key: string) {
    setTemplate(key)
    setSaved(false)
    setValues((current) => ({
      ...current,
      subject_sw: t(`staff.marketing.composer.templates.${key}.subject`, { lng: 'sw' }),
      subject_en: t(`staff.marketing.composer.templates.${key}.subject`, { lng: 'en' }),
      body_sw: t(`staff.marketing.composer.templates.${key}.body`, { lng: 'sw' }),
      body_en: t(`staff.marketing.composer.templates.${key}.body`, { lng: 'en' }),
      target_path: t(`staff.marketing.composer.templates.${key}.path`),
    }))
  }

  function saveDraft() {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(values))
      setSaved(true)
    } catch {
      setSaved(false)
    }
  }

  async function send() {
    setSending(true)
    setError(null)
    try {
      await panelApi.sendCampaign(values)
      try {
        localStorage.removeItem(DRAFT_KEY)
      } catch {
        /* nothing to clear */
      }
      navigate('/staff/marketing/campaigns')
    } catch (caught) {
      setError(errorMessage(t, caught))
      setConfirm(false)
      setSending(false)
    }
  }

  const parts = [
    { key: 'subject', icon: MailIcon, ref: subject },
    { key: 'body', icon: DocumentIcon, ref: body },
    { key: 'link', icon: ChevronRightIcon, ref: link },
  ] as const

  return (
    <div className="rounded-[24px] bg-[radial-gradient(#dfe3ea_1px,transparent_1px)] [background-size:16px_16px] p-3 sm:p-4">
      <nav aria-label={t('nav.breadcrumb')} className="text-[14px] text-navy-soft">
        <Link to="/staff/marketing/campaigns" className="hover:text-navy">{t('staff.marketing.campaigns.title')}</Link>
        <span className="mx-2 text-muted">/</span>
        <span className="text-navy">{t('staff.marketing.composer.title')}</span>
      </nav>
      <header className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white/80 px-5 py-4 backdrop-blur">
        <div>
          <h1 className="text-[26px] leading-tight font-medium text-navy">{t('staff.marketing.composer.title')}</h1>
          <p className="text-[13.5px] text-navy-soft">{saved ? t('staff.marketing.composer.saved') : t('staff.marketing.composer.draft')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => setPreview((value) => !value)} aria-pressed={preview} className={`inline-flex h-11 items-center gap-2 rounded-xl border px-4 text-[14px] ${preview ? 'border-navy bg-navy/5 text-navy' : 'border-mist bg-[#f1f2f4] text-navy'}`}>
            <EyeIcon className="size-[18px]" />
            {t('staff.marketing.composer.preview')}
          </button>
          <button type="button" onClick={saveDraft} className="inline-flex h-11 items-center gap-2 rounded-xl border border-mist bg-[#f1f2f4] px-4 text-[14px] text-navy">
            <SaveIcon className="size-[18px]" />
            {t('staff.marketing.composer.saveDraft')}
          </button>
          <button type="button" onClick={() => setConfirm(true)} disabled={!ready} className="inline-flex h-11 items-center gap-2 rounded-xl bg-navy px-5 text-[14px] font-medium text-white shadow-[0_6px_16px_-6px_rgba(15,23,42,0.5)] disabled:opacity-45">
            <SendIcon className="size-[18px]" />
            {t('staff.marketing.composer.send')}
          </button>
        </div>
      </header>

      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}

      <div className="mt-5 grid items-start gap-5 xl:grid-cols-[240px_minmax(0,1fr)_280px]">
        <aside className="rounded-[20px] border border-mist/80 bg-white px-5 py-5">
          <h2 className="text-[17px] font-medium text-navy">{t('staff.marketing.composer.builder')}</h2>
          <p className="mt-1 text-[13.5px] text-navy-soft">{t('staff.marketing.composer.builderHint')}</p>
          <p className="mt-5 text-[13.5px] text-navy-soft">{t('staff.marketing.composer.parts')}</p>
          <ul className="mt-2 space-y-2">
            {parts.map(({ key, icon: Icon, ref }) => (
              <li key={key}>
                <button type="button" onClick={() => ref.current?.focus()} className="flex h-10 w-full items-center gap-2.5 rounded-lg border border-mist px-3 text-[14px] text-navy hover:border-navy/30">
                  <span className="grid size-6 place-items-center rounded-md bg-gold/12 text-[#9a6c12]"><Icon className="size-3.5" /></span>
                  {t(`staff.marketing.composer.partNames.${key}`)}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-5 text-[13.5px] text-navy-soft">{t('staff.marketing.composer.templatesTitle')}</p>
          <ul className="mt-2 space-y-2">
            {(['listings', 'freeCheck', 'guide'] as const).map((key) => (
              <li key={key}>
                <button
                  type="button"
                  aria-pressed={template === key}
                  onClick={() => applyTemplate(key)}
                  className={`h-11 w-full rounded-lg border px-3 text-left text-[14px] text-navy ${template === key ? 'border-gold bg-gold/10' : 'border-mist hover:border-navy/30'}`}
                >
                  {t(`staff.marketing.composer.templates.${key}.name`)}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="overflow-hidden rounded-[20px] border border-mist/80 bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-mist px-5 pt-4 pb-3">
            <div className="min-w-0 flex-1">
              <label className="sr-only" htmlFor="subject">{t('staff.marketing.composer.subject')}</label>
              <input
                id="subject"
                ref={subject}
                value={lang === 'sw' ? values.subject_sw : values.subject_en}
                onChange={(event) => set(lang === 'sw' ? 'subject_sw' : 'subject_en', event.target.value)}
                maxLength={200}
                readOnly={preview}
                placeholder={t('staff.marketing.composer.subject')}
                className="w-full bg-transparent text-[24px] text-navy outline-none placeholder:text-[#b9bfca]"
              />
              <p className="text-[13px] text-[#b9bfca]">{t('staff.marketing.composer.previewText', { language: t(`staff.marketing.composer.languages.${lang}`) })}</p>
            </div>
            <div role="tablist" aria-label={t('staff.marketing.composer.language')} className="flex shrink-0 rounded-lg bg-paper p-1">
              {(['sw', 'en'] as const).map((value) => (
                <button key={value} type="button" role="tab" aria-selected={lang === value} onClick={() => setLang(value)} className={`h-8 rounded-md px-3 text-[12.5px] font-medium ${lang === value ? 'bg-white text-navy shadow-sm' : 'text-navy-soft'}`}>
                  {value.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-5 px-5 py-5">
            <div className={`rounded-xl p-2 ${preview ? '' : 'ring-1 ring-gold/60'}`}>
              <label className="sr-only" htmlFor="body">{t('staff.marketing.composer.body')}</label>
              <textarea
                id="body"
                ref={body}
                rows={10}
                value={lang === 'sw' ? values.body_sw : values.body_en}
                onChange={(event) => set(lang === 'sw' ? 'body_sw' : 'body_en', event.target.value)}
                maxLength={10000}
                readOnly={preview}
                placeholder={t('staff.marketing.composer.bodyHint')}
                className="w-full resize-y bg-transparent text-[15px] leading-relaxed text-navy outline-none placeholder:text-[#b9bfca]"
              />
            </div>
            <div className="flex justify-center">
              <span className="inline-flex h-11 items-center rounded-xl bg-navy px-6 text-[15px] font-medium text-white shadow-[0_6px_16px_-6px_rgba(15,23,42,0.5)]">{t('staff.marketing.composer.cta')}</span>
            </div>
            <div className="space-y-2">
              <label className="block">
                <span className="sr-only">{t('staff.marketing.composer.link')}</span>
                <input
                  ref={link}
                  value={values.target_path}
                  onChange={(event) => set('target_path', event.target.value)}
                  readOnly={preview}
                  className="h-11 w-full rounded-lg border border-mist px-3.5 text-[14px] text-navy outline-none focus:border-gold"
                />
              </label>
              <p className="rounded-lg border border-mist bg-paper/60 px-3.5 py-2.5 font-mono text-[12.5px] break-all text-navy-soft">
                {values.target_path || '/'}?source_tag={values.source_tag || '…'}
              </p>
            </div>
            <p className="border-t border-mist pt-4 text-center text-[12px] text-muted">{t('staff.marketing.composer.footer')}</p>
          </div>
        </section>

        <aside className="rounded-[20px] border border-mist/80 bg-white px-5 py-5">
          <h2 className="text-[17px] font-medium text-navy">{t('staff.marketing.composer.properties')}</h2>
          <label className="mt-4 block text-[14px] text-navy">
            {t('staff.marketing.composer.tag')}
            <input
              value={values.source_tag}
              onChange={(event) => set('source_tag', event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))}
              placeholder="newsletter-nov"
              className="mt-1.5 h-11 w-full rounded-lg border border-mist px-3 font-mono text-[13.5px] text-navy outline-none focus:border-gold"
            />
            <span className="mt-1 block text-[12px] text-muted">{t('staff.marketing.composer.tagHint')}</span>
          </label>
          <p className="mt-5 text-[14px] text-navy">{t('staff.marketing.composer.languagesTitle')}</p>
          <ul className="mt-2 space-y-2 text-[13px]">
            {(['sw', 'en'] as const).map((value) => {
              const done = Boolean((value === 'sw' ? values.subject_sw : values.subject_en).trim() && (value === 'sw' ? values.body_sw : values.body_en).trim())
              return (
                <li key={value} className="flex h-10 items-center justify-between rounded-lg border border-mist px-3">
                  <span className="text-navy">{t(`staff.marketing.composer.languages.${value}`)}</span>
                  <span className={done ? 'text-success' : 'text-muted'}>{done ? t('staff.marketing.composer.ready') : t('staff.marketing.composer.missing')}</span>
                </li>
              )
            })}
          </ul>
          <p className="mt-5 text-[14px] text-navy">{t('staff.marketing.composer.audience')}</p>
          <p className="mt-2 flex items-start gap-2 rounded-lg bg-paper px-3 py-2.5 text-[12.5px] text-navy-soft"><UsersIcon className="mt-0.5 size-4 shrink-0" />{t('staff.marketing.composer.audienceBody')}</p>
          <p className="mt-3 flex items-start gap-2 text-[12px] text-muted"><LockIcon className="mt-0.5 size-3.5 shrink-0" />{t('staff.marketing.composer.wording')}</p>
        </aside>
      </div>

      <AnimatePresence>
        {confirm && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[1000] grid place-items-center bg-navy/45 p-4">
            <motion.div role="dialog" aria-modal="true" aria-labelledby="send-title" initial={{ y: 12 }} animate={{ y: 0 }} exit={{ y: 12 }} className="w-full max-w-md rounded-2xl bg-white p-5">
              <h2 id="send-title" className="text-[18px] font-semibold text-navy">{t('staff.marketing.composer.confirmTitle')}</h2>
              <p className="mt-1.5 text-[14px] text-navy-soft">{t('staff.marketing.composer.confirmBody', { tag: values.source_tag })}</p>
              <div className="mt-5 flex justify-end gap-2">
                <button type="button" onClick={() => setConfirm(false)} className="h-10 rounded-lg border border-mist px-4 text-[14px] text-navy">{t('staff.marketing.composer.cancel')}</button>
                <button type="button" onClick={send} disabled={sending} className="inline-flex h-10 items-center gap-2 rounded-lg bg-navy px-4 text-[14px] font-medium text-white disabled:opacity-60">
                  <SendIcon className="size-4" />
                  {sending ? t('staff.marketing.composer.sending') : t('staff.marketing.composer.send')}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
