import type { TFunction } from 'i18next'

// Client-side mirrors of the backend password validators (ACC-04). The server
// still decides; these only save a round trip for the obvious cases.
export function passwordError(t: TFunction, password: string): string | undefined {
  if (!password) return t('validation.required')
  if (password.length < 8) return t('validation.passwordShort')
  if (/^\d+$/.test(password)) return t('validation.passwordNumeric')
  return undefined
}

export function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

export function emailError(t: TFunction, email: string): string | undefined {
  if (!email.trim()) return t('validation.required')
  if (!isEmail(email.trim())) return t('validation.emailInvalid')
  return undefined
}
