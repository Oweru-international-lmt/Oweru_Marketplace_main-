import { request } from './api'
import type { AccountCategory } from './authApi'

const BASE = '/management/authorization'

export type Role = { code: string; name: string; is_active: boolean }
export type Permission = { code: string; name: string; description: string }
export type RoleAssignment = { role_code: string; is_active: boolean }
export type AccountSummary = {
  id: string
  full_name: string
  account_category: AccountCategory
  is_active: boolean
}

// All endpoints need JWT plus an active Management role and the named permission
// (see doc/BACKEND_AUTHORIZATION.md).
export const managementApi = {
  roles: () => request<Role[]>(`${BASE}/roles/`, { auth: true }),

  permissions: () => request<Permission[]>(`${BASE}/permissions/`, { auth: true }),

  rolePermissions: (roleCode: string) =>
    request<Permission[]>(`${BASE}/roles/${encodeURIComponent(roleCode)}/permissions/`, { auth: true }),

  // Exact email match only; returns zero or one account.
  findAccount: (email: string) =>
    request<AccountSummary[]>(`${BASE}/users/?email=${encodeURIComponent(email)}`, { auth: true }),

  accountRoles: (userId: string) =>
    request<RoleAssignment[]>(`${BASE}/users/${encodeURIComponent(userId)}/roles/`, { auth: true }),

  assignRole: (userId: string, roleCode: string) =>
    request<RoleAssignment>(`${BASE}/users/${encodeURIComponent(userId)}/roles/assign/`, {
      method: 'POST',
      body: { role_code: roleCode },
      auth: true,
    }),

  revokeRole: (userId: string, roleCode: string) =>
    request<null>(`${BASE}/users/${encodeURIComponent(userId)}/roles/revoke/`, {
      method: 'POST',
      body: { role_code: roleCode },
      auth: true,
    }),

  setOutboxSend: (roleCode: string, enabled: boolean) =>
    request<{ enabled: boolean }>(`${BASE}/roles/${encodeURIComponent(roleCode)}/outbox-send/`, {
      method: 'PUT',
      body: { enabled },
      auth: true,
    }),
}
