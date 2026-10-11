import { motion } from 'motion/react'
import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { FilesField, SelectField, TextAreaField } from '../../components/FormFields'
import { ArrowRightIcon, CheckIcon } from '../../components/icons'
import { TextField } from '../../components/TextField'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useReveal } from '../../hooks/useReveal'
import { isLanguage } from '../../i18n'
import { ApiError } from '../../lib/api'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { EVIDENCE_TYPES, firstFileProblem, looksLikeWhatsApp } from '../../lib/files'
import { COMPLAINT_ROLES, COMPLAINT_TYPES, servicesApi, tokenFrom, type ComplaintRole, type ComplaintType } from '../../lib/servicesApi'
import { emailError } from '../../lib/validation'
import { CopyButton, FormSection, Panel, ServiceColumns, ServiceHeader, ServicePage } from './services/ServiceUi'

type Errors = Partial<Record<'name' | 'phone' | 'email' | 'complainant_role' | 'category' | 'property_reference' | 'description' | 'evidence', string>>

type Received = { id: string; reference: string; token: string }

function isType(value: string | null): value is ComplaintType {
  return COMPLAINT_TYPES.includes(value as ComplaintType)
}

// CMP-01: no sign-in. A property page links here with ?property= (and
// optionally ?type=) so the reference is filled in.
export function ComplaintPage() {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('complaint.title'))
  const [params] = useSearchParams()
  const prefilled = params.get('property') ?? ''
  const root = useRef<HTMLDivElement>(null)

  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<ComplaintRole | ''>('')
  const [category, setCategory] = useState<ComplaintType | ''>(() => (isType(params.get('type')) ? (params.get('type') as ComplaintType) : ''))
  const [property, setProperty] = useState(prefilled)
  const [description, setDescription] = useState('')
  const [evidence, setEvidence] = useState<File[]>([])
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [received, setReceived] = useState<Received | null>(null)
  useReveal(root, [received])

  function validate(): Errors {
    const next: Errors = {}
    if (!name.trim()) next.name = t('validation.required')
    if (!looksLikeWhatsApp(phone)) next.phone = t('forms.phoneAny')
    const badEmail = email.trim() ? emailError(t, email) : undefined
    if (badEmail) next.email = badEmail
    if (!role) next.complainant_role = t('validation.required')
    if (!category) next.category = t('validation.required')
    if (!description.trim()) next.description = t('validation.required')
    const problem = firstFileProblem(evidence, EVIDENCE_TYPES)
    if (problem) next.evidence = t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name })
    return next
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0 || !role || !category) {
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
      setReceived({ id: row.id, reference: row.reference, token: tokenFrom(row.status_link) ?? '' })
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) setErrors({ property_reference: t('complaint.propertyMissing') })
      else if (error instanceof ApiError && /international WhatsApp/i.test(error.detail ?? '')) setErrors({ phone: t('forms.phoneAny') })
      else if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) setErrors(fieldErrorsFrom(t, error.fieldErrors))
      else setFormError(errorMessage(t, error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <ServicePage>
      <div ref={root}>
        <ServiceHeader kicker={t('complaint.kicker')} lead={t('complaint.titleLead')} accent={t('complaint.titleAccent')} body={t('complaint.subtitle')} />

        <ServiceColumns aside={<WhatNext />}>
          {received ? (
            <ReceivedCard received={received} />
          ) : (
            <form noValidate onSubmit={(event) => void submit(event)} className="space-y-6">
              <FormSection number={1} title={t('complaint.stepYou')}>
                <TextField label={t('complaint.name')} autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} error={errors.name} />
                <div className="grid gap-5 sm:grid-cols-2">
                  <TextField
                    label={t('complaint.phone')}
                    hint={t('complaint.phoneHint')}
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    placeholder="0712 345 678"
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                    error={errors.phone}
                  />
                  <TextField
                    label={`${t('complaint.email')} ${t('forms.optional')}`}
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    error={errors.email}
                  />
                </div>
                <SelectField
                  label={t('complaint.role')}
                  placeholder={t('complaint.choose')}
                  value={role}
                  onChange={(event) => setRole(event.target.value as ComplaintRole)}
                  options={COMPLAINT_ROLES.map((value) => ({ value, label: t(`complaint.roles.${value}`) }))}
                  error={errors.complainant_role}
                />
              </FormSection>

              <FormSection number={2} title={t('complaint.stepWhat')}>
                <SelectField
                  label={t('complaint.type')}
                  placeholder={t('complaint.choose')}
                  value={category}
                  onChange={(event) => setCategory(event.target.value as ComplaintType)}
                  options={COMPLAINT_TYPES.map((value) => ({ value, label: t(`complaint.types.${value}`) }))}
                  error={errors.category}
                />
                <TextField
                  label={`${t('complaint.property')} ${t('forms.optional')}`}
                  hint={prefilled && property === prefilled ? t('complaint.propertyPrefilled') : t('complaint.propertyHint')}
                  autoCapitalize="characters"
                  maxLength={50}
                  value={property}
                  onChange={(event) => setProperty(event.target.value)}
                  error={errors.property_reference}
                />
                <TextAreaField
                  label={t('complaint.description')}
                  hint={t('complaint.descriptionHint')}
                  rows={6}
                  maxLength={10000}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  error={errors.description}
                />
              </FormSection>

              <FormSection number={3} title={`${t('complaint.stepEvidence')} ${t('forms.optional')}`} hint={t('complaint.evidenceHint')}>
                <FilesField
                  label={t('complaint.stepEvidence')}
                  files={evidence}
                  onChange={setEvidence}
                  accept="image/jpeg,image/png,application/pdf"
                  max={5}
                  error={errors.evidence}
                />
              </FormSection>

              {formError && <Alert tone="error">{formError}</Alert>}

              <div className="sm:max-w-xs">
                <Button type="submit" loading={submitting} loadingLabel={t('complaint.submitting')}>
                  {t('complaint.submit')}
                </Button>
              </div>
            </form>
          )}
        </ServiceColumns>
      </div>
    </ServicePage>
  )
}

// CMP-03: the number on screen straight away, with the private status link.
function ReceivedCard({ received }: { received: Received }) {
  const { t } = useTranslation()
  const statusPath = `/complaints/${received.id}?${new URLSearchParams({ token: received.token })}`

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: 'easeOut' }}
      aria-live="polite"
      className="rounded-2xl bg-white p-6 shadow-card sm:rounded-md sm:p-8"
    >
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 420, damping: 22, delay: 0.15 }}
        className="grid size-12 place-items-center rounded-full bg-success-soft text-success"
      >
        <CheckIcon className="size-6" />
      </motion.span>
      <p className="mt-5 text-xs font-semibold tracking-[0.2em] text-gold uppercase">{t('complaint.receivedKicker')}</p>
      <h2 className="mt-2 font-serif text-2xl font-semibold text-navy">{t('complaint.receivedTitle')}</h2>
      <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-paper px-4 py-3">
        <span className="font-mono text-lg font-semibold tracking-wide break-all text-navy sm:text-xl">{received.reference}</span>
        <CopyButton value={received.reference} />
      </div>
      <p className="mt-4 text-[15px] leading-relaxed text-muted">{t('complaint.receivedBody')}</p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Link
          to={statusPath}
          className="group inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-navy px-6 text-sm font-semibold text-white transition-colors hover:bg-navy-soft"
        >
          {t('complaint.track')}
          <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
        <CopyButton value={`${window.location.origin}${statusPath}`} label={t('forms.copyLink')} />
      </div>
      <p className="mt-4 text-xs leading-relaxed text-muted">{t('forms.privateLink')}</p>
    </motion.section>
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
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-navy font-serif text-xs font-semibold text-gold-light">{index + 1}</span>
            <span className="pt-0.5 text-sm leading-relaxed text-navy">{step}</span>
          </li>
        ))}
      </ol>
    </Panel>
  )
}
