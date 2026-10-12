import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert } from '../../../components/Alert'
import { FullPageLoader } from '../../../components/FullPageLoader'
import { ArrowLeftIcon, ChevronDownIcon, TickIcon } from '../../../components/icons'
import { useDocumentTitle } from '../../../hooks/useDocumentTitle'
import { errorMessage } from '../../../lib/errors'
import { servicesApi, type FullCheck } from '../../../lib/servicesApi'
import { staffApi } from '../../../lib/staffApi'

const FORM_ID = 'record-result'

// FUL-07, after W12: a back link, the page name with Cancel and Save on the
// right, then one white form card centred on a grey panel, with the same two
// buttons again at its foot.
export function ResultFormPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('staff.result.title'))
  const { jobId = '' } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState<FullCheck | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [result, setResult] = useState<'' | 'PASSED' | 'PROBLEM_FOUND'>('')
  const [risk, setRisk] = useState('')
  const [notChecked, setNotChecked] = useState('')
  const [reviewed, setReviewed] = useState(false)
  const [final, setFinal] = useState(false)
  const [errors, setErrors] = useState<Partial<Record<'result' | 'risk' | 'confirm', string>>>({})
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const back = `/staff/full-checks/${jobId}`

  useEffect(() => {
    let cancelled = false
    servicesApi
      .fullCheck(jobId)
      .then((loaded) => !cancelled && setJob(loaded))
      .catch((failure: unknown) => !cancelled && setLoadError(errorMessage(t, failure)))
    return () => {
      cancelled = true
    }
  }, [jobId, t])

  async function save(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const found: typeof errors = {}
    if (!result) found.result = t('validation.required')
    if (!risk.trim()) found.risk = t('validation.required')
    if (!reviewed || !final) found.confirm = t('staff.result.confirmRequired')
    setErrors(found)
    if (Object.keys(found).length > 0 || !result) return
    setSaving(true)
    try {
      const items = notChecked
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
      await staffApi.recordResult(jobId, result, risk.trim(), items)
      navigate(back)
    } catch (failure) {
      setSaving(false)
      setError(errorMessage(t, failure))
    }
  }

  if (loadError) return <Alert tone="error">{loadError}</Alert>
  if (!job) return <FullPageLoader inline />

  const field = 'block w-full rounded-[8px] border border-mist bg-white px-3.5 text-[15px] outline-none transition-colors placeholder:text-muted/60 focus:border-gold focus:ring-2 focus:ring-gold/20'
  const invalid = 'border-danger'

  return (
    <div>
      <Link to={back} className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-navy">
        <ArrowLeftIcon className="size-4" />
        {t('staff.result.back', { property: job.property_id })}
      </Link>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-[24px] font-semibold text-navy">{t('staff.result.title')}</h1>
        <div className="flex gap-3">
          <Link to={back} className="inline-flex h-11 items-center rounded-[8px] border border-mist bg-white px-5 text-[15px] text-navy hover:border-navy/30">
            {t('staff.cancel')}
          </Link>
          <button type="submit" form={FORM_ID} disabled={saving} className="inline-flex h-11 items-center rounded-[8px] bg-gold px-5 text-[15px] font-medium text-navy hover:bg-gold-light disabled:opacity-60">
            {saving ? t('listing.sending') : t('staff.result.save')}
          </button>
        </div>
      </div>

      <div className="mt-5 rounded-[10px] bg-[#e6e9ef]/70 px-4 py-6 sm:px-8 sm:py-6">
        <form id={FORM_ID} noValidate onSubmit={(event) => void save(event)} className="mx-auto max-w-[760px] rounded-[6px] bg-white px-4 pt-6 pb-5 sm:px-5">
          <h2 className="text-[19px] text-navy">{t('staff.result.details')}</h2>
          {job.status !== 'UNDER_REVIEW' && (
            <div className="mt-4">
              <Alert tone="error">{t('staff.result.notReady')}</Alert>
            </div>
          )}

          <div className="mt-4">
            <label htmlFor="result" className="mb-2 block text-[15px] text-navy">
              {t('staff.result.result')} <span className="text-danger">*</span>
            </label>
            <div className="relative">
              <select
                id="result"
                value={result}
                onChange={(event) => setResult(event.target.value as 'PASSED' | 'PROBLEM_FOUND')}
                aria-invalid={errors.result ? true : undefined}
                className={`${field} h-11 appearance-none pr-10 ${errors.result ? invalid : ''} ${result ? 'text-navy' : 'text-muted/70'}`}
              >
                <option value="" disabled>
                  {t('staff.result.choose')}
                </option>
                <option value="PASSED" className="text-navy">{t('fullCheck.statuses.PASSED')}</option>
                <option value="PROBLEM_FOUND" className="text-navy">{t('fullCheck.statuses.PROBLEM_FOUND')}</option>
              </select>
              <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-navy/60" />
            </div>
            {errors.result && <p className="mt-1.5 text-sm text-danger">{errors.result}</p>}
          </div>

          <div className="mt-5">
            <label htmlFor="risk" className="mb-2 block text-[15px] text-navy">
              {t('fullCheck.risk')} <span className="text-danger">*</span>
            </label>
            <textarea
              id="risk"
              rows={5}
              maxLength={20000}
              value={risk}
              onChange={(event) => setRisk(event.target.value)}
              placeholder={t('staff.result.typeHere')}
              aria-invalid={errors.risk ? true : undefined}
              className={`${field} resize-y py-3 leading-relaxed text-navy ${errors.risk ? invalid : ''}`}
            />
            {errors.risk && <p className="mt-1.5 text-sm text-danger">{errors.risk}</p>}
          </div>

          <div className="mt-5">
            <label htmlFor="not-checked" className="mb-2 block text-[15px] text-navy">
              {t('fullCheck.notChecked')}
            </label>
            <textarea
              id="not-checked"
              rows={3}
              value={notChecked}
              onChange={(event) => setNotChecked(event.target.value)}
              placeholder={t('staff.result.typeHere')}
              className={`${field} resize-y py-3 leading-relaxed text-navy`}
            />
            <p className="mt-1.5 text-xs text-navy/75">{t('staff.result.notCheckedHint')}</p>
          </div>

          <div className="mt-5 space-y-3">
            <Check id="reviewed" checked={reviewed} onChange={setReviewed} label={t('staff.result.reviewed')} />
            <Check id="final" checked={final} onChange={setFinal} label={t('staff.result.final')} hint={t('staff.result.finalHint')} />
            {errors.confirm && <p className="text-sm text-danger">{errors.confirm}</p>}
          </div>

          {error && (
            <div className="mt-5">
              <Alert tone="error">{error}</Alert>
            </div>
          )}

          <div className="mt-5 flex justify-end gap-3 border-t border-mist pt-4">
            <Link to={back} className="inline-flex h-11 items-center rounded-[8px] border border-mist px-4 text-[15px] text-navy hover:border-navy/30">
              {t('staff.cancel')}
            </Link>
            <button type="submit" disabled={saving} className="inline-flex h-11 items-center rounded-[8px] bg-gold px-5 text-[15px] font-medium text-navy hover:bg-gold-light disabled:opacity-60">
              {saving ? t('listing.sending') : t('staff.result.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function Check({ id, checked, onChange, label, hint }: { id: string; checked: boolean; onChange: (value: boolean) => void; label: string; hint?: string }) {
  return (
    <div>
      <label htmlFor={id} className="flex cursor-pointer items-center gap-2.5 text-[15px] text-navy">
        <input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="peer sr-only" />
        <span className="grid size-[18px] place-items-center rounded-[4px] border border-mist bg-white peer-checked:border-gold peer-checked:bg-gold peer-focus-visible:ring-2 peer-focus-visible:ring-gold/40">
          {checked && <TickIcon className="size-3.5 text-navy" />}
        </span>
        {label}
      </label>
      {hint && <p className="mt-1 pl-7 text-xs text-navy/70">{hint}</p>}
    </div>
  )
}
