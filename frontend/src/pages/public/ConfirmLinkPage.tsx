import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { ClockIcon, CloseIcon, TickIcon, WhatsAppIcon } from '../../components/icons'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ApiError } from '../../lib/api'
import { whatsappLink } from '../../lib/config'
import { confirmApi, type Confirmation } from '../../lib/confirmApi'
import { errorMessage } from '../../lib/errors'

type State = { kind: 'loading' } | { kind: 'ready'; confirmation: Confirmation } | { kind: 'done' } | { kind: 'invalid' } | { kind: 'error'; message: string }

// OWNER_CONFIRMATION_URL lands here with ?delivery=&token= (ACC-01). The phone
// link confirms the lister's WhatsApp number; other link types are opened by
// their own pages as those are built. Same card as the lister's identity
// status screen (L7).
export function ConfirmLinkPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const delivery = params.get('delivery') ?? ''
  const token = params.get('token') ?? ''
  const [state, setState] = useState<State>(() => (delivery && token ? { kind: 'loading' } : { kind: 'invalid' }))
  const [busy, setBusy] = useState(false)
  useDocumentTitle(t('confirmLink.title'))

  useEffect(() => {
    if (!delivery || !token) return
    let live = true
    confirmApi.open(delivery, token).then(
      (confirmation) => live && setState({ kind: 'ready', confirmation }),
      (caught) => live && setState(caught instanceof ApiError && (caught.status === 403 || caught.status === 404) ? { kind: 'invalid' } : { kind: 'error', message: errorMessage(t, caught) }),
    )
    return () => {
      live = false
    }
  }, [delivery, token, t])

  async function confirm() {
    setBusy(true)
    try {
      await confirmApi.decide(delivery, token, 'CONFIRM')
      setState({ kind: 'done' })
    } catch (caught) {
      setState(caught instanceof ApiError && caught.status === 403 ? { kind: 'invalid' } : { kind: 'error', message: errorMessage(t, caught) })
    } finally {
      setBusy(false)
    }
  }

  const phone = state.kind === 'ready' && state.confirmation.purpose === 'PHONE'
  const tone =
    state.kind === 'done' ? 'bg-success-soft text-success' : state.kind === 'invalid' || state.kind === 'error' ? 'bg-danger-soft text-danger' : 'bg-gold/15 text-[#9a6c12]'

  return (
    <div className="mx-auto w-full max-w-[420px] px-4 py-10 sm:py-16">
      <div className="flex min-h-[520px] flex-col items-center rounded-[28px] bg-white px-6 pt-14 pb-8 text-center shadow-[0_20px_50px_-24px_rgba(15,23,42,0.35)] ring-1 ring-mist">
        <span className={`grid size-20 place-items-center rounded-full ${tone}`}>
          {state.kind === 'done' ? (
            <TickIcon className="size-9" />
          ) : state.kind === 'invalid' || state.kind === 'error' ? (
            <CloseIcon className="size-9" />
          ) : state.kind === 'loading' ? (
            <span className="size-7 animate-spin rounded-full border-2 border-gold/25 border-t-gold" aria-label={t('common.loading')} />
          ) : phone ? (
            <WhatsAppIcon className="size-9" />
          ) : (
            <ClockIcon className="size-9" />
          )}
        </span>

        {state.kind === 'loading' && <h1 className="mt-7 text-[22px] font-bold text-navy">{t('confirmLink.checking')}</h1>}

        {state.kind === 'ready' && phone && (
          <>
            <h1 className="mt-7 text-[24px] leading-tight font-bold text-navy">{t('confirmLink.phoneTitle')}</h1>
            <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{t('confirmLink.phoneBody')}</p>
            {state.confirmation.context.phone && (
              <p className="mt-6 mb-6 w-full rounded-xl border border-mist px-4 py-3 text-[18px] font-semibold tracking-wide text-navy tabular-nums">{state.confirmation.context.phone}</p>
            )}
            <button
              type="button"
              onClick={() => void confirm()}
              disabled={busy}
              className="mt-auto inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-gold text-[15px] font-semibold text-navy hover:bg-gold-light disabled:opacity-70"
            >
              {busy && <span className="size-4 animate-spin rounded-full border-2 border-navy/25 border-t-navy" aria-hidden="true" />}
              {t('confirmLink.confirm')}
            </button>
            <p className="mt-3 text-[12.5px] text-muted">{t('confirmLink.notMine')}</p>
          </>
        )}

        {state.kind === 'ready' && !phone && (
          <>
            <h1 className="mt-7 text-[22px] leading-tight font-bold text-navy">{t('confirmLink.otherTitle')}</h1>
            <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{t('confirmLink.otherBody')}</p>
            <Help />
          </>
        )}

        {state.kind === 'done' && (
          <>
            <h1 className="mt-7 text-[24px] leading-tight font-bold text-navy">{t('confirmLink.doneTitle')}</h1>
            <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{t('confirmLink.doneBody')}</p>
            <Link to="/lister" className="mt-auto inline-flex h-12 w-full items-center justify-center rounded-xl bg-navy text-[15px] font-semibold text-white hover:bg-navy-soft">
              {t('confirmLink.toListings')}
            </Link>
          </>
        )}

        {state.kind === 'invalid' && (
          <>
            <h1 className="mt-7 text-[22px] leading-tight font-bold text-navy">{t('confirmLink.invalidTitle')}</h1>
            <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{t('confirmLink.invalidBody')}</p>
            <Link to="/lister/identity" className="mt-auto inline-flex h-12 w-full items-center justify-center rounded-xl bg-navy text-[15px] font-semibold text-white hover:bg-navy-soft">
              {t('confirmLink.newLink')}
            </Link>
          </>
        )}

        {state.kind === 'error' && (
          <>
            <h1 className="mt-7 text-[22px] leading-tight font-bold text-navy">{t('confirmLink.errorTitle')}</h1>
            <p className="mt-3 max-w-[310px] text-[14.5px] leading-relaxed text-navy-soft">{state.message}</p>
            <Help />
          </>
        )}
      </div>
    </div>
  )
}

function Help() {
  const { t } = useTranslation()
  return (
    <a
      href={whatsappLink(t('confirmLink.helpMessage'))}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-auto inline-flex h-11 items-center gap-2 rounded-xl border border-mist px-5 text-[14px] font-medium text-navy hover:border-navy-soft/40"
    >
      <WhatsAppIcon className="size-4" />
      {t('nav.helpAction')}
    </a>
  )
}
