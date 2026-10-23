import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { BankIcon, BanknoteIcon, ChatIcon, ClockIcon, HomeIcon, LockIcon, ShieldIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { adminApi, type Bank, type ListingLookup, type SettingHistory, type SettingRow, type SettingsPayload } from '../../../lib/adminApi'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate, formatTsh } from '../../../lib/format'
import { RateEditor } from './RateEditor'
import { TemplateEditor } from './TemplateEditor'

// ADM-02, PAY-01, D5. After R18: a grouped menu on the left; each section has
// a title and a short explanation, then each setting with what it does, its
// current value, who changed it last, and Save.

type Section = 'commission' | 'fee' | 'bank' | 'limits' | 'complaints' | 'checks' | 'scope' | 'delivery' | 'templates' | 'listings'

const GROUPS: { key: string; icon: typeof BanknoteIcon; sections: Section[] }[] = [
  { key: 'money', icon: BanknoteIcon, sections: ['commission', 'fee', 'bank'] },
  { key: 'time', icon: ClockIcon, sections: ['limits', 'complaints'] },
  { key: 'checks', icon: ShieldIcon, sections: ['checks', 'scope'] },
  { key: 'messages', icon: ChatIcon, sections: ['templates', 'delivery'] },
  { key: 'listings', icon: HomeIcon, sections: ['listings'] },
]

const KEYS: Partial<Record<Section, string[]>> = {
  limits: ['identity_expiry_months', 'location_check_months', 'confirmation_days', 'owner_consent_days', 'owner_contact_working_days', 'official_registration_days', 'official_task_days', 'professional_task_days', 'payout_working_days', 'full_check_reliance_days', 'full_check_refresh_months', 'lost_sold_review_months', 'free_check_report_days'],
  complaints: ['complaint_ack_working_days', 'complaint_payment_working_days', 'complaint_other_working_days', 'complaint_final_review_days'],
  checks: ['duplicate_distance_m', 'duplicate_size_percent', 'corner_accuracy_m', 'area_difference_percent', 'photo_distance_m', 'photo_age_days', 'public_map_rounding_m', 'free_check_daily_limit'],
  delivery: ['email_max_attempts', 'outbox_waiting_hours'],
}

function unitOf(key: string) {
  if (key.endsWith('working_days')) return 'workingDays'
  if (key.endsWith('_days')) return 'days'
  if (key.endsWith('_months')) return 'months'
  if (key.endsWith('_hours')) return 'hours'
  if (key.endsWith('_m')) return 'metres'
  if (key.endsWith('_percent')) return 'percent'
  return 'count'
}

export function SettingsPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('admin.settings.title'))
  const [params, setParams] = useSearchParams()
  const section = (params.get('section') as Section | null) ?? 'commission'
  const [data, setData] = useState<SettingsPayload | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi.settings().then(setData, (failure) => setError(errorMessage(t, failure)))
  }, [t])

  function updated(row: SettingRow) {
    setData((current) => (current ? { ...current, settings: current.settings.map((item) => (item.key === row.key ? row : item)) } : current))
  }

  if (error && !data) return <Alert tone="error">{error}</Alert>
  if (!data) return <FullPageLoader inline />
  const byKey = Object.fromEntries(data.settings.map((row) => [row.key, row]))

  return (
    <div className="pb-10">
      <h1 className="text-[24px] font-semibold text-navy">{t('admin.settings.title')}</h1>
      <div className="mt-5 grid gap-5 lg:grid-cols-[230px_minmax(0,1fr)]">
        <nav aria-label={t('admin.settings.title')} className="self-start rounded-xl border border-mist bg-white p-2 lg:sticky lg:top-4">
          {GROUPS.map((group) => (
            <div key={group.key} className="mb-1">
              <p className="flex items-center gap-2 px-3 pt-2 pb-1 text-[13px] font-semibold text-navy">
                <group.icon className="size-4 text-muted" />
                {t(`admin.settings.groups.${group.key}`)}
              </p>
              {group.sections.map((item) => (
                <button key={item} type="button" onClick={() => setParams({ section: item })} aria-current={section === item ? 'page' : undefined} className={`relative block w-full rounded-lg py-2 pr-3 pl-9 text-left text-[13px] ${section === item ? 'font-medium text-navy' : 'text-navy-soft hover:bg-paper'}`}>
                  {section === item && <motion.span layoutId="settings-section" className="absolute inset-0 rounded-lg bg-[#f3f5f9]" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
                  {section === item && <span className="absolute top-2 bottom-2 left-4 w-0.5 rounded-full bg-gold" />}
                  <span className="relative">{t(`admin.settings.sections.${item}.title`)}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <AnimatePresence mode="wait">
          <motion.section key={section} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} className="min-w-0 rounded-xl border border-mist bg-white px-5 py-5">
            <h2 className="text-[17px] font-semibold text-navy">{t(`admin.settings.sections.${section}.title`)}</h2>
            <p className="mt-1 border-b border-mist pb-4 text-[13px] text-muted">{t(`admin.settings.sections.${section}.body`)}</p>
            <div className="pt-4">
              {section === 'commission' && <RateEditor examples={data.examples} />}
              {section === 'fee' && byKey.full_check_fee && <FeeSection row={byKey.full_check_fee} director={data.is_director} examples={data.examples} onSaved={updated} />}
              {section === 'bank' && <BankSection />}
              {section === 'scope' && (
                <div className="space-y-6">
                  {['full_check_scope_sw', 'full_check_scope'].map((key) => byKey[key] && <SettingItem key={key} row={byKey[key]} onSaved={updated} long />)}
                </div>
              )}
              {KEYS[section] && (
                <div className="divide-y divide-mist/70">
                  {KEYS[section]?.map((key) => byKey[key] && <SettingItem key={key} row={byKey[key]} onSaved={updated} />)}
                </div>
              )}
              {section === 'templates' && <TemplateEditor />}
              {section === 'listings' && <ListingSection />}
            </div>
          </motion.section>
        </AnimatePresence>
      </div>
    </div>
  )
}

function LastChange({ row }: { row: SettingRow }) {
  const { t, i18n } = useTranslation()
  if (!row.changed_at) return <span className="text-[11px] text-muted">{t('admin.settings.default')}</span>
  return <span className="text-[11px] text-muted">{t('admin.settings.lastChange', { who: row.changed_by || t('admin.audit.system'), date: formatShortDate(row.changed_at, i18n.language) })}</span>
}

function SettingItem({ row, onSaved, long = false }: { row: SettingRow; onSaved: (row: SettingRow) => void; long?: boolean }) {
  const { t, i18n } = useTranslation()
  const [value, setValue] = useState(row.value === null ? '' : String(row.value))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState<SettingHistory | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const changed = value.trim() !== (row.value === null ? '' : String(row.value))
  const unit = unitOf(row.key)

  async function save() {
    setBusy(true)
    setError('')
    try {
      const result = await adminApi.saveSetting(row.key, long ? value.trim() : Number(value), row.version)
      onSaved({ ...row, value: result.value, version: result.version, changed_by: t('admin.settings.you'), changed_at: new Date().toISOString() })
      setHistory(null)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  function toggleHistory() {
    setShowHistory((value) => !value)
    if (!history && row.version > 0) adminApi.settingHistory(row.key).then(setHistory, () => undefined)
  }

  return (
    <div className={long ? '' : 'grid gap-3 py-4 md:grid-cols-[minmax(0,1fr)_260px] md:items-start'}>
      <div>
        <p className="text-[14px] font-medium text-navy">{t(`admin.settings.keys.${row.key}.label`)}</p>
        <p className="mt-0.5 text-[12px] text-muted">{t(`admin.settings.keys.${row.key}.help`)}</p>
        <span className="mt-1 flex flex-wrap items-center gap-2">
          <LastChange row={row} />
          {row.version > 0 && <button type="button" onClick={toggleHistory} className="text-[11px] text-[#3552a8] hover:underline">{showHistory ? t('admin.settings.hideHistory') : t('admin.settings.showHistory')}</button>}
        </span>
        <AnimatePresence>
          {showHistory && (
            <motion.ul initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="mt-2 space-y-1 overflow-hidden text-[11px] text-navy-soft">
              {history?.history.map((item) => (
                <li key={item.version}>{`v${item.version} · ${String(item.value).slice(0, 60)} · ${item.actor} · ${formatShortDate(item.created_at, i18n.language)}`}</li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>
      </div>
      <div className={long ? 'mt-3' : ''}>
        {long ? (
          <textarea rows={4} value={value} onChange={(event) => setValue(event.target.value)} className="w-full rounded-lg border border-mist px-3 py-2 text-[13px] leading-relaxed text-navy outline-none focus:border-gold" />
        ) : (
          <span className="flex items-center gap-2">
            <input inputMode="numeric" value={value} onChange={(event) => setValue(event.target.value)} className="h-10 w-28 rounded-lg border border-mist px-3 text-right text-[14px] text-navy tabular-nums outline-none focus:border-gold" />
            <span className="text-[12px] text-muted">{t(`admin.settings.units.${unit}`)}</span>
            <button type="button" disabled={!changed || busy} onClick={() => void save()} className="ml-auto h-10 rounded-lg bg-gold px-4 text-[13px] font-semibold text-navy disabled:opacity-40">{t('admin.save')}</button>
          </span>
        )}
        {long && (
          <div className="mt-2 flex justify-end">
            <button type="button" disabled={!changed || busy} onClick={() => void save()} className="h-10 rounded-lg bg-gold px-4 text-[13px] font-semibold text-navy disabled:opacity-40">{t('admin.save')}</button>
          </div>
        )}
        {error && <p className="mt-2 text-[12px] text-danger">{error}</p>}
      </div>
    </div>
  )
}

// FUL-01 and D5: only the Director sets the fee; the example shows how it is built.
function FeeSection({ row, director, examples, onSaved }: { row: SettingRow; director: boolean; examples: SettingsPayload['examples']; onSaved: (row: SettingRow) => void }) {
  const { t, i18n } = useTranslation()
  const [value, setValue] = useState(row.value === null ? '' : String(row.value))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const changed = value !== (row.value === null ? '' : String(row.value))
  async function save() {
    setBusy(true)
    setError('')
    try {
      const result = await adminApi.saveSetting('full_check_fee', value, row.version)
      onSaved({ ...row, value: result.value, version: result.version, changed_by: t('admin.settings.you'), changed_at: new Date().toISOString() })
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-4 rounded-xl bg-navy px-5 py-4 text-white">
        <div>
          <p className="text-[12px] text-white/60">{t('admin.fee.current')}</p>
          <p className="text-[28px] font-bold tracking-tight">{row.value ? formatTsh(String(row.value), i18n.language) : t('admin.fee.notSet')}</p>
          <LastChange row={row} />
        </div>
        {!director && (
          <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-[12px]"><LockIcon className="size-3.5" />{t('admin.fee.directorOnly')}</span>
        )}
      </div>
      {director && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-navy-soft">TSh</span>
          <input inputMode="numeric" value={value} onChange={(event) => setValue(event.target.value.replace(/\D/g, ''))} className="h-10 w-44 rounded-lg border border-mist px-3 text-right text-[14px] text-navy tabular-nums outline-none focus:border-gold" />
          <button type="button" onClick={() => setValue(String(examples.full_check_fee))} className="text-[12px] text-[#3552a8] hover:underline">{t('admin.fee.useExample')}</button>
          <button type="button" disabled={!changed || busy || !value} onClick={() => void save()} className="ml-auto h-10 rounded-lg bg-gold px-4 text-[13px] font-semibold text-navy disabled:opacity-40">{t('admin.save')}</button>
        </div>
      )}
      {error && <Alert tone="error">{error}</Alert>}
      <div>
        <p className="text-[13px] font-medium text-navy">{t('admin.fee.exampleTitle', { total: formatTsh(String(examples.full_check_fee), i18n.language) })}</p>
        <table className="mt-2 w-full text-[13px]">
          <tbody>
            {examples.full_check_fee_parts.map((part) => (
              <tr key={part.key} className="border-b border-mist/70">
                <td className="py-2.5 pr-3">
                  <span className="block text-navy">{t(`admin.fee.parts.${part.key}.label`)}</span>
                  <span className="block text-[11px] text-muted">{t(`admin.fee.parts.${part.key}.basis`)}</span>
                </td>
                <td className="py-2.5 text-right text-navy tabular-nums">{formatTsh(String(part.amount), i18n.language)}</td>
              </tr>
            ))}
            <tr>
              <td className="py-2.5 font-semibold text-navy">{t('admin.fee.total')}</td>
              <td className="py-2.5 text-right font-semibold text-navy tabular-nums">{formatTsh(String(examples.full_check_fee), i18n.language)}</td>
            </tr>
          </tbody>
        </table>
        <p className="mt-2 text-[12px] text-muted">{t('admin.fee.note')}</p>
      </div>
    </div>
  )
}

const BANK_FIELDS: (keyof Bank)[] = ['bank_name', 'account_name', 'account_number', 'branch']

function BankSection() {
  const { t, i18n } = useTranslation()
  const [bank, setBank] = useState<Bank | null | undefined>(undefined)
  const [form, setForm] = useState<Bank>({ bank_name: '', account_name: '', account_number: '', branch: '' })
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    adminApi.oweruBank().then(
      (row) => {
        setBank(row)
        if (row) setForm({ bank_name: row.bank_name, account_name: row.account_name, account_number: row.account_number, branch: row.branch })
      },
      (failure) => setError(errorMessage(t, failure)),
    )
  }, [t])
  async function save() {
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      await adminApi.saveOweruBank(form)
      setSaved(true)
      setBank({ ...form, updated_at: new Date().toISOString() })
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  if (bank === undefined) return error ? <Alert tone="error">{error}</Alert> : <div className="h-32 animate-pulse rounded-xl bg-paper" />
  return (
    <div className="max-w-xl space-y-4">
      <div className="flex items-center gap-3 rounded-xl border border-mist px-4 py-3">
        <span className="grid size-10 place-items-center rounded-full bg-navy text-gold"><BankIcon className="size-5" /></span>
        <span className="text-[13px] text-navy-soft">{bank ? t('admin.bank.lastChange', { date: bank.updated_at ? formatShortDate(bank.updated_at, i18n.language) : '' }) : t('admin.bank.none')}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {BANK_FIELDS.map((field) => (
          <label key={field} className="block">
            <span className="mb-1 block text-[13px] font-medium text-navy">{t(`admin.bank.fields.${field}`)}</span>
            <input value={form[field] ?? ''} onChange={(event) => setForm({ ...form, [field]: event.target.value })} className="h-10 w-full rounded-lg border border-mist px-3 text-[14px] text-navy outline-none focus:border-gold" />
          </label>
        ))}
      </div>
      <p className="text-[12px] text-muted">{t('admin.bank.note')}</p>
      {error && <Alert tone="error">{error}</Alert>}
      {saved && <Alert tone="success">{t('admin.bank.saved')}</Alert>}
      <button type="button" disabled={busy || BANK_FIELDS.some((field) => !String(form[field] ?? '').trim())} onClick={() => void save()} className="h-10 rounded-lg bg-gold px-5 text-[13px] font-semibold text-navy disabled:opacity-40">{t('admin.save')}</button>
    </div>
  )
}

// LST-12: find a listing by its number, then suspend or restore it with a reason.
function ListingSection() {
  const { t, i18n } = useTranslation()
  const [id, setId] = useState('')
  const [found, setFound] = useState<ListingLookup | null>(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [busy, setBusy] = useState(false)
  async function find(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setDone('')
    setFound(null)
    try {
      setFound(await adminApi.listing(id.trim()))
    } catch (failure) {
      setError(errorMessage(t, failure))
    }
  }
  async function act(action: 'suspend' | 'restore') {
    if (!found) return
    setBusy(true)
    setError('')
    try {
      const result = await adminApi.listingAction(found.listing_id, found.version, reason.trim(), action)
      setFound({ ...found, status: result.status, version: result.version })
      setDone(t(`admin.listings.done.${action}`))
      setReason('')
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }
  const suspended = found?.status === 'SUSPENDED'
  return (
    <div className="max-w-xl space-y-4">
      <form onSubmit={find} className="flex gap-2">
        <input value={id} onChange={(event) => setId(event.target.value)} placeholder={t('admin.listings.placeholder')} className="h-10 flex-1 rounded-lg border border-mist px-3 font-mono text-[13px] text-navy outline-none focus:border-gold" />
        <button type="submit" disabled={!id.trim()} className="h-10 rounded-lg bg-navy px-4 text-[13px] font-semibold text-white disabled:opacity-40">{t('admin.listings.find')}</button>
      </form>
      {error && <Alert tone="error">{error}</Alert>}
      {done && <Alert tone="success">{done}</Alert>}
      {found && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-mist p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[14px] font-semibold text-navy">{found.listing_id}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${suspended ? 'bg-danger-soft text-danger' : 'bg-success-soft text-success'}`}>{t(`admin.duplicate.statuses.${found.status}`, { defaultValue: found.status })}</span>
          </div>
          <p className="mt-1 text-[13px] text-navy-soft">{`${found.property_id} · ${found.area}`}</p>
          <p className="text-[12px] text-muted">{`${found.lister} (${t(`admin.duplicate.kinds.${found.lister_kind}`)}) · ${formatShortDate(found.created_at, i18n.language)}`}</p>
          <label className="mt-4 block">
            <span className="mb-1 block text-[13px] font-medium text-navy">{t('admin.listings.reason')}</span>
            <textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} className="w-full rounded-lg border border-mist px-3 py-2 text-[13px] text-navy outline-none focus:border-gold" />
          </label>
          <button type="button" disabled={busy || !reason.trim()} onClick={() => void act(suspended ? 'restore' : 'suspend')} className={`mt-3 h-10 rounded-lg px-4 text-[13px] font-semibold disabled:opacity-40 ${suspended ? 'bg-gold text-navy' : 'bg-danger text-white'}`}>
            {suspended ? t('admin.listings.restore') : t('admin.listings.suspend')}
          </button>
        </motion.div>
      )}
    </div>
  )
}
