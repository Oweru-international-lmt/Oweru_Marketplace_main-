import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { initials } from '../lib/initials'
import { ChevronDownIcon, LogOutIcon, UserIcon } from './icons'

export function UserMenu({ onSignOut }: { onSignOut: () => void }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const menuId = useId()

  // Close on outside click or Escape.
  useEffect(() => {
    if (!open) return
    function onPointer(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!user) return null
  const primaryRole = user.roles[0]

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={t('nav.userMenu')}
        className="flex items-center gap-3 rounded-xl p-1.5 pr-2 transition-colors hover:bg-white sm:pr-3"
      >
        <span className="grid size-9 place-items-center rounded-lg bg-navy font-display text-sm font-semibold text-gold-light">
          {initials(user.full_name)}
        </span>
        <span className="hidden text-left sm:block">
          <span className="block max-w-40 truncate text-sm font-semibold text-navy">{user.full_name}</span>
          <span className="block text-xs text-muted">
            {primaryRole ? t(`roleNames.${primaryRole}`, { defaultValue: primaryRole }) : t('account.noRoles')}
          </span>
        </span>
        <ChevronDownIcon className={`size-4 text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            id={menuId}
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 z-30 mt-2 w-64 origin-top-right rounded-2xl bg-white p-2 shadow-[0_20px_50px_-20px_rgba(15,23,42,0.35)] ring-1 ring-mist"
          >
            <div className="px-3 py-2">
              <p className="truncate text-sm font-semibold text-navy">{user.full_name}</p>
              <p className="truncate text-xs text-muted">{user.email}</p>
            </div>
            <div className="my-1 h-px bg-mist" />
            <Link
              to="/account"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-navy hover:bg-paper"
            >
              <UserIcon className="size-4 text-muted" />
              {t('nav.account')}
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false)
                onSignOut()
              }}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-danger hover:bg-danger-soft"
            >
              <LogOutIcon className="size-4" />
              {t('account.signOut')}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
