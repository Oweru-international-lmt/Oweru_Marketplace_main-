import { createContext, useContext } from 'react'
import type { RegistrationInput, User } from '../lib/authApi'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export type AuthContextValue = {
  status: AuthStatus
  user: User | null
  signIn: (email: string, password: string) => Promise<User>
  register: (input: RegistrationInput) => Promise<User>
  signOut: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
