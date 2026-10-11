import { useSyncExternalStore } from 'react'

// True while the CSS media query matches; re-renders when it changes.
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}

// Tailwind's lg breakpoint: desktop layouts from here up.
export const DESKTOP = '(min-width: 1024px)'
