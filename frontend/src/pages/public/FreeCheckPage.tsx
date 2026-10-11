import { motion } from 'motion/react'
import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { FilesField, SelectField, TextAreaField } from '../../components/FormFields'
import { BuildingIcon, HomeIcon, ImageIcon, LandIcon, MapPinIcon, SearchIcon, ShieldIcon } from '../../components/icons'
import { MapPicker, type LngLat } from '../../components/MapPicker'
import { TextField } from '../../components/TextField'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useReveal } from '../../hooks/useReveal'
import { isLanguage } from '../../i18n'
import { ApiError, idempotencyKey } from '../../lib/api'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { firstFileProblem, looksLikeWhatsApp, PHOTO_TYPES } from '../../lib/files'
import { CATEGORIES, type Category } from '../../lib/marketApi'
import { servicesApi, SIZE_UNITS, tokenFrom, type SizeUnit } from '../../lib/servicesApi'
import { emailError } from '../../lib/validation'
import { FormSection, Panel, ServiceColumns, ServiceHeader, ServicePage } from './services/ServiceUi'

// Mirrors the API's check, so the person hears it before sending (FRC-04:
// reports must never carry coordinates or boundaries).
const GEO_WORDS = /(?:coordinates|boundary|polygon|latitude|longitude|\bpin\b|\bGPS\b)|[-+]?\d{1,3}\.\d+\s*[,; ]\s*[-+]?\d{1,3}\.\d+/i

const CATEGORY_ICONS = { LAND: LandIcon, HOUSE: HomeIcon, COMMERCIAL: BuildingIcon }

type Errors = Partial<Record<'pin' | 'category' | 'size' | 'description' | 'external_url' | 'photos' | 'phone' | 'email', string>>

// FRC-01: map pin, stated description, optional photos and outside link, and
// the person's WhatsApp number. No account needed.
export function FreeCheckPage() {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('freeCheck.title'))
  const navigate = useNavigate()
  const root = useRef<HTMLDivElement>(null)
  useReveal(root)

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

  function validate(): Errors {
    const next: Errors = {}
    if (!pin) next.pin = t('freeCheck.pinRequired')
    if (!category) next.category = t('validation.required')
    if (!(Number(size) > 0)) next.size = t('validation.required')
    if (!description.trim()) next.description = t('validation.required')
    else if (GEO_WORDS.test(description)) next.description = t('freeCheck.descriptionGeo')
    if (externalUrl.trim() && !/^https?:\/\/\S+$/i.test(externalUrl.trim())) next.external_url = t('validation.required')
    const problem = firstFileProblem(photos, PHOTO_TYPES)
    if (problem) next.photos = t(problem.kind === 'size' ? 'forms.fileTooBig' : 'forms.fileType', { name: problem.name })
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
    if (Object.keys(found).length > 0 || !pin || !category) {
      document.querySelector<HTMLElement>('[aria-invalid="true"], [data-invalid="true"]')?.focus()
      return
    }
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
      const token = tokenFrom(created.report_link) ?? ''
      navigate(`/free-check/${created.id}?${new URLSearchParams({ token })}`, { state: { created } })
    } catch (error) {
      setSubmitting(false)
      if (error instanceof ApiError && error.status === 409) {
        setKey(idempotencyKey())
        setFormError(t('freeCheck.conflict'))
        return
      }
      if (error instanceof ApiError && error.status === 429) {
        setFormError(t('freeCheck.dailyLimit'))
        return
      }
      if (error instanceof ApiError) {
        const fields = fieldErrorsFrom(t, error.fieldErrors)
        if (fields.description && /coordinates|boundar/i.test(error.fieldErrors.description?.[0] ?? '')) fields.description = t('freeCheck.descriptionGeo')
        if (/international WhatsApp/i.test(error.detail ?? '')) {
          setErrors({ phone: t('forms.phoneAny') })
          return
        }
        if (Object.keys(fields).length > 0) {
          setErrors(fields)
          return
        }
      }
      setFormError(errorMessage(t, error))
    }
  }

  return (
    <ServicePage>
      <div ref={root}>
        <ServiceHeader kicker={t('freeCheck.kicker')} lead={t('freeCheck.titleLead')} accent={t('freeCheck.titleAccent')} body={t('freeCheck.subtitle')} />

        <ServiceColumns aside={<FreeCheckAside />}>
          <form noValidate onSubmit={(event) => void submit(event)} className="space-y-6">
            <FormSection number={1} title={t('freeCheck.stepLocation')} hint={t('freeCheck.stepLocationHint')}>
              <div data-invalid={errors.pin ? 'true' : undefined} tabIndex={errors.pin ? -1 : undefined} className="outline-none">
                <MapPicker
                  value={pin}
                  onChange={(value) => {
                    setPin(value)
                    setErrors((current) => ({ ...current, pin: undefined }))
                  }}
                  invalid={Boolean(errors.pin)}
                  describedBy={errors.pin ? 'pin-error' : undefined}
                />
              </div>
              {errors.pin ? (
                <p id="pin-error" className="text-sm text-danger">
                  {errors.pin}
                </p>
              ) : (
                pin && (
                  <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="inline-flex items-center gap-2 text-sm font-medium text-success">
                    <MapPinIcon className="size-4" />
                    {t('freeCheck.pinSet')}
                  </motion.p>
                )
              )}
            </FormSection>

            <FormSection number={2} title={t('freeCheck.stepProperty')}>
              <fieldset>
                <legend className="mb-1.5 text-sm font-medium text-navy">{t('freeCheck.category')}</legend>
                <div
                  role="radiogroup"
                  aria-invalid={errors.category ? true : undefined}
                  data-invalid={errors.category ? 'true' : undefined}
                  className="grid grid-cols-3 gap-2"
                >
                  {CATEGORIES.map((value) => {
                    const Icon = CATEGORY_ICONS[value]
                    const selected = category === value
                    return (
                      <label
                        key={value}
                        className={`relative flex cursor-pointer flex-col items-center gap-1.5 rounded-xl px-2 py-3.5 text-center text-[13px] font-semibold transition-colors has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-gold/30 sm:flex-row sm:justify-center sm:gap-2 sm:text-sm ${
                          selected ? 'bg-navy text-white' : 'bg-paper text-navy ring-1 ring-mist hover:ring-navy/30'
                        } ${errors.category && !selected ? 'ring-danger' : ''}`}
                      >
                        <input
                          type="radio"
                          name="category"
                          value={value}
                          checked={selected}
                          onChange={() => {
                            setCategory(value)
                            setErrors((current) => ({ ...current, category: undefined }))
                          }}
                          className="sr-only"
                        />
                        <Icon className={`size-5 ${selected ? 'text-gold-light' : 'text-gold'}`} />
                        {t(`market.category.${value}`)}
                      </label>
                    )
                  })}
                </div>
                {errors.category && <p className="mt-1.5 text-sm text-danger">{errors.category}</p>}
              </fieldset>

              <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3">
                <TextField
                  label={t('freeCheck.size')}
                  inputMode="decimal"
                  value={size}
                  onChange={(event) => setSize(event.target.value.replace(/[^\d.]/g, ''))}
                  error={errors.size}
                />
                <SelectField
                  label={t('freeCheck.unit')}
                  value={unit}
                  onChange={(event) => setUnit(event.target.value as SizeUnit)}
                  options={SIZE_UNITS.map((value) => ({ value, label: t(`freeCheck.units.${value}`) }))}
                />
              </div>

              <TextAreaField
                label={t('freeCheck.description')}
                hint={t('freeCheck.descriptionHint')}
                value={description}
                maxLength={4000}
                onChange={(event) => setDescription(event.target.value)}
                error={errors.description}
              />

              <TextField
                label={`${t('freeCheck.externalUrl')} ${t('forms.optional')}`}
                hint={t('freeCheck.externalUrlHint')}
                type="url"
                inputMode="url"
                placeholder="https://"
                value={externalUrl}
                onChange={(event) => setExternalUrl(event.target.value)}
                error={errors.external_url}
              />
            </FormSection>

            <FormSection number={3} title={`${t('freeCheck.stepPhotos')} ${t('forms.optional')}`} hint={t('freeCheck.photosHint')}>
              <FilesField label={t('freeCheck.stepPhotos')} files={photos} onChange={setPhotos} accept="image/jpeg,image/png" max={5} error={errors.photos} />
            </FormSection>

            <FormSection number={4} title={t('freeCheck.stepContact')}>
              <TextField
                label={t('freeCheck.phone')}
                hint={t('freeCheck.phoneHint')}
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder="0712 345 678"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                error={errors.phone}
              />
              <TextField
                label={`${t('freeCheck.email')} ${t('forms.optional')}`}
                hint={t('freeCheck.emailHint')}
                type="email"
                inputMode="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                error={errors.email}
              />
            </FormSection>

            {formError && <Alert tone="error">{formError}</Alert>}

            <div className="sm:max-w-xs">
              <Button type="submit" loading={submitting} loadingLabel={t('freeCheck.submitting')}>
                <SearchIcon className="size-5" />
                {t('freeCheck.submit')}
              </Button>
            </div>
          </form>
        </ServiceColumns>
      </div>
    </ServicePage>
  )
}

function FreeCheckAside() {
  const { t } = useTranslation()
  const items = [
    { key: 'land', icon: MapPinIcon },
    { key: 'duplicates', icon: SearchIcon },
    { key: 'photos', icon: ImageIcon },
    { key: 'description_match', icon: LandIcon },
  ] as const

  return (
    <>
      <Panel title={t('freeCheck.asideTitle')}>
        <ul className="space-y-4">
          {items.map((item) => (
            <li key={item.key} className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-gold/12 text-gold">
                <item.icon className="size-[18px]" />
              </span>
              <span className="pt-1.5 text-sm leading-relaxed text-navy">{t(`freeCheck.looks.${item.key}`)}</span>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel tone="navy">
        <div className="flex gap-3">
          <ShieldIcon className="mt-0.5 size-5 shrink-0 text-gold-light" />
          <p className="text-sm leading-relaxed text-white/80">{t('freeCheck.limitNote')}</p>
        </div>
      </Panel>
    </>
  )
}
