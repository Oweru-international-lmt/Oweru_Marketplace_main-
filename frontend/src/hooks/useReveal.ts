import type { RefObject } from 'react'
import { gsap, MOTION_OK, useGSAP } from '../lib/gsap'

// Fades [data-reveal] blocks inside `scope` up as they scroll into view.
export function useReveal(scope: RefObject<HTMLElement | null>, dependencies: unknown[] = []) {
  useGSAP(
    () => {
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach((element) => {
          gsap.from(element, {
            opacity: 0,
            y: 22,
            duration: 0.6,
            ease: 'power3.out',
            scrollTrigger: { trigger: element, start: 'top 90%', once: true },
          })
        })
      })
    },
    { scope, dependencies, revertOnUpdate: true },
  )
}
