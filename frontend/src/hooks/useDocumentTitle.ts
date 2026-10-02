import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

export function useDocumentTitle(title: string) {
  const { t } = useTranslation()
  const brand = t('common.brand')
  useEffect(() => {
    document.title = title ? `${title} · ${brand}` : brand
  }, [title, brand])
}
