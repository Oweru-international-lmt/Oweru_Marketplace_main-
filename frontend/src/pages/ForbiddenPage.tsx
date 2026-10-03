import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Card } from '../components/Card'
import { LockIcon } from '../components/icons'
import { PageBody, PageHero } from '../components/PageHero'

export function ForbiddenPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHero kicker="403" title={t('forbidden.title')} />
      <PageBody>
        <Card>
          <div className="flex gap-4">
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-gold/15 text-navy">
              <LockIcon className="size-6" />
            </span>
            <div>
              <p className="leading-relaxed text-muted">{t('forbidden.body')}</p>
              <Link to="/account" className="text-link mt-4 inline-block text-sm">
                {t('forbidden.back')}
              </Link>
            </div>
          </div>
        </Card>
      </PageBody>
    </>
  )
}
