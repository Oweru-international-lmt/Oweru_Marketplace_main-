import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import i18n from '../i18n'
import { ApiError } from '../lib/api'
import { authApi, type RegistrationInput, type User } from '../lib/authApi'
import { clearTokens, getTokens, setTokens } from '../lib/tokens'
import { AuthContext, type AuthStatus } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthStatus>(() => (getTokens() ? 'loading' : 'anonymous'))

  useEffect(() => {
    if (status !== 'loading') return
    let cancelled = false
    authApi
      .me()
      .then((me) => {
        if (cancelled) return
        setUser(me)
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
    const { access, refresh, user: signedIn } = await authApi.login(email, password)
    setTokens({ access, refresh })
    setUser(signedIn)
    setStatus('authenticated')
    // ACC-07: the account's language preference applies from sign-in.
    void i18n.changeLanguage(signedIn.language)
    return signedIn
  }, [])

  // The register endpoint returns the profile but no tokens; callers sign in next.
  const register = useCallback((input: RegistrationInput) => authApi.register(input), [])

  // No logout endpoint exists yet, so signing out only forgets the tokens.
  const signOut = useCallback(() => {
    clearTokens()
    setUser(null)
    setStatus('anonymous')
  }, [])

  const value = useMemo(
    () => ({ status, user, signIn, register, signOut }),
    [status, user, signIn, register, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
