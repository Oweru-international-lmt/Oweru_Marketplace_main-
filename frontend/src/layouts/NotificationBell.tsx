import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { BellIcon, CheckIcon } from '../components/icons'
import { formatShortDate } from '../lib/format'
import { peopleApi, type ScreenNotice } from '../lib/peopleApi'

// NTF-01: on-screen notices in the top bar; opening one marks it read and
// goes to the page its message links to.

const UUID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi

function parse(message: string) {
  const link = message.match(/(?:https?:\/\/\S+|(?:^|\s)(\/[\w\-/?=&.%]+))\s*$/)
  let path: string | null = null
  if (link) {
    const raw = (link[1] ?? link[0]).trim()
    try {
      const url = new URL(raw, window.location.origin)
      path = url.origin === window.location.origin ? `${url.pathname}${url.search}` : null
    } catch {
      path = null
    }
  }
  const text = (link ? message.slice(0, link.index) : message).replace(UUID, '').replace(/\s{2,}/g, ' ').replace(/\s+\./g, '.').trim()
  return { text, path }
}

export function NotificationBell() {
  const { t, i18n } = useTranslation()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [rows, setRows] = useState<ScreenNotice[]>([])
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let live = true
    peopleApi.notifications().then((list) => live && setRows(list), () => undefined)
    return () => {
      live = false
    }
  }, [pathname])

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  const unread = rows.filter((row) => !row.read_at).length

  async function read(row: ScreenNotice) {
    const { path } = parse(row.message)
    if (path) {
      setOpen(false)
      navigate(path)
    }
    if (row.read_at) return
    try {
      const result = await peopleApi.markRead(row.id)
      setRows((list) => list.map((item) => (item.id === row.id ? { ...item, read_at: result.read_at } : item)))
    } catch {
      // It stays unread; nothing else depends on it.
    }
  }

  return (
    <div ref={box} className="relative">
      <button type="button" aria-label={t('bell.label', { count: unread })} aria-expanded={open} onClick={() => setOpen((value) => !value)} className="relative grid size-10 place-items-center rounded-full text-navy/70 hover:bg-paper hover:text-navy">
        <BellIcon className="size-5" />
        <AnimatePresence>
          {unread > 0 && (
            <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} className="absolute top-1.5 right-1.5 grid min-w-4 place-items-center rounded-full bg-[#c2410c] px-1 text-[10px] leading-4 font-semibold text-white">
              {unread > 9 ? '9+' : unread}
            </motion.span>
          )}
        </AnimatePresence>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="absolute right-0 z-40 mt-2 w-[min(340px,calc(100vw-2rem))] overflow-hidden rounded-xl border border-mist bg-white shadow-lift">
            <p className="border-b border-mist px-4 py-3 text-[14px] font-semibold text-navy">{t('bell.title')}</p>
            {rows.length === 0 ? (
              <p className="px-4 py-8 text-center text-[13px] text-muted">{t('bell.empty')}</p>
            ) : (
              <ul className="max-h-[360px] overflow-y-auto">
                {rows.slice(0, 30).map((row) => (
                  <li key={row.id}>
                    <button type="button" onClick={() => void read(row)} className={`flex w-full gap-3 border-b border-mist/60 px-4 py-3 text-left last:border-b-0 ${row.read_at ? 'bg-white' : 'bg-[#fffaf0]'}`}>
                      <span className={`mt-1.5 size-2 shrink-0 rounded-full ${row.read_at ? 'bg-transparent' : 'bg-gold'}`} />
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13px] leading-snug text-navy">{parse(row.message).text}</span>
                        <span className="mt-1 flex items-center gap-1 text-[11px] text-muted">
                          {formatShortDate(row.created_at, i18n.language)}
                          {row.read_at && <CheckIcon className="size-3" />}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
