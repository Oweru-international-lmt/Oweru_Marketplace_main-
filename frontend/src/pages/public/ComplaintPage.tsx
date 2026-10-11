import { AnimatePresence, motion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { ArrowLeftIcon, ChevronRightIcon, CloseIcon, MapPinIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { isLanguage } from '../../i18n'
import { ApiError } from '../../lib/api'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem, looksLikeWhatsApp } from '../../lib/files'
import { formatDate } from '../../lib/format'
import { COMPLAINT_ROLES, COMPLAINT_TYPES, servicesApi, tokenFrom, type ComplaintRole, type ComplaintSummary, type ComplaintType } from '../../lib/servicesApi'
import { emailError } from '../../lib/validation'
import { Chips, Field, PhotoBox } from './services/fields'
import { ReceiptBrand, ReceiptCard, ReceiptFooter, ReceiptPage, ReceiptRow, ReceiptRows, ReceiptSeal, ReceiptSection } from './services/receipt'
import { CopyButton, Panel } from './services/ServiceUi'

type Errors = Partial<Record<'name' | 'phone' | 'email' | 'complainant_role' | 'property_reference' | 'description' | 'evidence', string>>

type Received = ComplaintSummary & { token: string; category: ComplaintType }

function isType(value: string | null): value is ComplaintType {
  return COMPLAINT_TYPES.includes(value as ComplaintType)
}

// CMP-01 without an account, after S5: pick what the complaint is about from
// a list, then one screen with the details, a photo box and one Send button.
// A property page links here with ?property= (and ?type=) filled in.
export function ComplaintPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('complaint.title'))
  const [params] = useSearchParams()
  const [category, setCategory] = useState<ComplaintType | ''>(() => (isType(params.get('type')) ? (params.get('type') as ComplaintType) : ''))
  const [received, setReceived] = useState<Received | null>(null)

  if (received) return <ReceivedReceipt received={received} />

  return (
    <div className="mx-auto max-w-[1000px] lg:grid lg:grid-cols-[minmax(0,560px)_340px] lg:justify-center lg:gap-10 lg:px-8 lg:pt-10 lg:pb-20">
      <div className="min-h-[calc(100dvh-4.5rem)] bg-white px-5 pt-5 pb-10 lg:min-h-0 lg:rounded-[28px] lg:px-9 lg:pt-8 lg:pb-10 lg:shadow-lift">
        <AnimatePresence mode="wait" initial={false}>
          {category ? (
            <motion.div key="details" initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 24 }} transition={{ duration: 0.22 }}>
              <Details
                category={category}
                prefilled={params.get('property') ?? ''}
                onBack={() => setCategory('')}
                onReceived={(row) => {
                  setReceived(row)
                  window.scrollTo(0, 0)
                }}
              />
            </motion.div>
          ) : (
            <motion.div key="types" initial={{ opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.22 }}>
              <TypeList onPick={setCategory} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <aside className="hidden lg:block">
        <WhatNext />
      </aside>
    </div>
  )
}

// S5's first screen: a close button, the title and a tappable list.
function TypeList({ onPick }: { onPick: (type: ComplaintType) => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  return (
    <>
      <button type="button" onClick={() => navigate(-1)} aria-label={t('complaint.close')} className="-ml-2 grid size-10 place-items-center rounded-full text-navy hover:bg-paper">
        <CloseIcon className="size-5" />
      </button>
      <h1 className="mt-3 text-[26px] leading-tight font-bold text-navy">{t('complaint.title')}</h1>
      <p className="mt-2 text-[15px] leading-relaxed text-muted">{t('complaint.pickType')}</p>
      <ul className="mt-6">
        {COMPLAINT_TYPES.map((type) => (
          <li key={type} className="border-b border-mist/80 last:border-0">
            <button type="button" onClick={() => onPick(type)} className="group flex w-full items-center justify-between gap-4 py-4 text-left">
              <span className="text-[15px] text-navy">{t(`complaint.types.${type}`)}</span>
              <ChevronRightIcon className="size-5 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

type DetailsProps = { category: ComplaintType; prefilled: string; onBack: () => void; onReceived: (row: Received) => void }

// S5's second screen: back arrow and the chosen type as the title, the
// property row, chips for who you are, then the description, the photo box,
// your contact and one round Send button.
function Details({ category, prefilled, onBack, onReceived }: DetailsProps) {
  const { t, i18n } = useTranslation()
  const [role, setRole] = useState<ComplaintRole | ''>('')
  const [property, setProperty] = useState(prefilled)
  const [editingProperty, setEditingProperty] = useState(!prefilled)
  const [description, setDescription] = useState('')
  const [evidence, setEvidence] = useState<File[]>([])
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function validate(): Errors {
    const next: Errors = {}
    if (!role) next.complainant_role = t('complaint.roleRequired')
    if (!description.trim()) next.description = t('validation.required')
    const problem = firstFileProblem(evidence, EVIDENCE_TYPES)
    if (problem) next.evidence = t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name })
    if (!name.trim()) next.name = t('validation.required')
    if (!looksLikeWhatsApp(phone)) next.phone = t('forms.phoneAny')
    const badEmail = email.trim() ? emailError(t, email) : undefined
    if (badEmail) next.email = badEmail
    return next
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0 || !role) {
      document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
      return
    }
    setSubmitting(true)
    try {
      const row = await servicesApi.lodgeComplaint({
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim() || undefined,
        complainant_role: role,
        category,
        description: description.trim(),
        property_reference: property.trim().toUpperCase() || undefined,
        language: isLanguage(i18n.language) ? i18n.language : 'sw',
        evidence,
      })
      onReceived({ ...row, token: tokenFrom(row.status_link) ?? '', category })
    } catch (error) {
      setSubmitting(false)
      if (error instanceof ApiError && error.status === 404) {
        setEditingProperty(true)
        setErrors({ property_reference: t('complaint.propertyMissing') })
      } else if (error instanceof ApiError && /international WhatsApp/i.test(error.detail ?? '')) setErrors({ phone: t('forms.phoneAny') })
      else if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) setErrors(fieldErrorsFrom(t, error.fieldErrors))
      else setFormError(errorMessage(t, error))
    }
  }

  return (
    <form noValidate onSubmit={(event) => void submit(event)}>
      <button type="button" onClick={onBack} aria-label={t('complaint.backToTypes')} className="-ml-2 grid size-10 place-items-center rounded-full text-navy hover:bg-paper">
        <ArrowLeftIcon className="size-5" />
      </button>
      <h1 className="mt-3 text-[26px] leading-tight font-bold text-navy">{t(`complaint.types.${category}`)}</h1>

      {editingProperty ? (
        <div className="mt-4">
          <Field label={`${t('complaint.property')} ${t('forms.optional')}`} variant="filled" hint={t('complaint.propertyHint')} error={errors.property_reference}>
            {(control) => (
              <input
                {...control}
                autoCapitalize="characters"
                maxLength={50}
                placeholder="OWR-P-000123"
                className={`${control.className} h-12`}
                value={property}
                onChange={(event) => setProperty(event.target.value)}
              />
            )}
          </Field>
        </div>
      ) : (
        <button type="button" onClick={() => setEditingProperty(true)} className="mt-3 flex w-full items-center gap-2.5 py-2 text-left">
          <MapPinIcon className="size-5 shrink-0 text-navy" />
          <span className="flex-1 font-mono text-[15px] text-navy">{property}</span>
          <ChevronRightIcon className="size-5 shrink-0 text-muted" />
        </button>
      )}

      <div className="mt-7">
        <Chips
          label={t('complaint.roleQuestion')}
          variant="light"
          centered
          value={role}
          onChange={(value: ComplaintRole) => {
            setRole(value)
            setErrors((current) => ({ ...current, complainant_role: undefined }))
          }}
          options={COMPLAINT_ROLES.map((value) => ({ value, label: t(`complaint.roles.${value}`) }))}
          error={errors.complainant_role}
        />
      </div>

      <div className="mt-7 space-y-5">
        <Field label={t('complaint.description')} variant="filled" hint={t('complaint.descriptionHint')} error={errors.description}>
          {(control) => (
            <textarea
              {...control}
              rows={5}
              maxLength={10000}
              className={`${control.className} resize-y py-3.5 leading-relaxed`}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          )}
        </Field>

        <PhotoBox
          label={t('complaint.addEvidence')}
          files={evidence}
          onChange={setEvidence}
          accept="image/jpeg,image/png,application/pdf"
          max={5}
          variant="filled"
          error={errors.evidence}
        />

        <p className="pt-2 text-sm font-semibold text-navy">{t('complaint.stepYou')}</p>
        <Field label={t('complaint.name')} variant="filled" error={errors.name}>
          {(control) => <input {...control} autoComplete="name" className={`${control.className} h-12`} value={name} onChange={(event) => setName(event.target.value)} />}
        </Field>
        <Field label={t('complaint.phone')} variant="filled" hint={t('complaint.phoneHint')} error={errors.phone}>
          {(control) => (
            <input
              {...control}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="0712 345 678"
              className={`${control.className} h-12`}
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          )}
        </Field>
        <Field label={`${t('complaint.email')} ${t('forms.optional')}`} variant="filled" error={errors.email}>
          {(control) => (
            <input
              {...control}
              type="email"
              inputMode="email"
              autoComplete="email"
              className={`${control.className} h-12`}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          )}
        </Field>
      </div>

      {formError && (
        <div className="mt-6">
          <Alert tone="error">{formError}</Alert>
        </div>
      )}

      <motion.button
        type="submit"
        whileTap={{ scale: 0.98 }}
        disabled={submitting}
        aria-busy={submitting || undefined}
        className="mt-8 inline-flex h-14 w-full items-center justify-center gap-2 rounded-full bg-gold text-[15px] font-semibold text-navy shadow-[0_10px_24px_-12px_rgba(200,145,40,0.8)] transition-colors hover:bg-gold-light disabled:opacity-70"
      >
        {submitting && <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" />}
        {submitting ? t('complaint.submitting') : t('complaint.send')}
      </motion.button>
    </form>
  )
}

// CMP-03: the number on screen straight away, as an S7 receipt.
function ReceivedReceipt({ received }: { received: Received }) {
  const { t, i18n } = useTranslation()
  const statusPath = `/complaints/${received.id}?${new URLSearchParams({ token: received.token })}`
  return (
    <ReceiptPage>
      <ReceiptBrand />
      <ReceiptCard
        mark="check"
        title={t('complaint.receivedTitle')}
        lead={
          <>
            {t('complaint.receivedLead')} <b className="font-semibold text-navy">{received.reference}</b>.
          </>
        }
      >
        <ReceiptSection title={t('complaint.receivedDetails')}>
          <ReceiptRows>
            <ReceiptRow label={t('complaint.number')} value={<span className="font-mono">{received.reference}</span>} />
            <ReceiptRow label={t('complaint.type')} value={t(`complaint.types.${received.category}`)} />
            <ReceiptRow label={t('complaint.statusLabel')} value={t(`complaint.statuses.${received.status}`)} />
            <ReceiptRow label={t('complaint.target')} value={formatDate(received.resolution_due_at, i18n.language)} />
          </ReceiptRows>
        </ReceiptSection>
        <ReceiptSection>
          <p className="text-center text-[15px] leading-relaxed text-navy/75">
            {t('complaint.receivedBody')}{' '}
            <Link to={statusPath} className="font-medium text-gold underline-offset-4 hover:underline">
              {t('complaint.track')}
            </Link>
          </p>
        </ReceiptSection>
      </ReceiptCard>
      <ReceiptFooter>
        <p>
          {t('complaint.number')}: <b className="font-semibold text-navy/80">{received.reference}</b>
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          <CopyButton value={received.reference} />
          <CopyButton value={`${window.location.origin}${statusPath}`} label={t('forms.copyLink')} />
        </div>
        <p className="text-[13px] text-muted/80">{t('forms.privateLink')}</p>
      </ReceiptFooter>
      <ReceiptSeal />
    </ReceiptPage>
  )
}

function WhatNext() {
  const { t } = useTranslation()
  const steps = t('complaint.asideSteps', { returnObjects: true }) as string[]
  return (
    <Panel title={t('complaint.asideTitle')}>
      <ol className="space-y-4">
        {steps.map((step, index) => (
          <li key={step} className="flex gap-3">
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-navy text-xs font-semibold text-gold-light">{index + 1}</span>
            <span className="pt-0.5 text-sm leading-relaxed text-navy">{step}</span>
          </li>
        ))}
      </ol>
    </Panel>
  )
}
