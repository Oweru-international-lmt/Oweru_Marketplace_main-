import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../components/Alert'
import { Card } from '../components/Card'
import { PageHeader } from '../components/PageHeader'
import { initials } from '../lib/initials'
import type { DeletionRequest } from '../lib/authApi'
import { errorMessage } from '../lib/errors'
import { managementApi, type ManagedDeletionRequest } from '../lib/managementApi'

const TABS: DeletionRequest['status'][] = ['pending', 'completed', 'declined', 'cancelled']

// ACC-08: Management decides deletion requests. Completing deactivates the
// account and ends its sessions; records are kept as the law requires.
export function ManagementDeletionsPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<DeletionRequest['status']>('pending')
  const [rows, setRows] = useState<ManagedDeletionRequest[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    managementApi
      .deletionRequests(tab)
      .then((data) => !cancelled && setRows(data))
      .catch((err: unknown) => !cancelled && setError(errorMessage(t, err)))
    return () => {
      cancelled = true
    }
    // `t` is left out on purpose: a language switch should not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  function selectTab(next: DeletionRequest['status']) {
    if (next === tab) return
    setRows(null)
    setError(null)
    setNotice(null)
    setTab(next)
  }

  function resolved(id: string, text: string) {
    setRows((current) => current?.filter((row) => row.id !== id) ?? null)
    setNotice(text)
  }

  return (
    <>
      <PageHeader eyebrow={t('deletionsPage.kicker')} title={t('deletionsPage.title')} description={t('deletionsPage.intro')} />

      <div className="mb-6 flex gap-1 overflow-x-auto rounded-xl bg-white p-1 ring-1 ring-mist [scrollbar-width:none] sm:inline-flex">
        {TABS.map((status) => (
          <button
            key={status}
            type="button"
            onClick={() => selectTab(status)}
            aria-pressed={tab === status}
            className={`relative shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              tab === status ? 'text-navy' : 'text-muted hover:text-navy'
            }`}
          >
            {tab === status && (
              <motion.span layoutId="deletion-tab" className="absolute inset-0 rounded-lg bg-gold/15" transition={{ type: 'spring', stiffness: 500, damping: 40 }} />
            )}
            <span className="relative">{t(`deletionsPage.${status}`)}</span>
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {notice && <Alert tone="success">{notice}</Alert>}
        {error ? (
          <Alert tone="error">{error}</Alert>
        ) : rows === null ? (
          <div className="h-32 animate-pulse rounded-2xl bg-white ring-1 ring-mist" aria-hidden="true" />
        ) : rows.length === 0 ? (
          <Card>
            <p className="text-sm text-muted">{t('deletionsPage.empty')}</p>
          </Card>
        ) : (
          <AnimatePresence initial={false}>
            {rows.map((row) => (
              <motion.div key={row.id} layout exit={{ opacity: 0, height: 0 }}>
                <RequestCard row={row} onResolved={resolved} />
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </>
  )
}

function RequestCard({ row, onResolved }: { row: ManagedDeletionRequest; onResolved: (id: string, text: string) => void }) {
  const { t, i18n } = useTranslation()
  const [mode, setMode] = useState<'idle' | 'complete' | 'decline'>('idle')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const formatDate = (value: string) =>
    new Intl.DateTimeFormat(i18n.language === 'sw' ? 'sw-TZ' : 'en-GB', { dateStyle: 'long' }).format(new Date(value))

  async function resolve(decision: 'completed' | 'declined') {
    if (decision === 'declined' && !note.trim()) {
      setError(t('server.reasonRequired'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      await managementApi.resolveDeletion(row.id, decision, note.trim())
      onResolved(row.id, decision === 'completed' ? t('deletionsPage.completedDone') : t('deletionsPage.declinedDone'))
    } catch (err) {
      setError(errorMessage(t, err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card delay={0}>
      <div className="flex flex-wrap items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-navy font-display font-semibold text-gold-light">
          {initials(row.account.full_name)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-display text-base font-semibold text-navy">{row.account.full_name}</p>
          <p className="text-xs text-muted">
            {t(`categories.${row.account.account_category}`)} · {t('deletionsPage.requested', { date: formatDate(row.requested_at) })}
            {row.resolved_at && ` · ${t('deletionsPage.resolved', { date: formatDate(row.resolved_at) })}`}
          </p>
          <p className="mt-3 text-sm leading-relaxed text-navy">{row.reason || <span className="text-muted">{t('deletionsPage.noReason')}</span>}</p>
          {row.resolution_note && <p className="mt-2 rounded-lg bg-paper px-3 py-2 text-sm text-muted">{row.resolution_note}</p>}
        </div>
      </div>

      {row.status === 'pending' && (
        <div className="mt-5 border-t border-mist pt-5">
          {error && (
            <div className="mb-4">
              <Alert tone="error">{error}</Alert>
            </div>
          )}
          {mode === 'idle' && (
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setMode('complete')}
                className="h-10 rounded-lg bg-danger px-4 text-sm font-semibold text-white hover:bg-danger/90"
              >
                {t('deletionsPage.complete')}
              </button>
              <button
                type="button"
                onClick={() => setMode('decline')}
                className="h-10 rounded-lg px-4 text-sm font-medium text-navy ring-1 ring-mist hover:bg-paper"
              >
                {t('deletionsPage.decline')}
              </button>
            </div>
          )}
          {mode !== 'idle' && (
            <div className="space-y-3">
              {mode === 'complete' ? (
                <p className="text-sm text-danger">{t('deletionsPage.confirmComplete')}</p>
              ) : null}
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-navy">{t('deletionsPage.note')}</span>
                <textarea
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={2}
                  maxLength={2000}
                  className="block w-full rounded-xl border border-mist bg-white px-4 py-3 text-[15px] text-navy outline-none focus:border-gold focus:ring-4 focus:ring-gold/20"
                />
              </label>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void resolve(mode === 'complete' ? 'completed' : 'declined')}
                  className={`h-10 rounded-lg px-4 text-sm font-semibold disabled:opacity-60 ${
                    mode === 'complete' ? 'bg-danger text-white hover:bg-danger/90' : 'bg-navy text-white hover:bg-navy-soft'
                  }`}
                >
                  {mode === 'complete' ? t('deletionsPage.confirmYes') : t('deletionsPage.decline')}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setMode('idle')
                    setError(null)
                  }}
                  className="h-10 rounded-lg px-4 text-sm font-medium text-navy ring-1 ring-mist hover:bg-paper"
                >
                  {t('profile.cancel')}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
