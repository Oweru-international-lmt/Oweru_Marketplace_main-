import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { ClockIcon, EyeIcon, MapPinIcon, PlusIcon, SendIcon, ShieldIcon, UsersIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'
import { partnersApi, type Invite, type Official, type ProfessionalRow } from '../../../lib/partnersApi'
import { SidePanel } from '../../deals/ui'
import { SearchBox } from '../ops/ui'
import { InviteForm, InvitePanel, OfficialPanel, ProfessionalForm, ProfessionalPanel } from './panels'
import { Count, Initials, PartnerChip, type PartnerStatus } from './ui'

// LOC-01, LOC-06, PRO-01. After R12: stat cards, then one table of everyone
// with role, area, documents received, a status chip and the date; R13's
// filters by type, region and status sit above it.

type Kind = 'official' | 'SURVEYOR' | 'AFISA_MIPANGO_MIJI' | 'PLANNER'
type Row = {
  key: string
  kind: Kind
  name: string
  area: string
  region: string
  documents: [number, number] | null
  status: PartnerStatus
  date: string
  open: { type: 'official'; item: Official } | { type: 'invite'; item: Invite } | { type: 'professional'; item: ProfessionalRow }
}

const KINDS: ('all' | Kind)[] = ['all', 'official', 'SURVEYOR', 'AFISA_MIPANGO_MIJI', 'PLANNER']
const STATUSES: ('all' | PartnerStatus)[] = ['all', 'INVITED', 'AWAITING_APPROVAL', 'ACTIVE', 'DEACTIVATED']

export function PartnersPage() {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  useDocumentTitle(t('partners.title'))
  const [data, setData] = useState<{ officials: Official[]; invites: Invite[]; professionals: ProfessionalRow[] } | null>(null)
  const [error, setError] = useState('')
  const [kind, setKind] = useState<'all' | Kind>('all')
  const [status, setStatus] = useState<'all' | PartnerStatus>('all')
  const [region, setRegion] = useState('')
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState<Row['open'] | null>(null)
  const [form, setForm] = useState<'invite' | 'professional' | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let live = true
    Promise.all([partnersApi.officials(), partnersApi.invites(), partnersApi.professionals().catch(() => [] as ProfessionalRow[])])
      .then(([officials, invites, professionals]) => live && setData({ officials, invites, professionals }))
      .catch((failure) => {
        if (!live) return
        setError(errorMessage(t, failure))
        setData({ officials: [], invites: [], professionals: [] })
      })
    return () => {
      live = false
    }
  }, [t, version])

  const rows = useMemo<Row[]>(() => {
    if (!data) return []
    return [
      ...data.invites.map<Row>((item) => ({
        key: `i-${item.id}`, kind: 'official', name: item.replaces ? t('partners.replacing', { name: item.replaces.name }) : t('partners.invitedOfficial'),
        area: `${item.locality.name}, ${item.locality.district}`, region: item.locality.region, documents: [0, 3],
        status: item.status === 'EXPIRED' ? 'EXPIRED' : 'INVITED', date: item.created_at, open: { type: 'invite', item },
      })),
      ...data.officials.map<Row>((item) => ({
        key: `o-${item.official_id}`, kind: 'official', name: item.name, area: item.locality ? `${item.locality.name}, ${item.locality.district}` : item.covers.join(', '),
        region: item.locality?.region ?? '', documents: [item.documents.received, item.documents.total], status: item.status, date: item.created_at, open: { type: 'official', item },
      })),
      ...data.professionals.map<Row>((item) => ({
        key: `p-${item.id}`, kind: item.professional_type, name: item.name, area: [...item.district_names, ...item.region_names].join(', '),
        region: item.region_names[0] ?? '', documents: [Number(Boolean(item.registration_number)) + Number(Boolean(item.national_id)), 2], status: item.status, date: item.created_at, open: { type: 'professional', item },
      })),
    ].sort((a, b) => b.date.localeCompare(a.date))
  }, [data, t])

  const regions = useMemo(() => [...new Set(rows.map((row) => row.region).filter(Boolean))].sort(), [rows])
  const shown = rows.filter((row) => {
    if (kind !== 'all' && row.kind !== kind) return false
    if (status !== 'all' && (status === 'DEACTIVATED' ? row.status !== 'DEACTIVATED' && row.status !== 'INACTIVE' : status === 'INVITED' ? row.status !== 'INVITED' && row.status !== 'EXPIRED' : row.status !== status)) return false
    if (region && row.region !== region) return false
    const needle = search.trim().toLowerCase()
    return !needle || `${row.name} ${row.area}`.toLowerCase().includes(needle)
  })

  if (!data) return <FullPageLoader inline />

  const cards = [
    { label: t('partners.cards.officials'), value: data.officials.filter((row) => row.status === 'ACTIVE').length, icon: ShieldIcon, tone: 'bg-navy text-gold', note: t('partners.cards.officialsNote', { count: data.officials.length }) },
    { label: t('partners.cards.awaiting'), value: data.officials.filter((row) => row.status === 'AWAITING_APPROVAL').length, icon: ClockIcon, tone: 'bg-[#c2410c] text-white', note: t('partners.cards.awaitingNote') },
    { label: t('partners.cards.invites'), value: data.invites.filter((row) => row.status === 'INVITED').length, icon: SendIcon, tone: 'bg-[#3552a8] text-white', note: t('partners.cards.invitesNote') },
    { label: t('partners.cards.professionals'), value: data.professionals.filter((row) => row.status === 'ACTIVE').length, icon: UsersIcon, tone: 'bg-gold text-navy', note: t('partners.cards.professionalsNote', { count: data.professionals.length }) },
  ]

  function refresh() {
    setVersion((value) => value + 1)
  }

  return (
    <div className="pb-10">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-navy">{t('partners.title')}</h1>
          <p className="mt-1 text-[13px] text-muted">{t('partners.subtitle')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link to="/staff/coverage" className="inline-flex h-10 items-center gap-2 rounded-xl border border-mist bg-white px-4 text-[13px] font-medium text-navy hover:border-navy-soft/40">
            <MapPinIcon className="size-4" />
            {t('partners.coverageLink')}
          </Link>
          <button type="button" onClick={() => setForm('professional')} className="inline-flex h-10 items-center gap-2 rounded-xl border border-mist bg-white px-4 text-[13px] font-medium text-navy hover:border-navy-soft/40">
            <PlusIcon className="size-4" />
            {t('partners.addProfessional')}
          </button>
          <button type="button" onClick={() => setForm('invite')} className="inline-flex h-10 items-center gap-2 rounded-xl bg-gold px-4 text-[13px] font-semibold text-navy hover:bg-[#d39d34]">
            <SendIcon className="size-4" />
            {t('partners.inviteOfficial')}
          </button>
        </div>
      </div>
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card, index) => (
          <motion.div key={card.label} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.07 }} className="flex items-start justify-between rounded-xl border border-mist bg-white px-5 py-4">
            <div>
              <p className="text-[13px] text-navy-soft">{card.label}</p>
              <p className="mt-1.5 text-[28px] font-bold tracking-tight text-navy"><Count value={card.value} /></p>
              <p className="mt-0.5 text-[12px] text-muted">{card.note}</p>
            </div>
            <span className={`grid size-10 place-items-center rounded-xl ${card.tone}`}>
              <card.icon className="size-5" />
            </span>
          </motion.div>
        ))}
      </div>

      <section className="mt-4 rounded-xl border border-mist bg-white">
        <div className="flex flex-wrap items-center gap-3 border-b border-mist/70 px-4 py-3">
          <div role="tablist" aria-label={t('partners.filters.type')} className="flex flex-wrap gap-1 rounded-lg bg-paper p-1">
            {KINDS.map((item) => (
              <button key={item} type="button" role="tab" aria-selected={kind === item} onClick={() => setKind(item)} className={`relative rounded-md px-3 py-1.5 text-[12px] font-medium ${kind === item ? 'text-navy' : 'text-muted hover:text-navy'}`}>
                {kind === item && <motion.span layoutId="partner-kind" className="absolute inset-0 rounded-md bg-white shadow-sm" transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}
                <span className="relative">{item === 'all' ? t('partners.filters.all') : item === 'official' ? t('partners.kinds.official') : t(`field.types.${item}`)}</span>
              </button>
            ))}
          </div>
          <select aria-label={t('partners.filters.status')} value={status} onChange={(event) => setStatus(event.target.value as typeof status)} className="h-9 rounded-lg border border-mist bg-white px-3 text-[12px] text-navy">
            {STATUSES.map((item) => (
              <option key={item} value={item}>{item === 'all' ? t('partners.filters.anyStatus') : t(`partners.status.${item}`)}</option>
            ))}
          </select>
          <select aria-label={t('partners.filters.region')} value={region} onChange={(event) => setRegion(event.target.value)} className="h-9 rounded-lg border border-mist bg-white px-3 text-[12px] text-navy">
            <option value="">{t('partners.filters.anyRegion')}</option>
            {regions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <div className="ml-auto w-full sm:w-auto">
            <SearchBox label={t('partners.filters.search')} value={search} onChange={setSearch} />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-left text-[13px]">
            <caption className="sr-only">{t('partners.title')}</caption>
            <thead>
              <tr className="bg-[#f6f1e6] text-[12px] text-navy-soft">
                <th className="w-12 px-4 py-2.5 font-medium">#</th>
                <th className="px-3 py-2.5 font-medium">{t('partners.columns.name')}</th>
                <th className="px-3 py-2.5 font-medium">{t('partners.columns.role')}</th>
                <th className="px-3 py-2.5 font-medium">{t('partners.columns.area')}</th>
                <th className="px-3 py-2.5 font-medium">{t('partners.columns.documents')}</th>
                <th className="px-3 py-2.5 font-medium">{t('partners.columns.status')}</th>
                <th className="px-3 py-2.5 font-medium">{t('partners.columns.date')}</th>
                <th className="px-4 py-2.5 text-right font-medium">{t('partners.columns.action')}</th>
              </tr>
            </thead>
            <tbody>
              {shown.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-muted">{t('partners.empty')}</td>
                </tr>
              )}
              {shown.map((row, index) => (
                <motion.tr
                  key={row.key}
                  initial={reduce ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(index, 12) * 0.035 }}
                  onClick={() => setOpen(row.open)}
                  className="cursor-pointer border-b border-mist/60 last:border-b-0 hover:bg-paper/70"
                >
                  <td className="px-4 py-3 text-muted tabular-nums">{index + 1}</td>
                  <td className="px-3 py-3">
                    <span className="flex items-center gap-2.5">
                      <Initials name={row.name} className="size-8" />
                      <span className="font-medium text-navy">{row.name}</span>
                    </span>
                  </td>
                  <td className="px-3 py-3 text-navy-soft">{row.kind === 'official' ? t('partners.kinds.official') : t(`field.types.${row.kind}`)}</td>
                  <td className="max-w-[220px] truncate px-3 py-3 text-navy-soft" title={row.area}>{row.area || '·'}</td>
                  <td className="px-3 py-3">
                    {row.documents && (
                      <span className={`font-medium tabular-nums ${row.documents[0] === row.documents[1] ? 'text-success' : 'text-navy-soft'}`}>{`${row.documents[0]}/${row.documents[1]}`}</span>
                    )}
                  </td>
                  <td className="px-3 py-3"><PartnerChip status={row.status} /></td>
                  <td className="px-3 py-3 text-navy-soft tabular-nums">{formatShortDate(row.date, i18n.language)}</td>
                  <td className="px-4 py-3 text-right">
                    <button type="button" aria-label={t('partners.open', { name: row.name })} className="inline-grid size-8 place-items-center rounded-full text-gold hover:bg-gold/10">
                      <EyeIcon className="size-4" />
                    </button>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <SidePanel open={open !== null} title={open?.type === 'invite' ? t('partners.invite.title') : open?.type === 'professional' ? t('partners.kinds.professional') : t('partners.kinds.official')} onClose={() => setOpen(null)}>
        {open?.type === 'official' && <OfficialPanel key={open.item.official_id} official={open.item} onChanged={(item) => { setOpen({ type: 'official', item }); refresh() }} />}
        {open?.type === 'invite' && <InvitePanel key={open.item.id} invite={open.item} onChanged={refresh} />}
        {open?.type === 'professional' && <ProfessionalPanel key={open.item.id} person={open.item} onChanged={(item) => { setOpen({ type: 'professional', item }); refresh() }} />}
      </SidePanel>
      <SidePanel open={form !== null} title={form === 'invite' ? t('partners.inviteOfficial') : t('partners.addProfessional')} onClose={() => setForm(null)}>
        {form === 'invite' && <InviteForm onDone={refresh} />}
        {form === 'professional' && <ProfessionalForm onDone={() => { setForm(null); refresh() }} />}
      </SidePanel>
    </div>
  )
}
