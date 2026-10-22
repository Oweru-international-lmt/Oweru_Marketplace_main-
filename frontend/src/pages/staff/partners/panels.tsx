import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../../components/Alert'
import { CheckIcon, ImageIcon, SendIcon, WhatsAppIcon } from '../../../components/icons'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'
import { marketApi, type Place } from '../../../lib/marketApi'
import { partnersApi, type Invite, type Official, type ProfessionalRow } from '../../../lib/partnersApi'
import type { ProfessionalType } from '../../../lib/tasksApi'
import { CopyValue, DetailRow } from '../../deals/ui'
import { Field, fieldClass, Initials, LocalityPicker, PartnerChip } from './ui'

const primary = 'inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-gold text-[14px] font-semibold text-navy transition-colors hover:bg-[#d39d34] disabled:opacity-50'
const secondary = 'inline-flex h-11 w-full items-center justify-center gap-2 rounded-full border border-mist text-[14px] font-medium text-navy hover:border-navy-soft/40'
const danger = 'inline-flex h-11 w-full items-center justify-center gap-2 rounded-full border border-danger/30 text-[14px] font-medium text-danger hover:bg-danger-soft disabled:opacity-50'

function placeText(place: Official['locality']) {
  return place ? `${place.name}, ${place.ward}, ${place.district}, ${place.region}` : ''
}

// The link is ready: staff open their own WhatsApp to send it (SRD 14.2 step 3).
export function Delivery({ invite }: { invite: Invite }) {
  const { t, i18n } = useTranslation()
  if (!invite.delivery) return null
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl bg-navy p-5 text-white">
      <p className="flex items-center gap-2 text-[15px] font-semibold">
        <span className="grid size-7 place-items-center rounded-full bg-gold text-navy">
          <CheckIcon className="size-4" />
        </span>
        {t('partners.invite.ready')}
      </p>
      <p className="mt-2 text-[13px] text-white/70">{t('partners.invite.readyBody', { phone: invite.phone, date: formatShortDate(invite.expires_at, i18n.language) })}</p>
      <a href={invite.delivery.whatsapp_link} target="_blank" rel="noreferrer" className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-[#25d366] text-[14px] font-semibold text-white">
        <WhatsAppIcon className="size-5" />
        {t('partners.invite.sendWhatsApp')}
      </a>
      <div className="mt-3 rounded-xl bg-white/10 px-3 py-2 text-[12px] [&_button]:text-gold [&_span]:text-white">
        <CopyValue value={invite.delivery.link} label={t('partners.invite.copyLink')} mono />
      </div>
    </motion.div>
  )
}

export function InviteForm({ onDone }: { onDone: (invite: Invite) => void }) {
  const { t } = useTranslation()
  const [locality, setLocality] = useState('')
  const [phone, setPhone] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState<Invite | null>(null)

  async function send() {
    setBusy(true)
    setError('')
    try {
      const invite = await partnersApi.invite(locality, phone.trim())
      setSent(invite)
      onDone(invite)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  if (sent) return <Delivery invite={sent} />
  return (
    <div className="space-y-4">
      <p className="text-[14px] text-navy-soft">{t('partners.invite.body')}</p>
      <LocalityPicker value={locality} onChange={setLocality} />
      <Field label={t('partners.invite.phone')} hint={t('partners.invite.phoneHint')}>
        <input className={fieldClass} inputMode="tel" autoComplete="off" placeholder="+255 7xx xxx xxx" value={phone} onChange={(event) => setPhone(event.target.value)} />
      </Field>
      {error && <Alert tone="error">{error}</Alert>}
      <button type="button" className={primary} disabled={busy || !locality || phone.trim().length < 9} onClick={() => void send()}>
        <SendIcon className="size-4" />
        {busy ? t('partners.sending') : t('partners.invite.create')}
      </button>
    </div>
  )
}

function SignedImage({ load, label }: { load: () => Promise<{ url: string }>; label: string }) {
  const { t } = useTranslation()
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  return (
    <div className="overflow-hidden rounded-xl border border-mist bg-paper">
      {url ? (
        <img src={url} alt={label} className="h-40 w-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <button type="button" onClick={() => load().then((data) => setUrl(data.url), () => setFailed(true))} className="grid h-40 w-full place-items-center text-[12px] text-muted hover:text-navy">
          <span className="flex flex-col items-center gap-2">
            <ImageIcon className="size-6" />
            {failed ? t('partners.photoFailed') : t('partners.showPhoto', { label })}
          </span>
        </button>
      )}
    </div>
  )
}

export function OfficialPanel({ official, onChanged }: { official: Official; onChanged: (official: Official, invite?: Invite) => void }) {
  const { t, i18n } = useTranslation()
  const [mode, setMode] = useState<'view' | 'deactivate'>('view')
  const [reason, setReason] = useState('')
  const [replacement, setReplacement] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [invite, setInvite] = useState<Invite | null>(null)

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3">
        <Initials name={official.name} className="size-12 text-[15px]" />
        <div className="min-w-0">
          <p className="truncate text-[16px] font-semibold text-navy">{official.name}</p>
          <p className="text-[13px] text-muted">{official.position ? t(`partners.positions.${official.position}`) : t('partners.kinds.official')} · {official.official_id}</p>
        </div>
        <span className="ml-auto">
          <PartnerChip status={official.status} />
        </span>
      </div>

      {(official.has_photo || official.has_stamp) && (
        <div className="mt-5 grid grid-cols-2 gap-3">
          {official.has_photo && <SignedImage label={t('partners.livePhoto')} load={() => partnersApi.photo(official.official_id, 'photo')} />}
          {official.has_stamp && <SignedImage label={t('partners.stamp')} load={() => partnersApi.photo(official.official_id, 'stamp')} />}
        </div>
      )}

      <div className="mt-4">
        {official.locality && <DetailRow label={t('partners.rows.locality')}>{placeText(official.locality)}</DetailRow>}
        {official.phone && <DetailRow label={t('partners.rows.phone')}>{official.phone}</DetailRow>}
        <DetailRow label={t('partners.rows.email')}>{official.email}</DetailRow>
        {official.national_id && <DetailRow label={t('partners.rows.nationalId')}>{official.national_id}</DetailRow>}
        <DetailRow label={t('partners.rows.documents')}>{`${official.documents.received}/${official.documents.total}`}</DetailRow>
        {official.covers.length > 0 && <DetailRow label={t('partners.rows.covers')}>{official.covers.join(', ')}</DetailRow>}
        <DetailRow label={t('partners.rows.registered')}>{formatShortDate(official.created_at, i18n.language)}</DetailRow>
        {official.confirmed_at && <DetailRow label={t('partners.rows.confirmed')}>{`${official.confirmed_by} · ${formatShortDate(official.confirmed_at, i18n.language)}`}</DetailRow>}
        {official.deactivated_reason && <DetailRow label={t('partners.rows.reason')}>{official.deactivated_reason}</DetailRow>}
      </div>

      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
      {invite && <div className="mt-5"><Delivery invite={invite} /></div>}

      <AnimatePresence mode="wait" initial={false}>
        {mode === 'view' && !invite ? (
          <motion.div key="view" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-6 space-y-2.5">
            {official.status === 'AWAITING_APPROVAL' && (
              <>
                <p className="rounded-xl bg-[#fdf3e2] px-4 py-3 text-[13px] text-[#8a4b06]">{t('partners.approveNote')}</p>
                <button type="button" className={primary} disabled={busy} onClick={() => void run(async () => onChanged(await partnersApi.approve(official.official_id)))}>
                  <CheckIcon className="size-4" />
                  {t('partners.approve')}
                </button>
              </>
            )}
            {official.status !== 'DEACTIVATED' && (
              <button type="button" className={danger} onClick={() => setMode('deactivate')}>
                {official.status === 'AWAITING_APPROVAL' ? t('partners.reject') : t('partners.deactivate')}
              </button>
            )}
          </motion.div>
        ) : mode === 'deactivate' && !invite ? (
          <motion.div key="off" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-6 space-y-4 rounded-2xl border border-mist p-4">
            <p className="text-[13px] text-navy-soft">{t('partners.deactivateBody')}</p>
            <Field label={t('partners.reason')}>
              <textarea rows={3} className={`${fieldClass} h-auto py-2.5`} value={reason} onChange={(event) => setReason(event.target.value)} />
            </Field>
            {official.locality && (
              <Field label={t('partners.replacementPhone')} hint={t('partners.replacementHint', { place: official.locality.name })}>
                <input className={fieldClass} inputMode="tel" placeholder="+255 7xx xxx xxx" value={replacement} onChange={(event) => setReplacement(event.target.value)} />
              </Field>
            )}
            <div className="grid grid-cols-2 gap-2">
              <button type="button" className={secondary} onClick={() => setMode('view')}>{t('partners.back')}</button>
              <button
                type="button"
                className={`${danger} bg-danger text-white hover:bg-danger/90`}
                disabled={busy || !reason.trim()}
                onClick={() =>
                  void run(async () => {
                    const result = await partnersApi.deactivate(official.official_id, reason.trim(), replacement.trim())
                    if (result.invite) setInvite(result.invite)
                    setMode('view')
                    onChanged(result.official, result.invite)
                  })
                }
              >
                {t('partners.confirmOff')}
              </button>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}

export function InvitePanel({ invite, onChanged }: { invite: Invite; onChanged: (invite: Invite) => void }) {
  const { t, i18n } = useTranslation()
  const [current, setCurrent] = useState(invite)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function act(action: () => Promise<Invite>) {
    setBusy(true)
    setError('')
    try {
      const next = await action()
      setCurrent(next)
      onChanged(next)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-[16px] font-semibold text-navy">{current.locality.name}</p>
        <PartnerChip status={current.status === 'REGISTERED' || current.status === 'CANCELLED' ? 'EXPIRED' : current.status} />
      </div>
      <div className="mt-3">
        <DetailRow label={t('partners.rows.locality')}>{placeText(current.locality)}</DetailRow>
        <DetailRow label={t('partners.rows.phone')}>{current.phone}</DetailRow>
        <DetailRow label={t('partners.rows.expires')}>{formatShortDate(current.expires_at, i18n.language)}</DetailRow>
        <DetailRow label={t('partners.rows.invitedBy')}>{current.invited_by}</DetailRow>
        {current.replaces && <DetailRow label={t('partners.rows.replaces')}>{current.replaces.name}</DetailRow>}
      </div>
      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
      {current.delivery && <div className="mt-5"><Delivery invite={current} /></div>}
      {current.status !== 'CANCELLED' && current.status !== 'REGISTERED' && (
        <div className="mt-6 space-y-2.5">
          <button type="button" className={primary} disabled={busy} onClick={() => void act(() => partnersApi.resend(current.id))}>
            <SendIcon className="size-4" />
            {t('partners.invite.resend')}
          </button>
          <button type="button" className={danger} disabled={busy} onClick={() => void act(() => partnersApi.cancel(current.id))}>
            {t('partners.invite.cancel')}
          </button>
        </div>
      )}
    </div>
  )
}

export function ProfessionalPanel({ person, onChanged }: { person: ProfessionalRow; onChanged: (person: ProfessionalRow) => void }) {
  const { t, i18n } = useTranslation()
  const [reason, setReason] = useState('')
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const next = person.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
  async function save() {
    setError('')
    try {
      onChanged(await partnersApi.updateProfessional(person.id, { status: next, reason: reason.trim() }))
      setOpen(false)
      setReason('')
    } catch (failure) {
      setError(errorMessage(t, failure))
    }
  }
  return (
    <div>
      <div className="flex items-center gap-3">
        <Initials name={person.name} className="size-12 text-[15px]" />
        <div className="min-w-0">
          <p className="truncate text-[16px] font-semibold text-navy">{person.name}</p>
          <p className="text-[13px] text-muted">{t(`field.types.${person.professional_type}`)}</p>
        </div>
        <span className="ml-auto">
          <PartnerChip status={person.status} />
        </span>
      </div>
      <div className="mt-4">
        <DetailRow label={t('partners.rows.registration')}>{person.registration_number}</DetailRow>
        <DetailRow label={t('partners.rows.phone')}>{person.phone}</DetailRow>
        <DetailRow label={t('partners.rows.email')}>{person.email}</DetailRow>
        <DetailRow label={t('partners.rows.nationalId')}>{person.national_id}</DetailRow>
        {person.region_names.length > 0 && <DetailRow label={t('partners.rows.regions')}>{person.region_names.join(', ')}</DetailRow>}
        {person.district_names.length > 0 && <DetailRow label={t('partners.rows.districts')}>{person.district_names.join(', ')}</DetailRow>}
        <DetailRow label={t('partners.rows.confirmed')}>{`${person.verified_by} · ${formatShortDate(person.verified_at, i18n.language)}`}</DetailRow>
      </div>
      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}
      {open ? (
        <div className="mt-6 space-y-3 rounded-2xl border border-mist p-4">
          <Field label={t('partners.reason')}>
            <textarea rows={3} className={`${fieldClass} h-auto py-2.5`} value={reason} onChange={(event) => setReason(event.target.value)} />
          </Field>
          <button type="button" className={next === 'INACTIVE' ? `${danger} bg-danger text-white hover:bg-danger/90` : primary} disabled={!reason.trim()} onClick={() => void save()}>
            {next === 'INACTIVE' ? t('partners.confirmOff') : t('partners.reactivate')}
          </button>
        </div>
      ) : (
        <button type="button" className={`mt-6 ${next === 'INACTIVE' ? danger : primary}`} onClick={() => setOpen(true)}>
          {next === 'INACTIVE' ? t('partners.deactivate') : t('partners.reactivate')}
        </button>
      )}
    </div>
  )
}

const TYPES: ProfessionalType[] = ['SURVEYOR', 'AFISA_MIPANGO_MIJI', 'PLANNER']

export function ProfessionalForm({ onDone }: { onDone: (person: ProfessionalRow) => void }) {
  const { t } = useTranslation()
  const [values, setValues] = useState({ full_name: '', email: '', phone: '', registration_number: '', national_id_number: '' })
  const [type, setType] = useState<ProfessionalType>('SURVEYOR')
  const [regions, setRegions] = useState<Place[]>([])
  const [region, setRegion] = useState('')
  const [districts, setDistricts] = useState<Place[]>([])
  const [chosen, setChosen] = useState<{ regions: Place[]; districts: Place[] }>({ regions: [], districts: [] })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    marketApi.regions().then(setRegions, () => setRegions([]))
  }, [])

  function pickRegion(id: string) {
    setRegion(id)
    setDistricts([])
    if (id) marketApi.districts(id).then(setDistricts, () => setDistricts([]))
  }

  function toggle(kind: 'regions' | 'districts', place: Place) {
    setChosen((current) => {
      const has = current[kind].some((row) => row.id === place.id)
      return { ...current, [kind]: has ? current[kind].filter((row) => row.id !== place.id) : [...current[kind], place] }
    })
  }

  async function save() {
    setBusy(true)
    setError('')
    try {
      onDone(await partnersApi.registerProfessional({ ...values, professional_type: type, regions: chosen.regions.map((row) => row.id), districts: chosen.districts.map((row) => row.id) }))
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  const set = (key: keyof typeof values) => (event: React.ChangeEvent<HTMLInputElement>) => setValues((current) => ({ ...current, [key]: event.target.value }))
  const ready = values.full_name.trim() && values.email.trim() && values.phone.trim() && values.registration_number.trim() && values.national_id_number.trim() && (chosen.regions.length || chosen.districts.length)
  const regionName = regions.find((row) => row.id === region)?.name ?? ''

  return (
    <div className="space-y-4">
      <p className="text-[14px] text-navy-soft">{t('partners.professional.body')}</p>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t('partners.professional.type')}>
        {TYPES.map((item) => (
          <button key={item} type="button" role="radio" aria-checked={type === item} onClick={() => setType(item)} className={`rounded-full border px-3.5 py-1.5 text-[13px] font-medium ${type === item ? 'border-gold bg-gold/15 text-[#7a5410]' : 'border-mist text-navy-soft'}`}>
            {t(`field.types.${item}`)}
          </button>
        ))}
      </div>
      <Field label={t('partners.professional.name')}><input className={fieldClass} value={values.full_name} onChange={set('full_name')} /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('partners.rows.phone')}><input className={fieldClass} inputMode="tel" placeholder="+255 7xx xxx xxx" value={values.phone} onChange={set('phone')} /></Field>
        <Field label={t('partners.rows.email')}><input className={fieldClass} type="email" value={values.email} onChange={set('email')} /></Field>
        <Field label={t('partners.rows.registration')}><input className={fieldClass} value={values.registration_number} onChange={set('registration_number')} /></Field>
        <Field label={t('partners.rows.nationalId')}><input className={fieldClass} value={values.national_id_number} onChange={set('national_id_number')} /></Field>
      </div>
      <div>
        <p className="mb-1.5 text-[13px] font-medium text-navy">{t('partners.professional.coverage')}</p>
        <select className={fieldClass} value={region} onChange={(event) => pickRegion(event.target.value)}>
          <option value="">{t('partners.place.choose')}</option>
          {regions.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
        {region && (
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => toggle('regions', { id: region, name: regionName })} className={`rounded-full border px-3 py-1 text-[12px] font-medium ${chosen.regions.some((row) => row.id === region) ? 'border-navy bg-navy text-white' : 'border-mist text-navy'}`}>
              {t('partners.professional.wholeRegion', { region: regionName })}
            </button>
            {districts.map((row) => {
              const on = chosen.districts.some((item) => item.id === row.id)
              return (
                <button key={row.id} type="button" onClick={() => toggle('districts', row)} className={`rounded-full border px-3 py-1 text-[12px] ${on ? 'border-gold bg-gold/15 text-[#7a5410]' : 'border-mist text-navy-soft'}`}>
                  {row.name}
                </button>
              )
            })}
          </div>
        )}
        {(chosen.regions.length > 0 || chosen.districts.length > 0) && (
          <p className="mt-3 text-[12px] text-muted">{t('partners.professional.chosen', { list: [...chosen.regions, ...chosen.districts].map((row) => row.name).join(', ') })}</p>
        )}
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      <p className="text-[12px] text-muted">{t('partners.professional.loginNote')}</p>
      <button type="button" className={primary} disabled={busy || !ready} onClick={() => void save()}>
        {busy ? t('partners.sending') : t('partners.professional.save')}
      </button>
    </div>
  )
}
