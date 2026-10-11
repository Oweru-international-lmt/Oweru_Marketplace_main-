import { createContext, useContext } from 'react'
import type { Profile, RegistrationInput, User } from '../lib/authApi'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export type AuthContextValue = {
  status: AuthStatus
  user: User | null
  // True after the user pressed sign out (as opposed to an expired session).
  signedOut: boolean
  signIn: (email: string, password: string) => Promise<User>
  register: (input: RegistrationInput) => Promise<Profile>
  signOut: () => void
  // After a profile edit returns the updated user.
  setUser: (user: User) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
