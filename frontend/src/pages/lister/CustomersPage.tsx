import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert } from '../../components/Alert'
import { FullPageLoader } from '../../components/FullPageLoader'
import { ArrowLeftIcon, CalendarIcon, ChatIcon, HomeIcon, NoteIcon, PlusIcon, SearchIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { errorMessage } from '../../lib/errors'
import { formatShortDate } from '../../lib/format'
import { peopleApi, type Customer, type CustomerLead } from '../../lib/peopleApi'

// LEAD-02, LEAD-06. After R23: the customer's name and stage chips, a
// WhatsApp button, then their enquiries and viewings by property, with the
// details on the right. After R24: notes as a table, newest first, with Add
// note. The list is private to this lister.

const STAGE_TONE: Record<string, string> = {
  NEW: 'bg-[#eef3fd] text-[#3552a8]',
  CONTACTED: 'bg-gold/15 text-[#7a5410]',
  VIEWING: 'bg-[#f1e9fa] text-[#6b3fa0]',
  NEGOTIATION: 'bg-[#fdf3e2] text-[#b4640a]',
  CLOSING: 'bg-navy text-gold',
  WON: 'bg-success-soft text-success',
  LOST: 'bg-paper text-muted',
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || '?'
}

export function CustomersPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('customers.title'))
  const [rows, setRows] = useState<Customer[] | null>(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    peopleApi.customers().then(setRows, (failure) => {
      setError(errorMessage(t, failure))
      setRows([])
    })
  }, [t])

  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (rows ?? []).filter((row) => !needle || `${row.name} ${row.whatsapp}`.toLowerCase().includes(needle))
  }, [rows, search])

  if (!rows) return <FullPageLoader inline />
  const current = rows.find((row) => row.whatsapp === selected) ?? null

  function noteAdded(leadId: string, note: CustomerLead['notes'][number]) {
    setRows((list) => list?.map((row) => ({ ...row, leads: row.leads.map((lead) => (lead.id === leadId ? { ...lead, notes: [note, ...lead.notes] } : lead)) })) ?? null)
  }

  return (
    <div className="pb-10">
      <h1 className="text-[24px] font-semibold text-navy">{t('customers.title')}</h1>
      <p className="mt-1 text-[13px] text-muted">{t('customers.subtitle')}</p>
      {error && <div className="mt-4"><Alert tone="error">{error}</Alert></div>}

      <div className="mt-5 grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <section className={`rounded-xl border border-mist bg-white ${current ? 'hidden lg:block' : ''}`}>
          <label className="relative block border-b border-mist p-3">
            <span className="sr-only">{t('customers.search')}</span>
            <SearchIcon className="pointer-events-none absolute top-1/2 left-6 size-4 -translate-y-1/2 text-muted" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('customers.search')} className="h-10 w-full rounded-lg border border-mist pr-3 pl-9 text-[13px] text-navy outline-none focus:border-gold" />
          </label>
          {shown.length === 0 ? (
            <p className="px-4 py-10 text-center text-[13px] text-muted">{rows.length === 0 ? t('customers.empty') : t('customers.noMatch')}</p>
          ) : (
            <ul className="max-h-[640px] overflow-y-auto p-2">
              {shown.map((row) => {
                const latest = row.leads.at(-1)
                return (
                  <li key={row.whatsapp}>
                    <button type="button" onClick={() => setSelected(row.whatsapp)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left ${selected === row.whatsapp ? 'bg-[#f6f1e6]' : 'hover:bg-paper'}`}>
                      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-navy text-[13px] font-semibold text-gold">{initials(row.name)}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14px] font-medium text-navy">{row.name || row.whatsapp}</span>
                        <span className="block truncate text-[12px] text-muted">{t('customers.enquiries', { count: row.leads.length })}</span>
                      </span>
                      {latest && <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${STAGE_TONE[latest.stage] ?? ''}`}>{t(`lister.stagesShort.${latest.stage}`)}</span>}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        <AnimatePresence mode="wait">
          {current ? (
            <CustomerDetail key={current.whatsapp} customer={current} onBack={() => setSelected(null)} onNote={noteAdded} />
          ) : (
            <motion.section key="none" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="hidden place-items-center rounded-xl border border-dashed border-mist bg-white/60 px-6 py-20 text-center lg:grid">
              <span>
                <ChatIcon className="mx-auto size-8 text-mist" />
                <span className="mt-3 block text-[14px] text-muted">{t('customers.pick')}</span>
              </span>
            </motion.section>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function CustomerDetail({ customer, onBack, onNote }: { customer: Customer; onBack: () => void; onNote: (leadId: string, note: CustomerLead['notes'][number]) => void }) {
  const { t, i18n } = useTranslation()
  const reduce = useReducedMotion()
  const [tab, setTab] = useState<'activity' | 'notes'>('activity')
  const latest = customer.leads.at(-1)
  const stages = [...new Set(customer.leads.map((lead) => lead.stage))]
  const notes = customer.leads.flatMap((lead) => lead.notes.map((note) => ({ ...note, listing_id: lead.listing_id }))).sort((a, b) => b.created_at.localeCompare(a.created_at))
  const followUp = customer.leads.map((lead) => lead.follow_up_at).filter(Boolean).sort()[0]
  const whatsapp = `https://wa.me/${customer.whatsapp.replace(/^\+/, '')}`

  return (
    <motion.section key={customer.whatsapp} initial={reduce ? false : { opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="min-w-0 overflow-hidden rounded-xl border border-mist bg-white">
      <div className="px-5 pt-4">
        <button type="button" onClick={onBack} className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-navy lg:hidden">
          <ArrowLeftIcon className="size-4" />
          {t('customers.back')}
        </button>
        <div className="mt-2 flex flex-wrap items-center gap-4">
          <span className="grid size-16 place-items-center rounded-full bg-navy text-[20px] font-semibold text-gold ring-4 ring-gold/30">{initials(customer.name)}</span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[20px] font-semibold text-navy">{customer.name || customer.whatsapp}</p>
            <p className="text-[13px] text-muted">{`${customer.whatsapp} · ${t('customers.since', { date: formatShortDate(customer.leads[0].created_at, i18n.language) })}`}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {stages.map((stage) => <span key={stage} className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${STAGE_TONE[stage] ?? ''}`}>{t(`lister.stages.${stage}`)}</span>)}
              <span className="rounded-md border border-mist px-2 py-0.5 text-[11px] text-navy-soft">{t('customers.properties', { count: new Set(customer.leads.map((lead) => lead.listing_id)).size })}</span>
            </div>
          </div>
          <a href={whatsapp} target="_blank" rel="noreferrer" className="inline-flex h-10 items-center gap-2 rounded-lg border border-mist px-4 text-[13px] font-medium text-navy hover:border-[#25d366]">
            <WhatsAppIcon className="size-4 text-[#25d366]" />
            {t('customers.whatsapp')}
          </a>
        </div>
        <div role="tablist" className="mt-5 flex gap-1">
          {(['activity', 'notes'] as const).map((item) => (
            <button key={item} type="button" role="tab" aria-selected={tab === item} onClick={() => setTab(item)} className={`relative rounded-md px-3 py-2 text-[13px] font-medium ${tab === item ? 'text-navy' : 'text-muted hover:text-navy'}`}>
              {tab === item && <motion.span layoutId="customer-tab" className="absolute inset-0 rounded-md bg-[#f3f5f9]" />}
              <span className="relative">{item === 'notes' ? t('customers.notesTab', { count: notes.length }) : t('customers.activityTab')}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="grid border-t border-mist lg:grid-cols-[minmax(0,1fr)_240px]">
        <div className="min-w-0 px-5 py-5">
          {tab === 'activity' ? (
            <ol className="space-y-3">
              {[...customer.leads].reverse().map((lead, index) => (
                <motion.li key={lead.id} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }} className="flex gap-3">
                  <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-full bg-gold/15 text-[#9a6c12]">{lead.source === 'VIEWING_REQUEST' ? <CalendarIcon className="size-4" /> : lead.source === 'WHATSAPP_CONTACT' ? <WhatsAppIcon className="size-4" /> : <ChatIcon className="size-4" />}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] text-navy"><span className="font-medium">{t(`lister.sources.${lead.source}`)}</span> <span className="text-muted">· {formatShortDate(lead.created_at, i18n.language)}</span></p>
                    <Link to={`/listings/${lead.listing_id}`} className="mt-1.5 flex items-center gap-3 rounded-xl border border-mist px-3 py-2.5 hover:border-gold/60">
                      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-paper text-muted"><HomeIcon className="size-5" /></span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] font-medium text-navy">{`${t(`market.category.${lead.category}`)} · ${lead.area}`}</span>
                        <span className="block font-mono text-[11px] text-muted">{lead.listing_id}</span>
                      </span>
                      <span className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${STAGE_TONE[lead.stage] ?? ''}`}>{t(`lister.stagesShort.${lead.stage}`)}</span>
                    </Link>
                  </div>
                </motion.li>
              ))}
            </ol>
          ) : (
            <Notes customer={customer} notes={notes} onNote={onNote} />
          )}
        </div>
        <aside className="border-t border-mist px-5 py-5 text-[13px] lg:border-t-0 lg:border-l">
          <p className="font-semibold text-navy">{t('customers.details')}</p>
          <dl className="mt-3 space-y-3">
            <div className="flex justify-between gap-3"><dt className="text-muted">{t('customers.stage')}</dt><dd>{latest && <span className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${STAGE_TONE[latest.stage] ?? ''}`}>{t(`lister.stages.${latest.stage}`)}</span>}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-muted">{t('customers.phone')}</dt><dd className="text-navy">{customer.whatsapp}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-muted">{t('customers.first')}</dt><dd className="text-navy">{formatShortDate(customer.leads[0].created_at, i18n.language)}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-muted">{t('customers.followUp')}</dt><dd className="text-navy">{followUp ? formatShortDate(followUp, i18n.language) : '·'}</dd></div>
          </dl>
          <p className="mt-4 text-[11px] text-muted">{t('customers.private')}</p>
        </aside>
      </div>
    </motion.section>
  )
}

function Notes({ customer, notes, onNote }: { customer: Customer; notes: (CustomerLead['notes'][number] & { listing_id: string })[]; onNote: (leadId: string, note: CustomerLead['notes'][number]) => void }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [leadId, setLeadId] = useState(customer.leads.at(-1)?.id ?? '')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function add() {
    setBusy(true)
    setError('')
    try {
      onNote(leadId, await peopleApi.addNote(leadId, text.trim()))
      setText('')
      setOpen(false)
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-[15px] font-semibold text-navy">{t('customers.notes')}</p>
        <button type="button" onClick={() => setOpen((value) => !value)} className="inline-flex items-center gap-1 text-[13px] font-medium text-[#9a6c12]"><PlusIcon className="size-4" />{t('customers.addNote')}</button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="mt-3 space-y-2 rounded-xl border border-gold/40 bg-[#fffaf0] p-3">
              {customer.leads.length > 1 && (
                <select value={leadId} onChange={(event) => setLeadId(event.target.value)} className="h-9 w-full rounded-lg border border-mist bg-white px-2 text-[13px] text-navy">
                  {customer.leads.map((lead) => <option key={lead.id} value={lead.id}>{`${lead.listing_id} · ${lead.area}`}</option>)}
                </select>
              )}
              <textarea rows={3} value={text} onChange={(event) => setText(event.target.value)} placeholder={t('customers.notePlaceholder')} className="w-full rounded-lg border border-mist bg-white px-3 py-2 text-[13px] text-navy outline-none focus:border-gold" />
              {error && <Alert tone="error">{error}</Alert>}
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setOpen(false)} className="h-9 rounded-lg border border-mist bg-white px-3 text-[13px] text-navy">{t('admin.cancel')}</button>
                <button type="button" disabled={busy || !text.trim() || !leadId} onClick={() => void add()} className="h-9 rounded-lg bg-gold px-4 text-[13px] font-semibold text-navy disabled:opacity-50">{t('customers.saveNote')}</button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {notes.length === 0 ? (
        <p className="mt-6 text-center text-[13px] text-muted">{t('customers.noNotes')}</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[420px] text-[13px]">
            <thead>
              <tr className="border-b border-mist text-left text-[12px] text-muted">
                <th className="w-8 py-2 font-medium" />
                <th className="py-2 font-medium">{t('customers.note')}</th>
                <th className="w-28 py-2 font-medium">{t('customers.date')}</th>
              </tr>
            </thead>
            <tbody>
              {notes.map((note) => (
                <tr key={note.id} className="border-b border-mist/60 align-top">
                  <td className="py-2.5"><NoteIcon className="size-4 text-muted" /></td>
                  <td className="py-2.5 pr-3 text-navy">
                    <span className="block whitespace-pre-wrap">{note.text}</span>
                    <span className="mt-0.5 block font-mono text-[10px] text-muted">{note.listing_id}</span>
                  </td>
                  <td className="py-2.5 text-navy-soft tabular-nums">{formatShortDate(note.created_at, i18n.language)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
