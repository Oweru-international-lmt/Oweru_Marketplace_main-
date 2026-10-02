import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en'
import sw from './sw'

export const LANGUAGES = ['sw', 'en'] as const
export type Language = (typeof LANGUAGES)[number]

const STORAGE_KEY = 'oweru.language'

export function isLanguage(value: unknown): value is Language {
  return value === 'sw' || value === 'en'
}

function storedLanguage(): Language {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (isLanguage(value)) return value
  } catch {
    // Storage can be blocked; Swahili is the default (SRD NFR-09).
  }
  return 'sw'
}

void i18n.use(initReactI18next).init({
  resources: { sw: { translation: sw }, en: { translation: en } },
  lng: storedLanguage(),
  fallbackLng: 'sw',
  interpolation: { escapeValue: false },
})

document.documentElement.lang = i18n.language
i18n.on('languageChanged', (language) => {
  document.documentElement.lang = language
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // Ignore: the choice just won't survive a reload.
  }
})

export default i18n
