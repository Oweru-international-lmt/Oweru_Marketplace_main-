import { isLanguage, type Language } from '../i18n'
import { ApiError, request } from './api'
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

// Stopgap until /auth/me reports roles. Three probes, run together:
// - the Management role's grants answer only for active Management with
//   authorization.view;
// - the complaints desk answers only for complaint.handle, which Verifiers
//   and Management hold (roles catalog);
// - the lister's identity answers 200, or 404 before they start, only for an
//   active Owner or Agent; everyone else gets 403;
// - the Marketer's featured listings answer only for an operational Marketer
//   or Management (MAR-01); that list is not an audited read.
// Any failure just hides those menus; the API still checks every request.
export async function loadAccess(): Promise<Access> {
  const [grants, desk, identity, marketing] = await Promise.allSettled([
    request<{ code: string }[]>('/management/authorization/roles/management/permissions/', { auth: true }),
    request<unknown[]>('/management/complaints/', { auth: true }),
    request<unknown>('/lister-identity/me/', { auth: true }),
    request<unknown[]>('/marketing/staff/featured/', { auth: true }),
  ])
  const handlesComplaints = desk.status === 'fulfilled'
  const lists =
    identity.status === 'fulfilled' || (identity.reason instanceof ApiError && identity.reason.status === 404)
  const access: Access = { roles: [], permissions: [] }
  if (grants.status === 'fulfilled') {
    access.roles.push('management')
    access.permissions.push(...grants.value.map((grant) => grant.code))
    if (handlesComplaints) access.permissions.push('complaint.handle')
  } else if (handlesComplaints) {
    access.roles.push('verifier')
    access.permissions.push('complaint.handle', 'verification.record_result')
  }
  if (marketing.status === 'fulfilled') {
    if (!access.roles.includes('management')) access.roles.push('marketer')
    access.permissions.push('analytics.view', 'analytics.export', 'marketing.manage', 'marketing.send_campaign')
  }
  if (lists) {
    access.roles.push('lister')
    // 'lister.area' is the UI's own marker: Management also holds listing.create,
    // but only Owners and Agents get the seller menus.
    access.permissions.push('lister.area', 'listing.create', 'lead.view')
  }
  return { roles: access.roles, permissions: [...new Set(access.permissions)] }
}
