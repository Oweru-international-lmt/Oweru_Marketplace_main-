import { useEffect } from 'react'

// Pages opened by a secret link (?token=) must not leak it to sites they link
// to or load from, such as a signed PDF URL or WhatsApp.
export function useNoReferrer() {
  useEffect(() => {
    const meta = document.createElement('meta')
    meta.name = 'referrer'
    meta.content = 'no-referrer'
    document.head.appendChild(meta)
    return () => meta.remove()
  }, [])
}
