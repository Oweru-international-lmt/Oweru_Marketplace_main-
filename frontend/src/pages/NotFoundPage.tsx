import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { Logo } from '../components/Logo'

export function NotFoundPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('notFound.title'))
  return (
    <div className="grid min-h-dvh place-items-center bg-paper px-5">
      <div className="max-w-md text-center">
        <div className="flex justify-center">
          <Logo />
        </div>
        <p className="mt-10 font-display text-7xl font-semibold text-gold">404</p>
        <h1 className="mt-4 font-display text-2xl font-semibold text-navy">{t('notFound.title')}</h1>
        <p className="mt-2 text-muted">{t('notFound.body')}</p>
        <Link to="/" className="text-link mt-8 inline-block">
          {t('notFound.home')}
        </Link>
      </div>
    </div>
  )
}
