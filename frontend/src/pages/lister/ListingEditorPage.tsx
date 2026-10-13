import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { ArrowLeftIcon, ArrowRightIcon, CloseIcon, InfoIcon, TickIcon, WhatsAppIcon } from '../../components/icons'
import { MapPicker, type LngLat } from '../../components/MapPicker'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import en from '../../i18n/en'
import sw from '../../i18n/sw'
import { ApiError } from '../../lib/api'
import { whatsappLink } from '../../lib/config'
import { errorMessage, fieldErrorsFrom } from '../../lib/errors'
import { digitsOnly, formatNumber, formatTsh } from '../../lib/format'
import {
  activationBlockers,
  listerApi,
  MINIMUM_PHOTOS,
  type ActivationBlocker,
  type Listing,
  type ListerIdentity,
  type ListerKind,
  type LocalityKind,
  type PropertyRecord,
} from '../../lib/listerApi'
import { CATEGORIES, marketApi, TITLE_TYPES, type Category, type Place, type TitleType } from '../../lib/marketApi'
import { ChoiceTiles, FormSection, Input, Select, TextArea } from './fields'
import { ListingPreview } from './ListingPreview'
import { MediaPanel } from './MediaPanel'
import { FEATURES, withUrls, type Feature, type Photo } from './rows'

type Basics = {
  category: Category | ''
  title_type: TitleType | ''
  size: string
  unit: string
  kind: ListerKind | ''
  price: string
  owner_price: string
  description: string
}

type Where = { region: string; district: string; ward: string; locality: string; locality_kind: LocalityKind; pin: LngLat | null }

const EMPTY_BASICS: Basics = { category: '', title_type: '', size: '', unit: 'sqm', kind: '', price: '', owner_price: '', description: '' }
const EMPTY_WHERE: Where = { region: '', district: '', ward: '', locality: '', locality_kind: 'street', pin: null }
const UNITS = ['sqm', 'acres', 'hectares'] as const
const STEPS = ['basics', 'location', 'media', 'review'] as const

// Either language's label for a feature, so stored labels tick their boxes.
const FEATURE_BY_LABEL = new Map<string, Feature>(
  FEATURES.flatMap((key) => [
    [sw.lister.features[key].toLowerCase(), key],
    [en.lister.features[key].toLowerCase(), key],
  ]),
)

function readFeatures(stored: unknown): { picked: Feature[]; extra: string[] } {
  const labels = Array.isArray(stored) ? stored.filter((item): item is string => typeof item === 'string') : []
  const picked: Feature[] = []
  const extra: string[] = []
  for (const label of labels) {
    const key = FEATURE_BY_LABEL.get(label.trim().toLowerCase())
    if (key) picked.push(key)
    else extra.push(label)
  }
  return { picked, extra }
}

// Server field names to the form's.
const FIELD_NAMES: Record<string, string> = { stated_size: 'size', selling_price: 'price', locality_name: 'locality', size_unit: 'unit' }

// After L3: a back button with the title, a "registration progress" column
// with the step list and a help box, and the form card with "Save as draft"
// and "Next step" in its footer. L1's preview stands on the right on wide
// screens; step 3 is L4's features grid and media card.
export function ListingEditorPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { listingId } = useParams()
  const [search] = useSearchParams()
  const [step, setStep] = useState(() => Math.min(3, Math.max(0, Number(search.get('step') ?? 1) - 1)))
  const [loading, setLoading] = useState(Boolean(listingId))
  const [basics, setBasics] = useState<Basics>(EMPTY_BASICS)
  const [where, setWhere] = useState<Where>(EMPTY_WHERE)
  const [features, setFeatures] = useState<Feature[]>([])
  const [extraFeatures, setExtraFeatures] = useState<string[]>([])
  const [property, setProperty] = useState<PropertyRecord | null>(null)
  const [listing, setListing] = useState<Listing | null>(null)
  const [photos, setPhotos] = useState<Photo[]>([])
  const [identity, setIdentity] = useState<ListerIdentity | null>(null)
  const [regions, setRegions] = useState<Place[]>([])
  const [districts, setDistricts] = useState<Place[]>([])
  const [wards, setWards] = useState<Place[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [blockers, setBlockers] = useState<ActivationBlocker[] | null>(null)
  const [busy, setBusy] = useState<'next' | 'draft' | null>(null)
  useDocumentTitle(listingId ? t('lister.editor.editTitle') : t('lister.editor.title'))

  // An existing listing: fill every step from the server.
  useEffect(() => {
    if (!listingId) return
    let live = true
    Promise.all([listerApi.listing(listingId), listerApi.photos(listingId).then(withUrls)])
      .then(async ([found, gallery]) => {
        const record = await listerApi.property(found.property_id)
        if (!live) return
        const kept = readFeatures(found.features)
        setListing(found)
        setProperty(record)
        setPhotos(gallery)
        setFeatures(kept.picked)
        setExtraFeatures(kept.extra)
        setBasics({
          category: record.category,
          title_type: record.title_type,
          size: record.stated_size ? String(Math.round(Number(record.stated_size))) : '',
          unit: record.size_unit || 'sqm',
          kind: found.lister_kind,
          price: found.selling_price,
          owner_price: found.lister_kind === 'AGENT' ? found.owner_price : '',
          description: found.description,
        })
        setWhere({
          region: record.region,
          district: record.district,
          ward: record.ward,
          locality: record.locality?.name ?? '',
          locality_kind: record.locality?.kind ?? 'street',
          pin: record.pin ? record.pin.coordinates : null,
        })
      })
      .catch((caught) => live && setFormError(errorMessage(t, caught)))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
  }, [listingId, t])

  useEffect(() => {
    listerApi.identity().then(setIdentity, () => setIdentity(null))
    marketApi.regions().then(setRegions, () => setRegions([]))
  }, [])

  useEffect(() => {
    if (!where.region) return
    let live = true
    marketApi.districts(where.region).then((list) => live && setDistricts(list), () => live && setDistricts([]))
    return () => {
      live = false
    }
  }, [where.region])

  useEffect(() => {
    if (!where.district) return
    let live = true
    marketApi.wards(where.district).then((list) => live && setWards(list), () => live && setWards([]))
    return () => {
      live = false
    }
  }, [where.district])

  const place = useMemo(() => {
    const name = (list: Place[], id: string) => list.find((item) => item.id === id)?.name ?? ''
    return { region: name(regions, where.region), district: name(districts, where.district), ward: name(wards, where.ward) }
  }, [regions, districts, wards, where.region, where.district, where.ward])

  function setBasic<K extends keyof Basics>(key: K, value: Basics[K]) {
    setBasics((current) => ({ ...current, [key]: value }))
    setErrors(({ [key]: _gone, ...rest }) => rest)
  }

  function setPlace(change: Partial<Where>) {
    setWhere((current) => ({ ...current, ...change }))
    setErrors((current) => {
      const next = { ...current }
      for (const key of Object.keys(change)) delete next[key]
      return next
    })
  }

  function checkBasics(): Record<string, string> {
    const found: Record<string, string> = {}
    const required = t('validation.required')
    if (!basics.category) found.category = required
    if (!basics.title_type) found.title_type = required
    if (!(Number(basics.size) > 0)) found.size = t('lister.editor.sizeInvalid')
    if (!basics.kind) found.kind = required
    if (!(Number(basics.price) > 0)) found.price = t('lister.editor.priceInvalid')
    if (basics.kind === 'AGENT' && !(Number(basics.owner_price) > 0)) found.owner_price = t('lister.editor.priceInvalid')
    return found
  }

  function checkWhere(): Record<string, string> {
    const found: Record<string, string> = {}
    const required = t('validation.required')
    if (!where.region) found.region = required
    if (!where.district) found.district = required
    if (!where.ward) found.ward = required
    if (!where.pin) found.pin = t('lister.editor.pinMissing')
    return found
  }

  function featureLabels(): string[] {
    return [...extraFeatures, ...features.map((key) => t(`lister.features.${key}`))]
  }

  // Creates the property record and the draft listing, or saves changes to them.
  async function saveRecord(): Promise<Listing> {
    const input = {
      category: basics.category as Category,
      title_type: basics.title_type as TitleType,
      stated_size: basics.size,
      size_unit: basics.unit,
      region: where.region,
      district: where.district,
      ward: where.ward,
      pin: { type: 'Point' as const, coordinates: where.pin as LngLat },
      ...(where.locality.trim() && where.locality.trim() !== property?.locality?.name
        ? { locality_name: where.locality.trim(), locality_kind: where.locality_kind }
        : {}),
    }
    const record = property ? await listerApi.updateProperty(property.property_id, input) : await listerApi.createProperty(input)
    setProperty(record)
    const prices = {
      selling_price: basics.price,
      owner_price: basics.kind === 'AGENT' ? basics.owner_price : basics.price,
      description: basics.description.trim(),
      features: featureLabels(),
    }
    const saved = listing
      ? await listerApi.updateListing(listing.listing_id, prices)
      : await listerApi.createListing(record.property_id, basics.kind as ListerKind, prices)
    setListing(saved)
    return saved
  }

  function showFailure(caught: unknown) {
    if (caught instanceof ApiError && Object.keys(caught.fieldErrors).length > 0) {
      const mapped = fieldErrorsFrom(t, caught.fieldErrors)
      const named: Record<string, string> = {}
      for (const [field, message] of Object.entries(mapped)) named[FIELD_NAMES[field] ?? field] = message
      setErrors(named)
      if (named.category || named.title_type || named.size || named.price || named.owner_price || named.kind) setStep(0)
    }
    setFormError(errorMessage(t, caught))
  }

  async function next(event?: FormEvent) {
    event?.preventDefault()
    setFormError(null)
    if (step === 0) {
      const found = checkBasics()
      setErrors(found)
      if (Object.keys(found).length === 0) setStep(1)
      return
    }
    if (step === 1) {
      const found = { ...checkBasics(), ...checkWhere() }
      setErrors(found)
      if (Object.keys(found).length > 0) {
        if (Object.keys(checkBasics()).length > 0) setStep(0)
        return
      }
      setBusy('next')
      try {
        const saved = await saveRecord()
        setStep(2)
        if (!listingId) navigate(`/lister/listings/${saved.listing_id}?step=3`, { replace: true })
      } catch (caught) {
        showFailure(caught)
      } finally {
        setBusy(null)
      }
      return
    }
    if (step === 2 && listing) {
      setBusy('next')
      try {
        setListing(await listerApi.updateListing(listing.listing_id, { features: featureLabels() }))
        setStep(3)
      } catch (caught) {
        showFailure(caught)
      } finally {
        setBusy(null)
      }
      return
    }
    if (step === 3 && listing) {
      setBusy('next')
      setBlockers(null)
      try {
        await listerApi.activate(listing.listing_id)
        navigate('/lister/listings?status=published', { state: { published: listing.listing_id } })
      } catch (caught) {
        const codes = activationBlockers(caught)
        if (codes) setBlockers(codes)
        else showFailure(caught)
      } finally {
        setBusy(null)
      }
    }
  }

  async function saveDraft() {
    setFormError(null)
    const found = { ...checkBasics(), ...checkWhere() }
    if (!listing && Object.keys(found).length > 0) {
      setErrors(found)
      return
    }
    setBusy('draft')
    try {
      if (step <= 1) await saveRecord()
      else if (listing) await listerApi.updateListing(listing.listing_id, { features: featureLabels() })
      navigate('/lister/listings?status=draft', { state: { saved: true } })
    } catch (caught) {
      showFailure(caught)
    } finally {
      setBusy(null)
    }
  }

  // Steps are open once the step before them is done.
  const reachable = (index: number) => index === 0 || (index === 1 && Object.keys(checkBasics()).length === 0) || (index >= 2 && Boolean(listing))
  const locked = listing !== null && listing.status !== 'DRAFT'
  const title = basics.category ? `${t(`market.category.${basics.category}`)}${where.locality.trim() || place.ward ? `, ${where.locality.trim() || place.ward}` : ''}` : t('lister.untitled')
  const facts = [
    basics.size ? `${formatNumber(basics.size, i18n.language)} ${t(`lister.unitsShort.${basics.unit}`)}` : '',
    basics.title_type ? t(`market.titleType.${basics.title_type}`) : '',
  ].filter(Boolean)
  const address = [where.locality.trim(), place.ward, place.district, place.region].filter(Boolean).join(', ')
  const preview = (
    <ListingPreview
      cover={photos[0]?.url ?? null}
      badge={basics.category ? t(`market.category.${basics.category}`) : null}
      price={basics.price}
      title={title}
      facts={facts}
      address={address}
      createdAt={listing?.created_at ?? null}
      photoCount={photos.length}
      status={listing?.status ?? null}
    />
  )
  const stepKey = STEPS[step]

  return (
    <div>
      {/* L3 heading: a round back button, the title and one line under it. */}
      <div className="mb-8 flex items-start gap-5">
        <Link
          to="/lister/listings"
          aria-label={t('lister.editor.back')}
          className="grid size-12 shrink-0 place-items-center rounded-full border border-mist bg-white text-navy shadow-[0_1px_2px_rgba(15,23,42,0.06)] transition-colors hover:border-navy-soft/40"
        >
          <ArrowLeftIcon className="size-5" />
        </Link>
        <div className="min-w-0 pt-0.5">
          <h1 className="text-[22px] leading-tight font-bold text-navy sm:text-[24px]">{listingId ? t('lister.editor.editTitle') : t('lister.editor.title')}</h1>
          <p className="mt-1.5 text-[14.5px] text-muted">{t('lister.editor.subtitle')}</p>
        </div>
      </div>

      <div className="grid items-start gap-8 lg:grid-cols-[250px_minmax(0,1fr)] min-[85rem]:grid-cols-[250px_minmax(0,1fr)_300px]">
        <aside className="lg:sticky lg:top-24">
          <h2 className="text-[16px] font-semibold text-navy">{t('lister.editor.progress')}</h2>
          <p className="mt-1 text-[13px] text-navy-soft">{t('lister.editor.stepOf', { step: step + 1, total: STEPS.length })}</p>
          <div className="mt-3.5 h-1 overflow-hidden rounded-full bg-mist" aria-hidden="true">
            <motion.div className="h-full rounded-full bg-gold" initial={false} animate={{ width: `${((step + 1) / STEPS.length) * 100}%` }} transition={{ duration: 0.4, ease: 'easeOut' }} />
          </div>
          <p className="mt-3 text-[14px] font-medium text-[#9a6c12] lg:hidden">{t(`lister.editor.steps.${stepKey}.title`)}</p>

          <ol className="mt-7 hidden space-y-2 lg:block">
            {STEPS.map((key, index) => {
              const current = index === step
              const done = index < step
              const open = reachable(index) && !busy
              return (
                <li key={key}>
                  <button
                    type="button"
                    disabled={!open || current}
                    onClick={() => setStep(index)}
                    aria-current={current ? 'step' : undefined}
                    className={`flex w-full items-center gap-3.5 rounded-lg px-3.5 py-3 text-left transition-colors ${
                      current ? 'border border-gold/45 bg-gold/10' : 'border border-transparent enabled:hover:bg-white'
                    } disabled:cursor-default`}
                  >
                    <span
                      className={`grid size-7 shrink-0 place-items-center text-[11px] font-semibold ${
                        current ? 'rounded-full bg-gold text-navy' : done ? 'rounded-full bg-navy text-gold-light' : 'rounded-md bg-mist/70 text-navy-soft'
                      }`}
                    >
                      {done ? <TickIcon className="size-3.5" /> : <span className={current ? 'grid size-3.5 place-items-center rounded-[3px] border border-navy/60 text-[9px]' : ''}>{index + 1}</span>}
                    </span>
                    <span className="min-w-0">
                      <span className={`block text-[14px] ${current ? 'font-semibold text-[#7a5410]' : 'text-navy-soft'}`}>{t(`lister.editor.steps.${key}.title`)}</span>
                      {current && <span className="mt-0.5 block text-[12px] text-[#9a6c12]">{t(`lister.editor.steps.${key}.hint`)}</span>}
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>

          <div className="mt-10 hidden rounded-lg border border-gold/25 bg-[#fdf7ec] px-4 py-4 lg:flex lg:gap-3">
            <InfoIcon className="mt-0.5 size-5 shrink-0 text-[#9a6c12]" />
            <div>
              <p className="text-[14px] font-semibold text-navy">{t('lister.editor.helpTitle')}</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-[#7a5410]">{t('lister.editor.helpBody')}</p>
              <a
                href={whatsappLink(t('lister.editor.helpMessage'))}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-navy underline-offset-2 hover:underline"
              >
                <WhatsAppIcon className="size-3.5" />
                {t('nav.helpAction')}
              </a>
            </div>
          </div>
        </aside>

        <form noValidate onSubmit={next} className="overflow-hidden rounded-2xl border border-mist/80 bg-white shadow-[0_4px_18px_-8px_rgba(15,23,42,0.12)]">
          <div className="border-b border-mist px-5 py-5 sm:px-6">
            <h2 className="text-[19px] font-bold text-navy sm:text-[20px]">{t(`lister.editor.cards.${stepKey}.title`)}</h2>
            <p className="mt-1 text-[14px] text-navy-soft">{t(`lister.editor.cards.${stepKey}.body`)}</p>
          </div>

          <div className="px-5 py-6 sm:px-7">
            {formError && (
              <div className="mb-5">
                <Alert tone="error">{formError}</Alert>
              </div>
            )}
            {loading ? (
              <div className="space-y-5" aria-busy="true">
                {[0, 1, 2].map((row) => (
                  <div key={row} className="h-16 animate-pulse rounded-lg bg-paper" />
                ))}
              </div>
            ) : (
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={stepKey} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.2 }} className="space-y-5">
                  {stepKey === 'basics' && (
                    <>
                      <div className="grid gap-5 sm:grid-cols-2">
                        <Select
                          label={t('lister.editor.category')}
                          required
                          value={basics.category}
                          onChange={(event) => setBasic('category', event.target.value as Category)}
                          placeholder={t('lister.editor.choose')}
                          options={CATEGORIES.map((value) => ({ value, label: t(`market.category.${value}`) }))}
                          error={errors.category}
                        />
                        <Select
                          label={t('lister.editor.titleType')}
                          required
                          value={basics.title_type}
                          onChange={(event) => setBasic('title_type', event.target.value as TitleType)}
                          placeholder={t('lister.editor.choose')}
                          options={TITLE_TYPES.map((value) => ({ value, label: t(`market.titleType.${value}`) }))}
                          error={errors.title_type}
                          hint={t('lister.editor.titleTypeHint')}
                        />
                      </div>
                      <div className="grid gap-5 sm:grid-cols-2">
                        <Input
                          label={t('lister.editor.size')}
                          required
                          inputMode="decimal"
                          placeholder="600"
                          value={basics.size}
                          onChange={(event) => setBasic('size', event.target.value.replace(/[^\d.]/g, ''))}
                          error={errors.size}
                        />
                        <Select
                          label={t('lister.editor.unit')}
                          value={basics.unit}
                          onChange={(event) => setBasic('unit', event.target.value)}
                          options={UNITS.map((value) => ({ value, label: t(`lister.units.${value}`) }))}
                        />
                      </div>
                      <ChoiceTiles<ListerKind>
                        label={t('lister.editor.kind')}
                        value={basics.kind}
                        onChange={(value) => !listing && setBasic('kind', value)}
                        options={(['OWNER', 'AGENT'] as const).map((value) => ({ value, label: t(`lister.kinds.${value}`), hint: t(`lister.editor.kindHint.${value}`) }))}
                        error={errors.kind}
                      />
                      <FormSection title={t('lister.editor.priceSection')}>
                        <Input
                          label={basics.kind === 'AGENT' ? t('lister.editor.sellingPrice') : t('lister.editor.price')}
                          required
                          prefix="TZS"
                          inputMode="numeric"
                          placeholder="250,000,000"
                          value={basics.price ? formatNumber(basics.price, 'en') : ''}
                          onChange={(event) => setBasic('price', digitsOnly(event.target.value))}
                          error={errors.price}
                          hint={basics.price ? formatTsh(basics.price, i18n.language) : t('lister.editor.priceHint')}
                        />
                        {basics.kind === 'AGENT' && (
                          <Input
                            label={t('lister.editor.ownerPrice')}
                            required
                            prefix="TZS"
                            inputMode="numeric"
                            value={basics.owner_price ? formatNumber(basics.owner_price, 'en') : ''}
                            onChange={(event) => setBasic('owner_price', digitsOnly(event.target.value))}
                            error={errors.owner_price}
                            hint={t('lister.editor.ownerPriceHint')}
                          />
                        )}
                        <TextArea
                          label={t('lister.editor.description')}
                          placeholder={t('lister.editor.descriptionPlaceholder')}
                          value={basics.description}
                          onChange={(event) => setBasic('description', event.target.value)}
                          error={errors.description}
                        />
                      </FormSection>
                    </>
                  )}

                  {stepKey === 'location' && (
                    <>
                      <div className="grid gap-5 sm:grid-cols-2">
                        <Select
                          label={t('lister.editor.region')}
                          required
                          value={where.region}
                          onChange={(event) => {
                            setDistricts([])
                            setWards([])
                            setPlace({ region: event.target.value, district: '', ward: '' })
                          }}
                          placeholder={t('lister.editor.choose')}
                          options={regions.map((item) => ({ value: item.id, label: item.name }))}
                          error={errors.region}
                        />
                        <Select
                          label={t('lister.editor.district')}
                          required
                          value={where.district}
                          disabled={!where.region}
                          onChange={(event) => {
                            setWards([])
                            setPlace({ district: event.target.value, ward: '' })
                          }}
                          placeholder={t('lister.editor.choose')}
                          options={districts.map((item) => ({ value: item.id, label: item.name }))}
                          error={errors.district}
                        />
                      </div>
                      <div className="grid gap-5 sm:grid-cols-2">
                        <Select
                          label={t('lister.editor.ward')}
                          required
                          value={where.ward}
                          disabled={!where.district}
                          onChange={(event) => setPlace({ ward: event.target.value })}
                          placeholder={t('lister.editor.choose')}
                          options={wards.map((item) => ({ value: item.id, label: item.name }))}
                          error={errors.ward}
                        />
                        <Input
                          label={t('lister.editor.locality')}
                          placeholder={t('lister.editor.localityPlaceholder')}
                          value={where.locality}
                          onChange={(event) => setPlace({ locality: event.target.value })}
                          error={errors.locality}
                          hint={t('lister.editor.localityHint')}
                        />
                      </div>
                      <fieldset>
                        <legend className="mb-2 block text-[13.5px] font-medium text-navy">{t('lister.editor.localityKind')}</legend>
                        <div className="flex flex-wrap gap-5">
                          {(['street', 'village'] as const).map((kind) => (
                            <label key={kind} className="inline-flex cursor-pointer items-center gap-2 text-[14px] text-navy">
                              <input
                                type="radio"
                                name="locality_kind"
                                checked={where.locality_kind === kind}
                                onChange={() => setPlace({ locality_kind: kind })}
                                className="size-4 accent-[#c89128]"
                              />
                              {t(`lister.editor.localityKinds.${kind}`)}
                            </label>
                          ))}
                        </div>
                      </fieldset>
                      <FormSection title={t('lister.editor.pinSection')}>
                        <p className="-mt-2 text-[13px] text-muted">{t('lister.editor.pinHint')}</p>
                        <MapPicker value={where.pin} onChange={(pin) => setPlace({ pin })} invalid={Boolean(errors.pin)} mapClassName="h-[280px] sm:h-[340px]" />
                        {errors.pin && <p className="text-[12px] text-danger">{errors.pin}</p>}
                      </FormSection>
                    </>
                  )}

                  {stepKey === 'media' && listing && (
                    <>
                      <section>
                        <h3 className="text-[18px] font-medium text-navy">{t('lister.editor.featuresTitle')}</h3>
                        <p className="mt-1 text-[13.5px] text-muted">{t('lister.editor.featuresHint')}</p>
                        <div className="mt-5 grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-3">
                          {FEATURES.map((key) => {
                            const on = features.includes(key)
                            return (
                              <label key={key} className="flex cursor-pointer items-center gap-3 text-[15px] text-navy">
                                <input
                                  type="checkbox"
                                  checked={on}
                                  onChange={() => setFeatures((current) => (on ? current.filter((item) => item !== key) : [...current, key]))}
                                  className="peer sr-only"
                                />
                                <span
                                  aria-hidden="true"
                                  className={`grid size-[22px] shrink-0 place-items-center rounded-[4px] border transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-gold/40 ${
                                    on ? 'border-gold bg-gold text-navy' : 'border-[#cfd5df] bg-white'
                                  }`}
                                >
                                  {on && <TickIcon className="size-3.5" />}
                                </span>
                                {t(`lister.features.${key}`)}
                              </label>
                            )
                          })}
                        </div>
                      </section>
                      <section className="border-t border-mist pt-6">
                        <h3 className="mb-5 text-[18px] font-medium text-navy">{t('lister.editor.mediaTitle')}</h3>
                        <MediaPanel listingId={listing.listing_id} photos={photos} onChange={setPhotos} />
                      </section>
                    </>
                  )}

                  {stepKey === 'review' && listing && (
                    <Review
                      listing={listing}
                      identity={identity}
                      photos={photos.length}
                      blockers={blockers}
                      rows={[
                        [t('lister.editor.category'), title],
                        [t('lister.editor.titleType'), basics.title_type ? t(`market.titleType.${basics.title_type}`) : '-'],
                        [t('lister.editor.size'), facts[0] ?? '-'],
                        [t('lister.editor.kind'), basics.kind ? t(`lister.kinds.${basics.kind}`) : '-'],
                        [t('lister.editor.price'), basics.price ? formatTsh(basics.price, i18n.language) : '-'],
                        [t('lister.editor.address'), address || '-'],
                        [t('lister.editor.featuresTitle'), featureLabels().join(', ') || '-'],
                      ]}
                      preview={<div className="min-[85rem]:hidden">{preview}</div>}
                    />
                  )}
                </motion.div>
              </AnimatePresence>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 bg-[#f3f5f8] px-5 py-4 sm:px-7">
            {step === 0 && !listing ? (
              <Link to="/lister/listings" className="inline-flex h-11 items-center rounded-full border border-[#cfd5df] bg-white px-6 text-[14.5px] text-navy hover:border-navy-soft/40">
                {t('lister.editor.cancel')}
              </Link>
            ) : (
              <button
                type="button"
                onClick={() => void saveDraft()}
                disabled={busy !== null || locked}
                className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-full border border-[#cfd5df] bg-white px-6 text-[14.5px] text-navy hover:border-navy-soft/40 disabled:opacity-60"
              >
                {busy === 'draft' && <span className="size-4 animate-spin rounded-full border-2 border-navy/20 border-t-navy" aria-hidden="true" />}
                {t('lister.editor.saveDraft')}
              </button>
            )}
            <div className="flex items-center gap-2">
              {step > 0 && (
                <button type="button" onClick={() => setStep(step - 1)} disabled={busy !== null} className="h-11 rounded-full px-4 text-[14px] text-navy-soft hover:text-navy">
                  {t('lister.editor.previous')}
                </button>
              )}
              {!(step === 3 && locked) && (
                <button
                  type="submit"
                  disabled={busy !== null || loading}
                  className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-full bg-gold px-6 text-[14.5px] font-semibold text-navy shadow-[0_8px_20px_-10px_rgba(200,145,40,0.8)] transition-colors hover:bg-gold-light disabled:opacity-70"
                >
                  {busy === 'next' && <span className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" aria-hidden="true" />}
                  {step === 3 ? t('lister.editor.publish') : t('lister.editor.next')}
                  {step < 3 && <ArrowRightIcon className="size-4" />}
                </button>
              )}
            </div>
          </div>
        </form>

        <div className="hidden min-[85rem]:sticky min-[85rem]:top-24 min-[85rem]:block">{preview}</div>
      </div>
    </div>
  )
}

function Review({ listing, identity, photos, blockers, rows, preview }: {
  listing: Listing
  identity: ListerIdentity | null
  photos: number
  blockers: ActivationBlocker[] | null
  rows: [string, string][]
  preview: ReactNode
}) {
  const { t } = useTranslation()
  const verified = identity?.status === 'APPROVED'
  // Before trying, only what the page can see; after, the server's answer.
  const checks: { key: ActivationBlocker; ok: boolean | null; action?: ReactNode }[] = [
    {
      key: 'lister_identity_verified',
      ok: blockers ? !blockers.includes('lister_identity_verified') : verified,
      action: <Link to="/lister/identity" className="font-semibold text-navy underline underline-offset-2">{t('lister.review.verifyAction')}</Link>,
    },
    { key: 'listing_required_media', ok: blockers ? !blockers.includes('listing_required_media') : photos >= MINIMUM_PHOTOS },
    {
      key: 'lister_phone_confirmed',
      ok: blockers ? !blockers.includes('lister_phone_confirmed') : identity ? identity.whatsapp_confirmed : null,
      // ACC-T1: offer a new WhatsApp link rather than a dead end.
      action: <NewLinkButton />,
    },
  ]
  if (blockers?.includes('listing_frozen_rate_version')) checks.push({ key: 'listing_frozen_rate_version', ok: false })

  return (
    <div className="space-y-6">
      {listing.status !== 'DRAFT' && (
        <p className="rounded-lg bg-paper px-4 py-3 text-[13.5px] text-navy-soft">{t('lister.review.notDraft', { status: t(`lister.statuses.${listing.status}`) })}</p>
      )}
      <dl className="divide-y divide-mist/80 rounded-lg border border-mist">
        {rows.map(([label, value]) => (
          <div key={label} className="grid gap-1 px-4 py-3 sm:grid-cols-[180px_minmax(0,1fr)] sm:gap-4">
            <dt className="text-[13px] text-muted">{label}</dt>
            <dd className="text-[14px] text-navy">{value}</dd>
          </div>
        ))}
      </dl>
      {listing.status === 'DRAFT' && (
        <section>
          <h3 className="text-[16px] font-semibold text-navy">{t('lister.review.checksTitle')}</h3>
          <p className="mt-1 text-[13px] text-muted">{t('lister.review.checksBody')}</p>
          <ul className="mt-4 space-y-2.5">
            {checks.map(({ key, ok, action }) => (
              <li key={key} className="flex items-start gap-3 rounded-lg border border-mist px-4 py-3">
                <span
                  className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full ${
                    ok === true ? 'bg-success text-white' : ok === false ? 'bg-danger text-white' : 'bg-mist text-navy-soft'
                  }`}
                >
                  {ok === true ? <TickIcon className="size-3" /> : ok === false ? <CloseIcon className="size-3" /> : <InfoIcon className="size-3" />}
                </span>
                <div className="min-w-0 text-[13.5px]">
                  <p className="font-medium text-navy">{t(`lister.review.checks.${key}`)}</p>
                  {ok !== true && (
                    <p className="mt-0.5 text-muted">
                      {t(`lister.review.fixes.${key}`, { min: MINIMUM_PHOTOS })} {action}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
      {preview}
    </div>
  )
}

function NewLinkButton() {
  const { t } = useTranslation()
  const [state, setState] = useState<'idle' | 'busy' | 'sent' | 'failed'>('idle')
  if (state === 'sent') return <span className="font-semibold text-success">{t('lister.review.linkRequested')}</span>
  return (
    <button
      type="button"
      disabled={state === 'busy'}
      onClick={() => {
        setState('busy')
        listerApi.requestWhatsAppLink().then(
          () => setState('sent'),
          () => setState('failed'),
        )
      }}
      className="font-semibold text-navy underline underline-offset-2 disabled:opacity-60"
    >
      {state === 'failed' ? t('lister.review.linkFailed') : t('lister.review.linkAction')}
    </button>
  )
}
