import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { FullPageLoader } from '../components/FullPageLoader'
import { useAuth } from './useAuth'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <FullPageLoader />
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

// Sign-in, sign-up and forgot-password make no sense once signed in.
export function GuestOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'loading') return <FullPageLoader inline />
  if (status === 'authenticated') return <Navigate to="/account" replace />
  return children
}

export function HomeRedirect() {
  const { status } = useAuth()
  if (status === 'loading') return <FullPageLoader />
  return <Navigate to={status === 'authenticated' ? '/account' : '/login'} replace />
}
