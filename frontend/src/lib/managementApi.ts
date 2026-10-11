import type { Language } from '../i18n'
import { request } from './api'
import type { AccountCategory, DeletionRequest, ProfileChanges } from './authApi'

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
  must_change_password: boolean
}

export type StaffAccountInput = { email: string; phone: string; full_name: string; language: Language }
export type TemporaryPasswordResult = { account: AccountSummary; temporary_password: string }
export type ManagedDeletionRequest = DeletionRequest & { account: AccountSummary }

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

  // ACC-06 staff accounts (account.manage / account.suspend).
  createStaffAccount: (input: StaffAccountInput) =>
    request<TemporaryPasswordResult>(`${ACCOUNTS}/`, { method: 'POST', body: input, auth: true }),

  updateStaffAccount: (userId: string, changes: ProfileChanges) =>
    request<AccountSummary>(`${ACCOUNTS}/${encodeURIComponent(userId)}/`, { method: 'PATCH', body: changes, auth: true }),

  issueTemporaryPassword: (userId: string) =>
    request<TemporaryPasswordResult>(`${ACCOUNTS}/${encodeURIComponent(userId)}/temporary-password/`, {
      method: 'POST',
      auth: true,
    }),

  setAccountActive: (userId: string, active: boolean, reason: string) =>
    request<AccountSummary>(`${ACCOUNTS}/${encodeURIComponent(userId)}/${active ? 'reactivate' : 'deactivate'}/`, {
      method: 'POST',
      body: { reason },
      auth: true,
    }),

  // ACC-08 deletion requests.
  deletionRequests: (status: DeletionRequest['status']) =>
    request<ManagedDeletionRequest[]>(`${ACCOUNTS}/deletion-requests/?status=${status}`, { auth: true }),

  resolveDeletion: (requestId: string, decision: 'completed' | 'declined', note: string) =>
    request<ManagedDeletionRequest>(`${ACCOUNTS}/deletion-requests/${encodeURIComponent(requestId)}/resolve/`, {
      method: 'POST',
      body: { decision, note },
      auth: true,
    }),
}
