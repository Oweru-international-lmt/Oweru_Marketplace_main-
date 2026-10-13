import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useState, type ComponentType, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../../components/Alert'
import { ChatIcon, CloseIcon, IdCardIcon, InboxIcon, ResetIcon, ShieldIcon, TickIcon, WhatsAppIcon } from '../../../components/icons'
import { PageHeader } from '../../../components/PageHeader'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate, formatTime } from '../../../lib/format'
import { initials } from '../../../lib/initials'
import { staffApi, type OutboxMessage } from '../../../lib/staffApi'
import { useMediaQuery } from '../../../lib/useMediaQuery'

type Tab = 'waiting' | 'sent'
type Kind = 'all' | 'links' | 'verification' | 'complaints' | 'other'

const KINDS: Record<Exclude<Kind, 'all' | 'other'>, string[]> = {
  links: ['PHONE', 'OWNER_PRICE', 'OWNER_RECEIPT', 'FULL_CHECK_CONSENT'],
  verification: ['TASK_ASSIGNED', 'NEEDS_OFFICIAL', 'PROFESSIONAL_LOGIN', 'PROFESSIONAL_DECLINED', 'OFFICIAL_REGISTRATION', 'FULL_CHECK_REPORT_READY', 'FULL_CHECK_NOT_COMPLETED', 'FULL_CHECK_ORDERED', 'OWNER_CONTACT_REQUIRED', 'VERIFICATION_EXPIRING'],
  complaints: ['COMPLAINT_NUMBER', 'COMPLAINT_UPDATE'],
}

const KIND_ICON: Record<Kind, ComponentType<SVGProps<SVGSVGElement>>> = {
  all: InboxIcon,
  links: WhatsAppIcon,
  verification: ShieldIcon,
  complaints: ChatIcon,
  other: IdCardIcon,
}

function kindOf(purpose: string): Exclude<Kind, 'all'> {
  for (const [kind, purposes] of Object.entries(KINDS)) if (purposes.includes(purpose)) return kind as Exclude<Kind, 'all'>
  return 'other'
}

// NTF-02, after O1, O2, O5 and O6: count tiles across the top, Waiting and
// Sent tabs, the kinds of message in a narrow column beside one table, and the
// chosen message as a WhatsApp bubble with "Open in WhatsApp" and "Mark sent".
export function OutboxPage() {
  const { t, i18n } = useTranslation()
  const wide = useMediaQuery('(min-width: 85rem)')
  // With a message open, the kinds column folds away below 1600px.
  const roomy = useMediaQuery('(min-width: 100rem)')
  const [tab, setTab] = useState<Tab>('waiting')
  const [kind, setKind] = useState<Kind>('all')
  const [waiting, setWaiting] = useState<OutboxMessage[] | null>(null)
  const [sent, setSent] = useState<OutboxMessage[] | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [today] = useState(() => new Date().toDateString())

  const load = useCallback(() => {
    staffApi.outbox().then(setWaiting, (caught) => setError(errorMessage(t, caught)))
    staffApi.outbox(true).then(setSent, () => setSent([]))
  }, [t])

  useEffect(() => {
    load()
  }, [load])

  const rows = tab === 'waiting' ? waiting : sent
  const shown = useMemo(
    () => (rows ?? []).filter((row) => kind === 'all' || kindOf(row.purpose) === kind).sort((a, b) => (tab === 'waiting' ? 1 : -1) * a.created_at.localeCompare(b.created_at)),
    [rows, kind, tab],
  )
  const open = (rows ?? []).find((row) => row.id === openId) ?? null
  const kindCounts = (kind: Kind) => (rows ?? []).filter((row) => kind === 'all' || kindOf(row.purpose) === kind).length

  function markedSent(id: string) {
    const row = waiting?.find((item) => item.id === id)
    setWaiting((current) => current?.filter((item) => item.id !== id) ?? null)
    if (row) setSent((current) => [{ ...row, status: 'SENT', sent_at: new Date().toISOString() }, ...(current ?? [])])
    setNotice(t('staff.outbox.markedSent', { name: row?.recipient_name || row?.phone || '' }))
    const next = shown.find((item) => item.id !== id)
    setOpenId(next?.id ?? null)
  }

  const tiles = [
    { label: t('staff.outbox.tiles.waiting'), value: waiting?.length },
    { label: t('staff.outbox.tiles.overdue'), value: waiting?.filter((row) => row.overdue).length, warn: true },
    { label: t('staff.outbox.tiles.links'), value: waiting?.filter((row) => kindOf(row.purpose) === 'links').length },
    { label: t('staff.outbox.tiles.sentToday'), value: sent?.filter((row) => row.sent_at && new Date(row.sent_at).toDateString() === today).length },
  ]

  return (
    <>
      <PageHeader
        title={t('staff.outbox.title')}
        description={t('staff.outbox.subtitle')}
        actions={
          <button
            type="button"
            onClick={() => {
              setError(null)
              setNotice(null)
              load()
            }}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-mist bg-white px-4 text-[13px] font-medium text-navy hover:border-navy/30">
            <ResetIcon className="size-4" />
            {t('staff.outbox.refresh')}
          </button>
        }
      />
      {error && <Alert tone="error">{error}</Alert>}
      {notice && (
        <div className="mb-4">
          <Alert tone="success">{notice}</Alert>
        </div>
      )}

      {/* O2: bordered tiles, small capital label over a large figure. */}
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tiles.map((tile) => (
          <div key={tile.label} className="rounded-md border border-[#cfe0e8] bg-[#f6fafc] px-4 py-3 text-center">
            <p className="text-[11px] font-medium tracking-[0.08em] text-navy-soft uppercase">{tile.label}</p>
            <p className={`mt-1 text-[26px] font-light tabular-nums ${tile.warn && tile.value ? 'text-danger' : 'text-navy'}`}>{tile.value ?? '-'}</p>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-mist/70 bg-white">
        {/* O5: tabs with a count in a small round badge, underlined when active. */}
        <div role="tablist" aria-label={t('staff.outbox.title')} className="flex gap-6 border-b border-mist px-5">
          {(['waiting', 'sent'] as const).map((key) => {
            const on = tab === key
            const count = (key === 'waiting' ? waiting : sent)?.length
            return (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={on}
                onClick={() => {
                  setTab(key)
                  setOpenId(null)
                }}
                className={`-mb-px inline-flex items-center gap-2 border-b-2 py-3.5 text-[14px] ${on ? 'border-gold font-medium text-[#7a5410]' : 'border-transparent text-navy hover:text-[#7a5410]'}`}
              >
                {key === 'waiting' ? <InboxIcon className="size-4" /> : <TickIcon className="size-4" />}
                {t(`staff.outbox.tabs.${key}`)}
                <span className={`grid min-w-6 place-items-center rounded-full border px-1.5 text-[11px] tabular-nums ${on ? 'border-gold/50 bg-gold/12' : 'border-navy/30'}`}>{count ?? '-'}</span>
              </button>
            )
          })}
        </div>

        <div
          className={`grid ${
            wide && open
              ? roomy
                ? 'grid-cols-[210px_minmax(0,1fr)_400px]'
                : 'grid-cols-[minmax(0,1fr)_400px]'
              : 'grid-cols-[minmax(0,1fr)] lg:grid-cols-[210px_minmax(0,1fr)]'
          }`}
        >
          {/* O1: the kinds of message, each with its count. */}
          <nav
            aria-label={t('staff.outbox.kinds.label')}
            className={`border-b border-mist px-3 py-4 lg:border-r lg:border-b-0 ${wide && open && !roomy ? 'hidden' : ''}`}
          >
            <p className="px-2 text-[18px] font-semibold text-navy">{t('staff.outbox.kinds.label')}</p>
            <ul className="mt-3 flex gap-1 overflow-x-auto lg:block lg:space-y-0.5 lg:overflow-visible">
              {(['all', 'links', 'verification', 'complaints', 'other'] as const).map((key) => {
                const Icon = KIND_ICON[key]
                const on = kind === key
                return (
                  <li key={key} className="shrink-0">
                    <button
                      type="button"
                      onClick={() => setKind(key)}
                      aria-pressed={on}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13.5px] whitespace-nowrap lg:whitespace-normal ${on ? 'bg-paper font-medium text-navy' : 'text-navy-soft hover:bg-paper/60'}`}
                    >
                      <Icon className="size-4 shrink-0" />
                      <span className="flex-1">{t(`staff.outbox.kinds.${key}`)}</span>
                      <span className="text-[12.5px] text-navy-soft tabular-nums">{rows ? kindCounts(key) : '-'}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </nav>

          {/* O1: one table; the open row is tinted. On a phone each row folds into
              two lines (who and when, then the message and its status). */}
          <div className="min-w-0 sm:overflow-x-auto">
            <table className="w-full text-left max-sm:block sm:min-w-[620px] sm:table-fixed">
              <caption className="sr-only">{t(`staff.outbox.tabs.${tab}`)}</caption>
              <thead className="max-sm:sr-only">
                <tr className="border-b border-mist bg-paper/70 text-[12.5px] text-navy-soft">
                  <th scope="col" className="w-[210px] px-4 py-3 font-normal">{t('staff.outbox.columns.to')}</th>
                  <th scope="col" className="px-4 py-3 font-normal">{t('staff.outbox.columns.message')}</th>
                  <th scope="col" className="w-[130px] px-4 py-3 font-normal">{t('staff.outbox.columns.status')}</th>
                  <th scope="col" className="w-[120px] px-4 py-3 font-normal">{t(tab === 'waiting' ? 'staff.outbox.columns.created' : 'staff.outbox.columns.sent')}</th>
                </tr>
              </thead>
              <tbody className="max-sm:block">
                {rows === null &&
                  [0, 1, 2, 3].map((row) => (
                    <tr key={row} className="border-b border-mist/70 max-sm:block">
                      <td colSpan={4} className="px-4 py-3 max-sm:block">
                        <div className="h-8 animate-pulse rounded bg-paper" />
                      </td>
                    </tr>
                  ))}
                {rows !== null && shown.length === 0 && (
                  <tr className="max-sm:block">
                    <td colSpan={4} className="px-4 py-14 text-center text-[14px] text-muted max-sm:block">
                      {tab === 'waiting' ? t('staff.outbox.emptyWaiting') : t('staff.outbox.emptySent')}
                    </td>
                  </tr>
                )}
                {shown.map((row) => {
                  const on = row.id === openId
                  const when = (tab === 'waiting' ? row.created_at : row.sent_at) ?? row.created_at
                  return (
                    <tr
                      key={row.id}
                      onClick={() => setOpenId(row.id)}
                      className={`cursor-pointer border-b border-mist/70 text-[14px] text-navy transition-colors max-sm:grid max-sm:grid-cols-[minmax(0,1fr)_auto] max-sm:items-center max-sm:gap-x-3 max-sm:gap-y-1 max-sm:px-4 max-sm:py-3 ${on ? 'bg-gold/10' : 'hover:bg-paper'}`}
                    >
                      <td className="px-4 py-3 max-sm:order-1 max-sm:min-w-0 max-sm:p-0">
                        <button type="button" className="flex items-center gap-3 text-left" aria-current={on ? 'true' : undefined} onClick={() => setOpenId(row.id)}>
                          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[#e7f6ec] text-[12px] font-semibold text-[#1f7a4d]">
                            {initials(row.recipient_name) || <WhatsAppIcon className="size-4" />}
                          </span>
                          <span className="min-w-0">
                            <span className="block max-w-[150px] truncate">{row.recipient_name || row.phone}</span>
                            <span className="block text-[11.5px] text-muted tabular-nums">{row.recipient_name ? row.phone : t(`staff.outbox.purposes.${row.purpose}`, { defaultValue: row.purpose })}</span>
                          </span>
                        </button>
                      </td>
                      <td className="px-4 py-3 max-sm:order-3 max-sm:min-w-0 max-sm:p-0 max-sm:pl-12 sm:max-w-0">
                        <p className="truncate text-[13.5px]">{t(`staff.outbox.purposes.${row.purpose}`, { defaultValue: row.purpose })}</p>
                        <p className="truncate text-[12px] text-muted">{row.message}</p>
                      </td>
                      <td className="px-4 py-3 max-sm:order-4 max-sm:justify-self-end max-sm:p-0">
                        <StatusChip row={row} />
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap max-sm:order-2 max-sm:p-0 max-sm:text-right">
                        <span className="rounded-md bg-paper px-2 py-1 text-[12px] text-navy-soft tabular-nums">
                          {new Date(when).toDateString() === today ? formatTime(when, i18n.language) : formatShortDate(when, i18n.language)}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {wide && open && (
            <aside className="border-l border-mist">
              <div className="sticky top-[72px]">
                <MessagePane message={open} onClose={() => setOpenId(null)} onSent={markedSent} />
              </div>
            </aside>
          )}
        </div>
      </div>

      {/* Narrower screens: the message slides over from the right. */}
      <AnimatePresence>
        {!wide && open && (
          <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={open.recipient_name || open.phone}>
            <motion.div className="absolute inset-0 bg-navy/45" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpenId(null)} />
            <motion.div
              className="absolute inset-y-0 right-0 w-full max-w-[420px] bg-white shadow-lift"
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', stiffness: 380, damping: 36 }}
            >
              <MessagePane message={open} onClose={() => setOpenId(null)} onSent={markedSent} />
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  )
}

function StatusChip({ row }: { row: OutboxMessage }) {
  const { t } = useTranslation()
  const [tone, key] =
    row.status === 'SENT'
      ? ['bg-success-soft text-success', 'sent']
      : row.overdue
        ? ['bg-danger-soft text-danger', 'overdue']
        : ['bg-gold/15 text-[#7a5410]', 'waiting']
  return <span className={`rounded-md px-2 py-1 text-[12px] whitespace-nowrap ${tone}`}>{t(`staff.outbox.statuses.${key}`)}</span>
}

// O6: the recipient on top, the message as a green outgoing bubble on the
// chat background, and the two actions in the bar at the bottom.
function MessagePane({ message, onClose, onSent }: { message: OutboxMessage; onClose: () => void; onSent: (id: string) => void }) {
  const { t, i18n } = useTranslation()
  const [opened, setOpened] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const waiting = message.status === 'WAITING'

  async function markSent() {
    setBusy(true)
    setError(null)
    try {
      await staffApi.markSent(message.id)
      onSent(message.id)
    } catch (caught) {
      setError(errorMessage(t, caught))
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full min-h-[560px] flex-col">
      <div className="flex items-center gap-3 border-b border-mist px-4 py-3.5">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-[#e7f6ec] text-[13px] font-semibold text-[#1f7a4d]">
          {initials(message.recipient_name) || <WhatsAppIcon className="size-5" />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-medium text-navy">
            {message.recipient_name || message.phone}
            {message.recipient_name && <span className="ml-2 text-[12px] font-normal text-muted tabular-nums">{message.phone}</span>}
          </p>
          <p className="mt-1 truncate">
            <span className="rounded-full border border-[#1f7a4d]/30 bg-[#e7f6ec] px-2 py-0.5 text-[11px] text-[#1f7a4d]">
              {t(`staff.outbox.purposes.${message.purpose}`, { defaultValue: message.purpose })}
            </span>
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label={t('staff.outbox.close')} className="grid size-9 place-items-center rounded-full text-muted hover:bg-paper hover:text-navy">
          <CloseIcon className="size-4" />
        </button>
      </div>

      <div className="flex-1 bg-[#efeae2] px-4 py-5">
        <p className="mx-auto w-fit rounded-md bg-white/80 px-2.5 py-1 text-[11px] text-navy-soft shadow-sm">
          {formatShortDate(message.created_at, i18n.language)} · {message.language === 'en' ? 'English' : 'Kiswahili'}
        </p>
        <div className="mt-4 ml-auto max-w-[88%] rounded-lg rounded-tr-none bg-[#d9fdd3] px-3 py-2.5 shadow-[0_1px_1px_rgba(15,23,42,0.12)]">
          <p className="text-[13.5px] leading-relaxed break-words whitespace-pre-wrap text-[#111b21]">{message.message}</p>
          <p className="mt-1 flex items-center justify-end gap-1 text-[10.5px] text-[#667781]">
            {formatTime(message.sent_at ?? message.created_at, i18n.language)}
            {!waiting && <TickIcon className="size-3.5 text-[#53bdeb]" />}
          </p>
        </div>
      </div>

      <div className="border-t border-mist px-4 py-4">
        {error && (
          <div className="mb-3">
            <Alert tone="error">{error}</Alert>
          </div>
        )}
        {waiting ? (
          confirming ? (
            <div>
              <p className="text-[13.5px] text-navy">{t('staff.outbox.confirmQuestion', { name: message.recipient_name || message.phone })}</p>
              <div className="mt-3 flex gap-2">
                <button type="button" onClick={() => setConfirming(false)} disabled={busy} className="h-11 flex-1 rounded-lg border border-mist text-[14px] text-navy hover:border-navy/30">
                  {t('staff.outbox.notYet')}
                </button>
                <button type="button" onClick={() => void markSent()} disabled={busy} className="inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-navy text-[14px] font-semibold text-white hover:bg-navy-soft disabled:opacity-60">
                  {busy && <span className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden="true" />}
                  {t('staff.outbox.yesSent')}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-2 sm:flex-row">
              <a
                href={message.whatsapp_link}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setOpened(true)}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-[#25d366] sm:flex-1 text-[14px] font-semibold text-[#0b3d22] hover:bg-[#3ee07a]"
              >
                <WhatsAppIcon className="size-4" />
                {t('staff.outbox.openWhatsApp')}
              </a>
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className={`inline-flex h-11 items-center justify-center gap-2 rounded-lg border text-[14px] font-semibold sm:flex-1 ${opened ? 'border-navy bg-navy text-white hover:bg-navy-soft' : 'border-mist text-navy hover:border-navy/30'}`}
              >
                <TickIcon className="size-4" />
                {t('staff.outbox.markSent')}
              </button>
            </div>
          )
        ) : (
          <p className="flex items-center gap-2 text-[13.5px] text-success">
            <TickIcon className="size-4" />
            {t('staff.outbox.sentOn', { date: formatShortDate(message.sent_at ?? message.created_at, i18n.language), time: formatTime(message.sent_at ?? message.created_at, i18n.language) })}
          </p>
        )}
        {waiting && !confirming && <p className="mt-2 text-[12px] text-muted">{t('staff.outbox.howTo')}</p>}
      </div>
    </div>
  )
}
