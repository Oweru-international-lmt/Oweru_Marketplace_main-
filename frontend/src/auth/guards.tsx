import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { FullPageLoader } from '../components/FullPageLoader'
import { ForbiddenPage } from '../pages/ForbiddenPage'
import { can } from './access'
import { useAuth } from './useAuth'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, signedOut, user } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <FullPageLoader />
  // Remember the page only when the session ended on its own; after a
  // deliberate sign-out the next person must not land on the previous user's page.
  if (status === 'anonymous') {
    return signedOut ? <Navigate to="/login" replace /> : <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  // ACC-06: a temporary password must be replaced before anything else.
  if (user?.must_change_password) return <Navigate to="/change-password" replace />
  return children
}

// The forced first-sign-in password page. Only for accounts that still have a temporary password.
export function RequirePasswordChange({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  if (status === 'loading') return <FullPageLoader inline />
  if (status === 'anonymous') return <Navigate to="/login" replace />
  if (!user?.must_change_password) return <Navigate to="/account" replace />
  return children
}

// Use inside RequireAuth. Hiding the page is UX only; the API enforces access.
export function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const { user } = useAuth()
  return can(user, permission) ? children : <ForbiddenPage />
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
