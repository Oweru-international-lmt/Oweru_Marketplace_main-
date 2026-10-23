import { AnimatePresence, motion } from 'motion/react'
import { Fragment, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../../components/Alert'
import { ClockIcon, ResetIcon } from '../../../components/icons'
import { adminApi, type Template } from '../../../lib/adminApi'
import { errorMessage } from '../../../lib/errors'
import { formatShortDate } from '../../../lib/format'

// NTF-04. After R21: Swahili and English side by side; {reference},
// {details} and {link} are inserted as whole chips and shown as chips in the
// preview, so they cannot be broken; then the version history.

const VARIABLES = ['reference', 'details', 'link'] as const
type Language = 'sw' | 'en'

function problemsOf(text: string) {
  const problems: string[] = []
  const names = [...text.matchAll(/\{([^{}]*)\}/g)].map((match) => match[1])
  if (names.some((name) => !(VARIABLES as readonly string[]).includes(name))) problems.push('unknown')
  if (text.replace(/\{(reference|details|link)\}/g, '').match(/[{}]/)) problems.push('broken')
  if (!names.includes('link')) problems.push('link')
  if (!text.trim()) problems.push('empty')
  return problems
}

export function TemplateEditor() {
  const { t, i18n } = useTranslation()
  const [rows, setRows] = useState<Template[] | null>(null)
  const [selected, setSelected] = useState('')
  const [text, setText] = useState<Record<Language, string>>({ sw: '', en: '' })
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [busy, setBusy] = useState(false)
  const areas = { sw: useRef<HTMLTextAreaElement>(null), en: useRef<HTMLTextAreaElement>(null) }

  useEffect(() => {
    adminApi.templates().then(
      (list) => {
        setRows(list)
        if (list[0]) {
          setSelected(list[0].key)
          setText({ sw: list[0].sw, en: list[0].en })
        }
      },
      (failure) => setError(errorMessage(t, failure)),
    )
  }, [t])

  const row = rows?.find((item) => item.key === selected)
  const language: Language = i18n.language.startsWith('sw') ? 'sw' : 'en'

  function pick(item: Template) {
    setSelected(item.key)
    setText({ sw: item.sw, en: item.en })
    setSaved('')
    setError('')
  }

  function insert(target: Language, name: string) {
    const area = areas[target].current
    const value = text[target]
    const start = area?.selectionStart ?? value.length
    const end = area?.selectionEnd ?? value.length
    const next = `${value.slice(0, start)}{${name}}${value.slice(end)}`
    setText({ ...text, [target]: next })
    requestAnimationFrame(() => {
      area?.focus()
      const caret = start + name.length + 2
      area?.setSelectionRange(caret, caret)
    })
  }

  async function save() {
    if (!row) return
    setBusy(true)
    setError('')
    try {
      const result = await adminApi.saveTemplate(row.key, text.en, text.sw, row.version)
      const list = await adminApi.templates()
      setRows(list)
      setSaved(t('admin.templates.saved', { version: result.version }))
    } catch (failure) {
      setError(errorMessage(t, failure))
    } finally {
      setBusy(false)
    }
  }

  if (!rows) return error ? <Alert tone="error">{error}</Alert> : <div className="h-40 animate-pulse rounded-xl bg-paper" />
  const problems = { sw: problemsOf(text.sw), en: problemsOf(text.en) }
  const changed = row ? text.sw !== row.sw || text.en !== row.en : false

  return (
    <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)]">
      <ul className="max-h-[560px] space-y-1 overflow-y-auto rounded-xl border border-mist p-1.5">
        {rows.map((item) => (
          <li key={item.key}>
            <button type="button" onClick={() => pick(item)} className={`w-full rounded-lg px-3 py-2 text-left text-[12px] ${item.key === selected ? 'bg-gold/15 font-medium text-[#7a5410]' : 'text-navy-soft hover:bg-paper'}`}>
              <span className="line-clamp-2">{item.title[language]}</span>
              {item.version > 0 && <span className="mt-0.5 block text-[10px] text-muted">{t('admin.templates.edited', { version: item.version })}</span>}
            </button>
          </li>
        ))}
      </ul>

      {row && (
        <div className="min-w-0 rounded-xl border border-mist">
          <div className="flex flex-wrap items-center gap-2 border-b border-mist px-4 py-3">
            <span className="rounded-md bg-gold/15 px-2 py-0.5 font-mono text-[11px] text-[#7a5410]">{row.key}</span>
            <span className="text-[14px] font-semibold text-navy">{row.title[language]}</span>
          </div>
          <div className="grid gap-4 p-4 lg:grid-cols-2">
            {(['sw', 'en'] as Language[]).map((code) => (
              <div key={code} className="min-w-0">
                <p className="text-[12px] font-semibold tracking-wide text-muted uppercase">{t(`admin.templates.language.${code}`)}</p>
                <textarea ref={areas[code]} rows={5} value={text[code]} onChange={(event) => setText({ ...text, [code]: event.target.value })} className="mt-1.5 w-full rounded-lg border border-mist px-3 py-2 text-[13px] leading-relaxed text-navy outline-none focus:border-gold" />
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {VARIABLES.map((name) => (
                    <button key={name} type="button" onClick={() => insert(code, name)} className="inline-flex items-center gap-1 rounded-md border border-mist bg-white px-2 py-1 font-mono text-[11px] text-navy hover:border-gold">
                      <span className="text-[#9a6c12]">{'{•}'}</span>
                      {name}
                    </button>
                  ))}
                </div>
                <div className="mt-3 rounded-lg bg-[#f3f5f9] px-3 py-2.5 text-[13px] leading-relaxed text-navy">
                  <p className="mb-1 text-[10px] font-semibold tracking-wide text-muted uppercase">{t('admin.templates.preview')}</p>
                  <Preview text={text[code]} />
                </div>
                <AnimatePresence>
                  {problems[code].length > 0 && (
                    <motion.ul initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="mt-2 space-y-0.5 text-[12px] text-danger">
                      {problems[code].map((problem) => <li key={problem}>{t(`admin.templates.problems.${problem}`)}</li>)}
                    </motion.ul>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-mist px-4 py-3">
            {error && <div className="w-full"><Alert tone="error">{error}</Alert></div>}
            {saved && !changed && <div className="w-full"><Alert tone="success">{saved}</Alert></div>}
            <button type="button" onClick={() => setText({ sw: row.default.sw, en: row.default.en })} className="inline-flex items-center gap-1.5 text-[12px] text-muted hover:text-navy">
              <ResetIcon className="size-3.5" />
              {t('admin.templates.useDefault')}
            </button>
            <button type="button" disabled={!changed} onClick={() => setText({ sw: row.sw, en: row.en })} className="ml-auto h-9 rounded-[6px] border border-mist px-3 text-[13px] text-navy disabled:opacity-40">{t('admin.cancel')}</button>
            <button type="button" disabled={busy || !changed || problems.sw.length + problems.en.length > 0} onClick={() => void save()} className="h-9 rounded-[6px] bg-gold px-4 text-[13px] font-semibold text-navy disabled:opacity-50">{t('admin.templates.save')}</button>
          </div>
          <div className="border-t border-mist px-4 py-3">
            <p className="flex items-center gap-1.5 text-[12px] font-medium text-navy"><ClockIcon className="size-3.5" />{t('admin.templates.history')}</p>
            {row.history.length === 0 ? (
              <p className="mt-1.5 text-[12px] text-muted">{t('admin.templates.noHistory')}</p>
            ) : (
              <ul className="mt-2 space-y-1.5">
                {row.history.map((item) => (
                  <li key={item.version} className="flex flex-wrap items-center gap-2 text-[12px]">
                    <span className="font-semibold text-navy">{t('admin.rates.version', { version: item.version })}</span>
                    <span className="text-muted">{`${item.actor} · ${formatShortDate(item.created_at, i18n.language)}`}</span>
                    <button type="button" onClick={() => setText({ sw: item.sw, en: item.en })} className="ml-auto text-[#3552a8] hover:underline">{t('admin.templates.load')}</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Preview({ text }: { text: string }) {
  const parts = text.split(/(\{(?:reference|details|link)\})/g)
  return (
    <p className="break-words whitespace-pre-wrap">
      {parts.map((part, index) => {
        const name = part.match(/^\{(reference|details|link)\}$/)?.[1]
        return name ? (
          <span key={index} className="mx-0.5 inline-flex items-center gap-1 rounded-md border border-gold/40 bg-white px-1.5 py-0.5 align-baseline font-mono text-[11px] text-[#7a5410]">
            <span className="text-gold">{'{•}'}</span>
            {name}
          </span>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        )
      })}
    </p>
  )
}
