import type { Language } from '../i18n'
import { request } from './api'
import type { AccountCategory } from './authApi'
import type { ASSIGNABLE_ROLES } from './roles'

const BASE = '/management/authorization'
const ACCOUNTS = '/management/accounts'

export type Role = { code: string; name: string; is_active: boolean }
export type Permission = { code: string; name: string; description: string }
export type RoleAssignment = { role_code: string; is_active: boolean }
export type AccountSummary = {
  id: string
  full_name: string
  account_category: AccountCategory
  is_active: boolean
}

// `version` guards against two managers editing at once: a stale one gets 409.
export type AccountDetail = AccountSummary & { email: string; version: number }

export type StaffAccountInput = {
  role: (typeof ASSIGNABLE_ROLES)[number]
  email: string
  phone: string
  full_name: string
  language: Language
}

// Every change is recorded with a reason. Send either `active` or `full_name`.
export type AccountChange = { version: number; reason: string; active?: boolean; full_name?: string }

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

  // ACC-06 staff accounts (account.manage). The new staff member gets an email
  // link to set their own password.
  createStaffAccount: ({ language, ...input }: StaffAccountInput) =>
    request<{ id: string; version: number }>(`${ACCOUNTS}/`, {
      method: 'POST',
      body: { ...input, preferred_language: language },
      auth: true,
    }),

  account: (userId: string) => request<AccountDetail>(`${ACCOUNTS}/${encodeURIComponent(userId)}/`, { auth: true }),

  // Name changes need account.manage; activating or deactivating needs account.suspend.
  changeAccount: (userId: string, change: AccountChange) =>
    request<{ id: string; is_active: boolean; version: number }>(`${ACCOUNTS}/${encodeURIComponent(userId)}/`, {
      method: 'POST',
      body: change,
      auth: true,
    }),
}
