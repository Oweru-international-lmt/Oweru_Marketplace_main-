import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { LANGUAGES } from '../i18n'

type LanguageSwitchProps = {
  tone?: 'dark' | 'light'
}

export function LanguageSwitch({ tone = 'dark' }: LanguageSwitchProps) {
  const { t, i18n } = useTranslation()
  const light = tone === 'light'

  return (
    <div
      role="group"
      aria-label={t('common.language')}
      className={`inline-flex rounded-full p-1 ${light ? 'bg-white/10 ring-1 ring-white/20' : 'bg-white ring-1 ring-mist'}`}
    >
      {LANGUAGES.map((language) => {
        const active = i18n.language === language
        return (
          <button
            key={language}
            type="button"
            lang={language}
            aria-pressed={active}
            aria-label={t(`common.languageNames.${language}`)}
            title={t(`common.languageNames.${language}`)}
            onClick={() => void i18n.changeLanguage(language)}
            className={`relative min-w-11 rounded-full px-3 py-1.5 font-display text-xs font-semibold tracking-wider uppercase transition-colors ${
              active ? 'text-navy' : light ? 'text-white/80 hover:text-white' : 'text-muted hover:text-navy'
            }`}
          >
            {active && (
              <motion.span
                layoutId={`language-pill-${tone}`}
                className="absolute inset-0 rounded-full bg-gold"
                transition={{ type: 'spring', stiffness: 500, damping: 38 }}
              />
            )}
            <span className="relative">{language}</span>
          </button>
        )
      })}
    </div>
  )
}
