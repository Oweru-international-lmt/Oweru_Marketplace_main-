import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { useLocation, useOutlet } from 'react-router-dom'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { PhotoPanel } from './PhotoPanel'
import { sceneFor } from './scenes'

const YEAR = new Date().getFullYear()

// Keeps the outgoing page rendered while AnimatePresence plays its exit.
function FrozenOutlet() {
  const outlet = useOutlet()
  const [frozen] = useState(outlet)
  return frozen
}

export function AuthLayout() {
  const { pathname } = useLocation()
  const scene = sceneFor(pathname)

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <PhotoPanel scene={scene} />

      <main className="flex flex-col px-5 pt-8 pb-6 sm:px-10 lg:min-h-dvh lg:px-14 lg:py-10 xl:px-20">
        <div className="hidden justify-end lg:flex">
          <LanguageSwitch />
        </div>

        <div className="flex flex-1 items-center justify-center lg:py-10">
          <div className="w-full max-w-[420px]">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={pathname}
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
              >
                <FrozenOutlet />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        <p className="mt-12 text-center text-xs text-muted lg:mt-0">
          © {YEAR} Oweru International Ltd
        </p>
      </main>
    </div>
  )
}
