import type { User } from '../lib/authApi'

// These only decide what the UI shows. The backend enforces every permission,
// so hiding a link is never the security boundary.
export function can(user: User | null, permission: string): boolean {
  return Boolean(user?.permissions.includes(permission))
}

export function hasRole(user: User | null, role: string): boolean {
  return Boolean(user?.roles.includes(role))
}
