import { useTranslation } from 'react-i18next'

// `inline` fits inside the auth layout's form column instead of taking the viewport.
export function FullPageLoader({ inline = false }: { inline?: boolean }) {
  const { t } = useTranslation()
  return (
    <div className={`grid place-items-center ${inline ? 'py-24' : 'min-h-dvh bg-paper'}`} role="status">
      <span className="flex flex-col items-center gap-4">
        <span className="size-9 animate-spin rounded-full border-[3px] border-mist border-t-gold" aria-hidden="true" />
        <span className="text-sm text-muted">{t('common.loading')}</span>
      </span>
    </div>
  )
}
