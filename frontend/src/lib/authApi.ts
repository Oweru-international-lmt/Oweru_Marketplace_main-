import { isLanguage, type Language } from '../i18n'
import { request } from './api'
import type { Tokens } from './tokens'

export type AccountCategory = 'public' | 'operational'

// Mirrors accounts.serializers.UserPublicSerializer / UserPrivateProfileSerializer.
type ApiProfile = {
  id: string
  email: string
  phone: string
  full_name: string
  preferred_language: string
  is_email_verified: boolean
  created_at: string
}

export type Profile = {
  id: string
  email: string
  phone: string
  full_name: string
  language: Language
  email_verified: boolean
  created_at: string
}

// The profile endpoints don't report roles or permissions, so `access` is
// learned separately (see loadAccess). It only decides what the UI shows;
// the API still checks every request.
export type Access = { roles: string[]; permissions: string[] }
export type User = Profile & Access

export const NO_ACCESS: Access = { roles: [], permissions: [] }

function toProfile(raw: ApiProfile): Profile {
  return {
    id: raw.id,
    email: raw.email,
    phone: raw.phone,
    full_name: raw.full_name,
    language: isLanguage(raw.preferred_language) ? raw.preferred_language : 'sw',
    email_verified: raw.is_email_verified,
    created_at: raw.created_at,
  }
}

export type RegistrationInput = {
  email: string
  phone: string
  full_name: string
  password: string
  language: Language
}

export type ProfileChanges = Partial<Pick<Profile, 'full_name' | 'language'>>

// Mirrors accounts.serializers.AccountDeletionRequestSerializer.
export type DeletionRequest = {
  id: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED'
  reason: string
  requested_at: string
}

export const authApi = {
  register: async (input: RegistrationInput) => {
    const { language, ...rest } = input
    return toProfile(
      await request<ApiProfile>('/auth/register/', { method: 'POST', body: { ...rest, preferred_language: language } }),
    )
  },

  login: async (email: string, password: string) => {
    const { user, ...tokens } = await request<Tokens & { user: ApiProfile }>('/auth/login/', {
      method: 'POST',
      body: { email, password },
    })
    return { ...tokens, user: toProfile(user) }
  },

  logout: (refresh: string) => request<null>('/auth/logout/', { method: 'POST', body: { refresh } }),

  me: async () => toProfile(await request<ApiProfile>('/auth/me/', { auth: true })),

  updateProfile: async ({ language, ...changes }: ProfileChanges) =>
    toProfile(
      await request<ApiProfile>('/users/me/', {
        method: 'PATCH',
        body: { ...changes, ...(language ? { preferred_language: language } : {}) },
        auth: true,
      }),
    ),

  // The server ends every session, this one included, so the caller signs out.
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ detail: string }>('/auth/password/change/', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword, new_password_confirm: newPassword },
      auth: true,
    }),

  requestPasswordReset: (email: string) =>
    request<{ detail: string }>('/auth/password/reset/', { method: 'POST', body: { email } }),

  confirmPasswordReset: (uid: string, token: string, newPassword: string) =>
    request<{ detail: string }>('/auth/password/reset/confirm/', {
      method: 'POST',
      body: { uid, token, new_password: newPassword },
    }),

  verifyEmail: (token: string) => request<{ detail: string }>('/auth/email/verify/', { method: 'POST', body: { token } }),

  resendEmailConfirmation: () => request<{ detail: string }>('/auth/email/resend/', { method: 'POST', auth: true }),

  // Returns the existing pending request if there already is one.
  requestDeletion: (reason: string) =>
    request<DeletionRequest>('/users/me/deletion-request/', { method: 'POST', body: { reason }, auth: true }),
}

// Stopgap until /auth/me reports roles. Two probes, run together:
// - the Management role's grants answer only for active Management with
//   authorization.view;
// - the complaints desk answers only for complaint.handle, which Verifiers
//   and Management hold (roles catalog).
// Any failure just hides those menus; the API still checks every request.
export async function loadAccess(): Promise<Access> {
  const [grants, desk] = await Promise.allSettled([
    request<{ code: string }[]>('/management/authorization/roles/management/permissions/', { auth: true }),
    request<unknown[]>('/management/complaints/', { auth: true }),
  ])
  const handlesComplaints = desk.status === 'fulfilled'
  if (grants.status === 'fulfilled') {
    const permissions = grants.value.map((grant) => grant.code)
    return { roles: ['management'], permissions: handlesComplaints ? [...new Set([...permissions, 'complaint.handle'])] : permissions }
  }
  if (handlesComplaints) return { roles: ['verifier'], permissions: ['complaint.handle', 'verification.record_result'] }
  return NO_ACCESS
}
