import type { Language } from '../i18n'
import { request } from './api'
import type { Tokens } from './tokens'

export type AccountCategory = 'public' | 'operational'

// Mirrors accounts.serializers.UserPublicSerializer. `roles` and `permissions`
// list effective access only; the API still checks every request.
export type User = {
  id: string
  phone: string
  full_name: string
  email: string
  language: Language
  account_category: AccountCategory
  roles: string[]
  permissions: string[]
  email_verified: boolean
  phone_verified: boolean
  must_change_password: boolean
  created_at: string
}

export type RegistrationInput = {
  email: string
  phone: string
  full_name: string
  password: string
  language: Language
}

export type ProfileChanges = Partial<Pick<User, 'full_name' | 'phone' | 'language'>>

export type DeletionRequest = {
  id: string
  status: 'pending' | 'completed' | 'declined' | 'cancelled'
  reason: string
  requested_at: string
  resolved_at: string | null
  resolution_note: string
}

export type ConfirmationLink = {
  state: 'valid' | 'used' | 'expired'
  purpose: string
  recipient: string
  full_name: string
  expires_at: string
  decision: '' | 'confirmed' | 'declined'
}

export const authApi = {
  register: (input: RegistrationInput) => request<User>('/auth/register/', { method: 'POST', body: input }),

  login: (email: string, password: string) =>
    request<Tokens & { user: User }>('/auth/login/', { method: 'POST', body: { email, password } }),

  logout: (refresh: string) => request<null>('/auth/logout/', { method: 'POST', body: { refresh } }),

  me: () => request<User>('/auth/me/', { auth: true }),

  updateProfile: (changes: ProfileChanges) =>
    request<User>('/auth/me/', { method: 'PATCH', body: changes, auth: true }),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<Tokens & { user: User }>('/auth/password/change/', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword },
      auth: true,
    }),

  requestPasswordReset: (email: string) =>
    request<{ detail: string }>('/auth/password/reset/', { method: 'POST', body: { email } }),

  confirmPasswordReset: (uid: string, token: string, newPassword: string) =>
    request<{ detail: string }>('/auth/password/reset/confirm/', {
      method: 'POST',
      body: { uid, token, new_password: newPassword },
    }),

  confirmEmail: (id: string, token: string) =>
    request<{ detail: string; state: string }>('/auth/email/confirm/', { method: 'POST', body: { id, token } }),

  resendEmailConfirmation: () => request<{ detail: string }>('/auth/email/resend/', { method: 'POST', auth: true }),

  // SRD 20.3 WhatsApp confirmation page; no sign-in, the token is the proof.
  confirmationLink: (id: string, token: string) =>
    request<ConfirmationLink>(`/auth/confirmations/${encodeURIComponent(id)}/?token=${encodeURIComponent(token)}`),

  decideConfirmationLink: (id: string, token: string, decision: 'confirmed' | 'declined') =>
    request<{ state: string }>(`/auth/confirmations/${encodeURIComponent(id)}/`, {
      method: 'POST',
      body: { token, decision },
    }),

  deletionRequest: () => request<{ request: DeletionRequest | null }>('/auth/me/deletion-request/', { auth: true }),

  requestDeletion: (reason: string) =>
    request<{ request: DeletionRequest }>('/auth/me/deletion-request/', { method: 'POST', body: { reason }, auth: true }),

  cancelDeletion: () => request<null>('/auth/me/deletion-request/', { method: 'DELETE', auth: true }),
}
