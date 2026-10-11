import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import i18n from '../i18n'
import { ApiError } from '../lib/api'
import { authApi, loadAccess, type RegistrationInput, type User } from '../lib/authApi'
import { clearTokens, getTokens, setTokens } from '../lib/tokens'
import { AuthContext, type AuthStatus } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthStatus>(() => (getTokens() ? 'loading' : 'anonymous'))
  const [signedOut, setSignedOut] = useState(false)

  useEffect(() => {
    if (status !== 'loading') return
    let cancelled = false
    Promise.all([authApi.me(), loadAccess()])
      .then(([profile, access]) => {
        if (cancelled) return
        setUser({ ...profile, ...access })
        setStatus('authenticated')
      })
      .catch((error: unknown) => {
        if (cancelled) return
        // Keep tokens on a network failure so a reload can recover the session.
        if (error instanceof ApiError && error.status === 401) clearTokens()
        setStatus('anonymous')
      })
    return () => {
      cancelled = true
    }
  }, [status])

  const signIn = useCallback(async (email: string, password: string) => {
    const { access, refresh, user: profile } = await authApi.login(email, password)
    setTokens({ access, refresh })
    const signedIn = { ...profile, ...(await loadAccess()) }
    setUser(signedIn)
    setStatus('authenticated')
    setSignedOut(false)
    // ACC-07: the account's language preference applies from sign-in.
    void i18n.changeLanguage(signedIn.language)
    return signedIn
  }, [])

  // The register endpoint returns the profile but no tokens; callers sign in next.
  const register = useCallback((input: RegistrationInput) => authApi.register(input), [])

  // Revoke the refresh token on the server (best effort), then forget it locally.
  const signOut = useCallback(() => {
    const tokens = getTokens()
    if (tokens) void authApi.logout(tokens.refresh).catch(() => undefined)
    clearTokens()
    setUser(null)
    setStatus('anonymous')
    setSignedOut(true)
  }, [])

  const value = useMemo(
    () => ({ status, user, signedOut, signIn, register, signOut, setUser }),
    [status, user, signedOut, signIn, register, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
