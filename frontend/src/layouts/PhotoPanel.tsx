import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { AnimatePresence, motion } from 'motion/react'
import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { Logo } from '../components/Logo'
import type { Scene } from './scenes'

export function PhotoPanel({ scene }: { scene: Scene }) {
  const { t } = useTranslation()
  const root = useRef<HTMLElement>(null)
  const headline = t(scene.headlineKey)

  // Replays whenever the scene or the language changes the headline.
  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap
          .timeline({ defaults: { ease: 'power3.out' } })
          .from('[data-kicker]', { opacity: 0, y: 10, duration: 0.5 })
          .from('[data-rule]', { scaleX: 0, duration: 0.7, ease: 'power2.inOut' }, '<0.1')
          .from('[data-word]', { yPercent: 110, duration: 0.8, stagger: 0.05 }, '<0.15')
          .from('[data-meta]', { opacity: 0, duration: 0.6 }, '-=0.4')
      })
    },
    { scope: root, dependencies: [headline], revertOnUpdate: true },
  )

  return (
    <section
      ref={root}
      className="relative isolate h-60 overflow-hidden bg-navy sm:h-72 lg:sticky lg:top-0 lg:h-dvh"
    >
      <AnimatePresence initial={false}>
        <motion.img
          key={scene.id}
          src={scene.small}
          srcSet={`${scene.small} 720w, ${scene.large} 1200w`}
          sizes="(min-width: 1024px) 52vw, 100vw"
          alt=""
          fetchPriority="high"
          initial={{ opacity: 0, scale: 1.08 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ opacity: { duration: 0.9 }, scale: { duration: 7, ease: 'easeOut' } }}
          className="absolute inset-0 -z-20 size-full object-cover"
        />
      </AnimatePresence>
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-gradient-to-t from-navy via-navy/55 to-navy/25 lg:via-navy/40 lg:to-navy/10"
      />

      <div className="flex items-center justify-between p-5 sm:p-8 lg:p-12">
        <Logo tone="light" />
        <div className="lg:hidden">
          <LanguageSwitch tone="light" />
        </div>
      </div>

      <div className="absolute inset-x-0 bottom-0 p-5 sm:p-8 lg:p-12 xl:p-16">
        <p data-kicker className="font-display text-[11px] font-medium tracking-[0.35em] text-gold-light uppercase">
          {t('panel.kicker')}
        </p>
        <span data-rule className="mt-3 mb-4 block h-0.5 w-14 origin-left bg-gold lg:mb-6" aria-hidden="true" />
        <h2 className="max-w-xl font-display text-2xl leading-[1.15] font-medium text-white sm:text-3xl lg:text-5xl">
          {headline.split(' ').map((word, index) => (
            <span key={`${word}-${index}`} className="inline-block overflow-hidden pb-1 align-bottom">
              <span data-word className="mr-[0.25em] inline-block">
                {word}
              </span>
            </span>
          ))}
        </h2>
        <p data-meta className="mt-10 hidden items-center justify-between text-xs text-white/65 lg:flex">
          <span>{t('common.location')}</span>
          <span>{t('common.photoCredit', { name: scene.credit })}</span>
        </p>
      </div>
    </section>
  )
}
