import { AnimatePresence, motion } from 'motion/react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { ArrowLeftIcon, CameraIcon, CheckIcon, CloseIcon, DocumentIcon, MapPinIcon, ShieldIcon, WhatsAppIcon } from '../../components/icons'
import { MapPicker, type LngLat } from '../../components/MapPicker'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { isLanguage } from '../../i18n'
import { ApiError, idempotencyKey } from '../../lib/api'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { firstFileProblem, looksLikeWhatsApp, PHOTO_TYPES } from '../../lib/files'
import { CATEGORIES, type Category } from '../../lib/marketApi'
import { servicesApi, SIZE_UNITS, tokenFrom, type SizeUnit } from '../../lib/servicesApi'
import { DESKTOP, useMediaQuery } from '../../lib/useMediaQuery'
import { emailError } from '../../lib/validation'
import { Chips, Field, PhotoBox, type Variant } from './services/fields'

// Mirrors the API's check, so the person hears it before sending (FRC-04:
// reports must never carry coordinates or boundaries).
const GEO_WORDS = /(?:coordinates|boundary|polygon|latitude|longitude|\bpin\b|\bGPS\b)|[-+]?\d{1,3}\.\d+\s*[,; ]\s*[-+]?\d{1,3}\.\d+/i

type FieldName = 'pin' | 'category' | 'size' | 'description' | 'external_url' | 'photos' | 'phone' | 'email'
type Errors = Partial<Record<FieldName, string>>

// Which fields each desktop step asks for. Phones ask the map first, then
// everything else in one sheet.
const DESKTOP_STEPS: FieldName[][] = [['pin'], ['category', 'size', 'description', 'external_url'], ['photos'], ['phone', 'email']]
const PHONE_STEPS: FieldName[][] = [['pin'], ['category', 'size', 'description', 'external_url', 'photos', 'phone', 'email']]

// FRC-01 without an account. Desktop follows the S3 step form, phones the S2
// map-then-sheet flow.
export function FreeCheckPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('freeCheck.title'))
  const desktop = useMediaQuery(DESKTOP)
  const form = useFreeCheckForm()
  return desktop ? <StepForm form={form} /> : <PhoneFlow form={form} />
}

type Form = ReturnType<typeof useFreeCheckForm>

function useFreeCheckForm() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [pin, setPin] = useState<LngLat | null>(null)
  const [category, setCategory] = useState<Category | ''>('')
  const [size, setSize] = useState('')
  const [unit, setUnit] = useState<SizeUnit>('sqm')
  const [description, setDescription] = useState('')
  const [externalUrl, setExternalUrl] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  // One key per check, so a retry after a dropped connection returns the same report.
  const [key, setKey] = useState(idempotencyKey)

  function check(fields: FieldName[]): Errors {
    const all: Errors = {}
    if (!pin) all.pin = t('freeCheck.pinRequired')
    if (!category) all.category = t('validation.required')
    if (!(Number(size) > 0)) all.size = t('validation.required')
    if (!description.trim()) all.description = t('validation.required')
    else if (GEO_WORDS.test(description)) all.description = t('freeCheck.descriptionGeo')
    if (externalUrl.trim() && !/^https?:\/\/\S+$/i.test(externalUrl.trim())) all.external_url = t('freeCheck.urlInvalid')
    const problem = firstFileProblem(photos, PHOTO_TYPES)
    if (problem) all.photos = t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name })
    if (!looksLikeWhatsApp(phone)) all.phone = t('forms.phoneAny')
    const badEmail = email.trim() ? emailError(t, email) : undefined
    if (badEmail) all.email = badEmail
    const found: Errors = {}
    for (const field of fields) if (all[field]) found[field] = all[field]
    return found
  }

  // True when these fields are fine; otherwise shows their errors.
  function passes(fields: FieldName[]): boolean {
    const found = check(fields)
    setErrors(found)
    return Object.keys(found).length === 0
  }

  function clear(field: FieldName) {
    setErrors((current) => ({ ...current, [field]: undefined }))
  }

  async function submit(): Promise<Errors | null> {
    setFormError(null)
    const found = check(DESKTOP_STEPS.flat())
    setErrors(found)
    if (Object.keys(found).length > 0 || !pin || !category) return found
    setSubmitting(true)
    try {
      const created = await servicesApi.submitFreeCheck(
        {
          pin: { type: 'Point', coordinates: pin },
          category,
          size,
          size_unit: unit,
          description: description.trim(),
          phone: phone.trim(),
          email: email.trim() || undefined,
          external_url: externalUrl.trim() || undefined,
          language: isLanguage(i18n.language) ? i18n.language : 'sw',
          photos,
        },
        key,
      )
      navigate(`/free-check/${created.id}?${new URLSearchParams({ token: tokenFrom(created.report_link) ?? '' })}`, { state: { created } })
      return null
    } catch (error) {
      setSubmitting(false)
      if (error instanceof ApiError && error.status === 409) {
        setKey(idempotencyKey())
        setFormError(t('freeCheck.conflict'))
      } else if (error instanceof ApiError && error.status === 429) setFormError(t('freeCheck.dailyLimit'))
      else if (error instanceof ApiError && /international WhatsApp/i.test(error.detail ?? '')) {
        const next = { phone: t('forms.phoneAny') }
        setErrors(next)
        return next
      } else if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
        const next: Errors = fieldErrorsFrom(t, error.fieldErrors)
        if (next.description && /coordinates|boundar/i.test(error.fieldErrors.description?.[0] ?? '')) next.description = t('freeCheck.descriptionGeo')
        setErrors(next)
        return next
      } else setFormError(errorMessage(t, error))
      return null
    }
  }

  return {
    values: { pin, category, size, unit, description, externalUrl, photos, phone, email },
    set: { setPin, setCategory, setSize, setUnit, setDescription, setExternalUrl, setPhotos, setPhone, setEmail },
    errors,
    formError,
    submitting,
    passes,
    clear,
    submit,
  }
}

// The property, photo and contact fields, drawn in one of the field styles.
function DetailFields({ form, variant, fields }: { form: Form; variant: Variant; fields: FieldName[] }) {
  const { t } = useTranslation()
  const { values, set, errors, clear } = form
  const dark = variant === 'dark'
  const show = (name: FieldName) => fields.includes(name)
  const tall = variant === 'line' ? 'py-2' : 'h-12'

  return (
    <div className={variant === 'line' ? 'space-y-6' : 'space-y-5'}>
      {show('category') && (
        <Chips
          label={t('freeCheck.category')}
          variant={dark ? 'dark' : 'tag'}
          value={values.category}
          onChange={(value: Category) => {
            set.setCategory(value)
            clear('category')
          }}
          options={CATEGORIES.map((value) => ({ value, label: t(`market.category.${value}`) }))}
          error={errors.category}
        />
      )}
      {show('size') && (
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4">
          <Field label={t('freeCheck.size')} variant={variant} error={errors.size}>
            {(control) => (
              <input
                {...control}
                inputMode="decimal"
                className={`${control.className} ${tall}`}
                value={values.size}
                onChange={(event) => set.setSize(event.target.value.replace(/[^\d.]/g, ''))}
              />
            )}
          </Field>
          <Field label={t('freeCheck.unit')} variant={variant}>
            {(control) => (
              <select {...control} className={`${control.className} ${tall}`} value={values.unit} onChange={(event) => set.setUnit(event.target.value as SizeUnit)}>
                {SIZE_UNITS.map((value) => (
                  <option key={value} value={value}>
                    {t(`freeCheck.units.${value}`)}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
      )}
      {show('description') && (
        <Field label={t('freeCheck.description')} variant={variant} hint={t('freeCheck.descriptionHint')} error={errors.description}>
          {(control) => (
            <textarea
              {...control}
              rows={variant === 'line' ? 2 : 4}
              maxLength={4000}
              className={`${control.className} resize-y ${variant === 'line' ? 'py-2' : 'py-3'} leading-relaxed`}
              value={values.description}
              onChange={(event) => set.setDescription(event.target.value)}
            />
          )}
        </Field>
      )}
      {show('external_url') && (
        <Field label={`${t('freeCheck.externalUrl')} ${t('forms.optional')}`} variant={variant} hint={t('freeCheck.externalUrlHint')} error={errors.external_url}>
          {(control) => (
            <input
              {...control}
              type="url"
              inputMode="url"
              placeholder="https://"
              className={`${control.className} ${tall}`}
              value={values.externalUrl}
              onChange={(event) => set.setExternalUrl(event.target.value)}
            />
          )}
        </Field>
      )}
      {show('photos') && (
        <PhotoBox
          label={t('freeCheck.addPhotos')}
          files={values.photos}
          onChange={(files) => {
            set.setPhotos(files)
            clear('photos')
          }}
          accept="image/jpeg,image/png"
          max={5}
          variant={dark ? 'dark' : 'filled'}
          error={errors.photos}
        />
      )}
      {show('phone') && (
        <Field label={t('freeCheck.phone')} variant={variant} hint={t('freeCheck.phoneHint')} error={errors.phone}>
          {(control) => (
            <input
              {...control}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="0712 345 678"
              className={`${control.className} ${tall}`}
              value={values.phone}
              onChange={(event) => set.setPhone(event.target.value)}
            />
          )}
        </Field>
      )}
      {show('email') && (
        <Field label={`${t('freeCheck.email')} ${t('forms.optional')}`} variant={variant} hint={t('freeCheck.emailHint')} error={errors.email}>
          {(control) => (
            <input
              {...control}
              type="email"
              inputMode="email"
              autoComplete="email"
              className={`${control.className} ${tall}`}
              value={values.email}
              onChange={(event) => set.setEmail(event.target.value)}
            />
          )}
        </Field>
      )}
    </div>
  )
}

const STEP_ICONS = [MapPinIcon, DocumentIcon, CameraIcon, WhatsAppIcon]

// Desktop, after S3: one navy card with the title over a rule, the steps
// listed down the left with icon circles, a thin line with a dot per step,
// and the current step on the right with "Step n/4" and a round Next button.
function StepForm({ form }: { form: Form }) {
  const { t } = useTranslation()
  const [step, setStep] = useState(0)
  const steps = (['location', 'property', 'photos', 'contact'] as const).map((name, index) => ({
    title: t(`freeCheck.steps.${name}.title`),
    hint: t(`freeCheck.steps.${name}.hint`),
    lead: t(`freeCheck.steps.${name}.lead`),
    body: t(`freeCheck.steps.${name}.body`),
    icon: STEP_ICONS[index],
  }))
  const last = steps.length - 1

  async function next(event: FormEvent) {
    event.preventDefault()
    if (step < last) {
      if (form.passes(DESKTOP_STEPS[step])) setStep(step + 1)
      return
    }
    const found = await form.submit()
    // Send the person back to the first step with a problem.
    const back = found ? DESKTOP_STEPS.findIndex((fields) => fields.some((field) => found[field])) : -1
    if (back >= 0 && back !== step) setStep(back)
  }

  const current = steps[step]
  return (
    <div className="mx-auto max-w-[1100px] px-8 pt-10 pb-20">
      <form noValidate onSubmit={(event) => void next(event)} className="rounded-[28px] bg-navy px-16 py-14 text-white shadow-lift">
        <div className="mx-auto max-w-[880px]">
          <h1 className="text-[26px] font-bold">{t('freeCheck.title')}</h1>
          <p className="mt-2 text-[13px] text-white/60">{t('freeCheck.stepsIntro', { count: steps.length })}</p>
          <div className="mt-8 border-t border-white/10" />

          <div className="grid grid-cols-[230px_44px_minmax(0,1fr)]">
            <ol className="relative space-y-9 pt-9 pb-12">
              {steps.map((item, index) => {
                const here = index === step
                const done = index < step
                return (
                  <li key={item.title} className="relative flex items-center justify-end gap-4 text-right">
                    {index < last && <span aria-hidden="true" className="absolute top-1/2 right-[19px] h-[calc(100%+2.25rem)] w-px bg-white/15" />}
                    <button
                      type="button"
                      disabled={!done}
                      onClick={() => setStep(index)}
                      aria-current={here ? 'step' : undefined}
                      className="min-w-0 text-right disabled:cursor-default"
                    >
                      <span className={`block text-[13px] font-semibold ${here ? 'text-white' : 'text-white/60'}`}>{item.title}</span>
                      <span className="mt-0.5 block text-[11px] text-white/45">{item.hint}</span>
                    </button>
                    <span
                      className={`relative grid size-10 shrink-0 place-items-center rounded-full ${
                        here ? 'bg-gold text-navy' : done ? 'bg-gold/25 text-gold-light' : 'bg-white/[0.12] text-white/80'
                      }`}
                    >
                      {done ? <CheckIcon className="size-5" /> : <item.icon className="size-[18px]" />}
                    </span>
                  </li>
                )
              })}
            </ol>

            {/* The divider with one dot per step, level with the steps. */}
            <div aria-hidden="true" className="relative flex justify-center">
              <span className="absolute inset-y-0 w-px bg-white/10" />
              <ol className="relative space-y-9 pt-9">
                {steps.map((item, index) => (
                  <li key={item.title} className="flex h-10 items-center">
                    <span
                      className={`size-2.5 rounded-full ${index === step ? 'bg-gold ring-4 ring-gold/25' : index < step ? 'bg-gold/60' : 'bg-navy ring-1 ring-white/35'}`}
                    />
                  </li>
                ))}
              </ol>
            </div>

            <div className="min-w-0 pt-9 pb-4 pl-4">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.25 }}>
                  <p className="text-xs text-white/60">{t('freeCheck.stepOf', { step: step + 1, total: steps.length })}</p>
                  <h2 className="mt-2 text-[24px] leading-tight font-bold">{current.lead}</h2>
                  <p className="mt-2 text-[13px] leading-relaxed text-white/60">{current.body}</p>
                  <div className="my-6 border-t border-white/10" />

                  {step === 0 ? (
                    <div>
                      <MapPicker
                        tone="dark"
                        value={form.values.pin}
                        onChange={(value) => {
                          form.set.setPin(value)
                          form.clear('pin')
                        }}
                        invalid={Boolean(form.errors.pin)}
                        mapClassName="h-[320px]"
                      />
                      {form.errors.pin ? (
                        <p className="mt-2 text-sm text-[#ffb3a6]">{form.errors.pin}</p>
                      ) : (
                        form.values.pin && (
                          <p className="mt-3 inline-flex items-center gap-2 text-sm text-gold-light">
                            <CheckIcon className="size-4" />
                            {t('freeCheck.pinSet')}
                          </p>
                        )
                      )}
                    </div>
                  ) : (
                    <DetailFields form={form} variant="dark" fields={DESKTOP_STEPS[step]} />
                  )}
                </motion.div>
              </AnimatePresence>

              {form.formError && (
                <div className="mt-6">
                  <Alert tone="error">{form.formError}</Alert>
                </div>
              )}

              <div className="mt-7 flex items-center justify-between">
                {step > 0 ? (
                  <button type="button" onClick={() => setStep(step - 1)} className="inline-flex h-12 items-center gap-2 text-sm font-medium text-white/70 hover:text-white">
                    <ArrowLeftIcon className="size-4" />
                    {t('freeCheck.previous')}
                  </button>
                ) : (
                  <span />
                )}
                <motion.button
                  type="submit"
                  whileTap={{ scale: 0.97 }}
                  disabled={form.submitting}
                  aria-busy={form.submitting || undefined}
                  className="inline-flex h-12 min-w-[150px] items-center justify-center gap-2 rounded-full bg-gold px-8 text-sm font-semibold text-navy transition-colors hover:bg-gold-light disabled:opacity-70"
                >
                  {form.submitting && <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" />}
                  {step < last ? t('freeCheck.next') : form.submitting ? t('freeCheck.submitting') : t('freeCheck.submit')}
                </motion.button>
              </div>
            </div>
          </div>
        </div>
      </form>
      <p className="mx-auto mt-6 flex max-w-[880px] items-start gap-2.5 text-sm leading-relaxed text-muted">
        <ShieldIcon className="mt-0.5 size-4 shrink-0 text-gold" />
        {t('freeCheck.limitNote')}
      </p>
    </div>
  )
}

// Phones, after S2: the map fills the screen with a "Select the location"
// sheet; confirming opens the details sheet under a strip of the map.
function PhoneFlow({ form }: { form: Form }) {
  const { t } = useTranslation()
  const [step, setStep] = useState<0 | 1>(0)
  const [locating, setLocating] = useState(false)
  const [locateError, setLocateError] = useState(false)

  function locate() {
    if (!('geolocation' in navigator)) {
      setLocateError(true)
      return
    }
    setLocating(true)
    setLocateError(false)
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocating(false)
        form.set.setPin([coords.longitude, coords.latitude])
        form.clear('pin')
      },
      () => {
        setLocating(false)
        setLocateError(true)
      },
      { enableHighAccuracy: true, timeout: 15000 },
    )
  }

  async function send(event: FormEvent) {
    event.preventDefault()
    if (!form.passes(PHONE_STEPS[1])) {
      document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
      return
    }
    const found = await form.submit()
    if (found?.pin) setStep(0)
  }

  const pinMap = (className: string) => (
    <MapPicker
      bare
      value={form.values.pin}
      onChange={(value) => {
        form.set.setPin(value)
        form.clear('pin')
      }}
      mapClassName={className}
    />
  )

  if (step === 0) {
    return (
      <div className="relative">
        {pinMap('h-[calc(100dvh-4.5rem)]')}
        <Sheet>
          <h1 className="text-lg font-semibold text-navy">{t('freeCheck.selectLocation')}</h1>
          <p className="mt-3 text-[11px] tracking-[0.04em] text-muted uppercase">{t('freeCheck.yourLocation')}</p>
          <div className="mt-1.5 flex items-center gap-2 border-b border-mist pb-3">
            {form.values.pin ? <CheckIcon className="size-[18px] shrink-0 text-success" /> : <MapPinIcon className="size-[18px] shrink-0 text-muted" />}
            <span className={`min-w-0 flex-1 truncate text-sm ${form.values.pin ? 'text-navy' : 'text-muted'}`}>
              {form.values.pin ? t('freeCheck.pinSet') : t('freeCheck.mapHint')}
            </span>
            <button type="button" onClick={locate} disabled={locating} className="shrink-0 text-sm font-semibold text-gold disabled:opacity-60">
              {locating ? t('freeCheck.locating') : t('freeCheck.useLocationShort')}
            </button>
          </div>
          {(locateError || form.errors.pin) && <p className="mt-2 text-sm text-danger">{locateError ? t('freeCheck.locateFailed') : form.errors.pin}</p>}
          <button
            type="button"
            onClick={() => {
              if (form.passes(PHONE_STEPS[0])) setStep(1)
            }}
            className="mt-4 h-12 w-full rounded-lg bg-gold text-sm font-semibold text-navy transition-colors active:bg-gold-light"
          >
            {t('freeCheck.confirmLocation')}
          </button>
        </Sheet>
      </div>
    )
  }

  return (
    <form noValidate onSubmit={(event) => void send(event)}>
      {pinMap('h-[34dvh]')}
      <div className="relative z-[500] -mt-6 rounded-t-[24px] bg-white px-5 pt-5 pb-8 shadow-[0_-10px_30px_-18px_rgba(15,23,42,0.45)]">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-navy">{t('freeCheck.detailsTitle')}</h1>
          <button type="button" onClick={() => setStep(0)} aria-label={t('freeCheck.backToMap')} className="grid size-10 place-items-center rounded-full text-muted hover:bg-paper">
            <CloseIcon className="size-5" />
          </button>
        </div>
        <p className="mt-3 text-[11px] tracking-[0.04em] text-muted uppercase">{t('freeCheck.yourLocation')}</p>
        <div className="mt-1.5 mb-6 flex items-center gap-2 border-b border-mist pb-3">
          <CheckIcon className="size-[18px] shrink-0 text-success" />
          <span className="min-w-0 flex-1 truncate text-sm text-navy">{t('freeCheck.pinSet')}</span>
          <button type="button" onClick={() => setStep(0)} className="shrink-0 text-sm font-semibold text-gold">
            {t('freeCheck.change')}
          </button>
        </div>

        <DetailFields form={form} variant="line" fields={PHONE_STEPS[1]} />

        {form.formError && (
          <div className="mt-6">
            <Alert tone="error">{form.formError}</Alert>
          </div>
        )}
        <button
          type="submit"
          disabled={form.submitting}
          aria-busy={form.submitting || undefined}
          className="mt-7 inline-flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-gold text-sm font-semibold text-navy transition-colors active:bg-gold-light disabled:opacity-70"
        >
          {form.submitting && <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" />}
          {form.submitting ? t('freeCheck.submitting') : t('freeCheck.submit')}
        </button>
        <p className="mt-5 flex items-start gap-2 text-xs leading-relaxed text-muted">
          <ShieldIcon className="mt-0.5 size-4 shrink-0 text-gold" />
          {t('freeCheck.limitNote')}
        </p>
      </div>
    </form>
  )
}

function Sheet({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ y: 40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 380, damping: 34 }}
      className="absolute inset-x-0 bottom-0 z-[500] rounded-t-[24px] bg-white px-5 pt-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] shadow-[0_-10px_30px_-18px_rgba(15,23,42,0.45)]"
    >
      {children}
    </motion.div>
  )
}
