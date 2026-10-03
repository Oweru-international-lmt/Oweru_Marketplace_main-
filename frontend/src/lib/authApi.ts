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
  created_at: string
}

export type RegistrationInput = {
  email: string
  phone: string
  full_name: string
  password: string
  language: Language
}

export const authApi = {
  register: (input: RegistrationInput) => request<User>('/auth/register/', { method: 'POST', body: input }),

  login: (email: string, password: string) =>
    request<Tokens & { user: User }>('/auth/login/', { method: 'POST', body: { email, password } }),

  me: () => request<User>('/auth/me/', { auth: true }),

  requestPasswordReset: (email: string) =>
    request<{ detail: string }>('/auth/password/reset/', { method: 'POST', body: { email } }),

  confirmPasswordReset: (uid: string, token: string, newPassword: string) =>
    request<{ detail: string }>('/auth/password/reset/confirm/', {
      method: 'POST',
      body: { uid, token, new_password: newPassword },
    }),
}
