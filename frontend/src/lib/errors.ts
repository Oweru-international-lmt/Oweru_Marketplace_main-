import type { TFunction } from 'i18next'
import { ApiError, type FieldErrors } from './api'

// The backend answers in English (no LocaleMiddleware), so known messages are
// mapped to translation keys; anything unrecognised is shown as sent.
const KNOWN_MESSAGES: [RegExp, string][] = [
  [/email already exists/i, 'server.emailTaken'],
  [/phone already exists/i, 'server.phoneTaken'],
  [/too short/i, 'validation.passwordShort'],
  [/too common/i, 'server.passwordCommon'],
  [/entirely numeric/i, 'validation.passwordNumeric'],
  [/too similar/i, 'server.passwordSimilar'],
  [/invalid email or password/i, 'server.invalidCredentials'],
  [/invalid or expired/i, 'server.resetInvalid'],
  [/valid email/i, 'validation.emailInvalid'],
  [/separate accounts/i, 'server.separateAccounts'],
  [/self-(assignment|revocation)/i, 'server.selfChange'],
  [/inactive account/i, 'server.inactiveTarget'],
  [/not have permission|required permission|required role/i, 'server.forbidden'],
  [/required|may not be blank/i, 'validation.required'],
]

export function translateServerMessage(t: TFunction, message: string): string {
  for (const [pattern, key] of KNOWN_MESSAGES) {
    if (pattern.test(message)) return t(key)
  }
  return message
}

export function fieldErrorsFrom(t: TFunction, errors: FieldErrors): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [field, messages] of Object.entries(errors)) {
    if (messages[0]) result[field] = translateServerMessage(t, messages[0])
  }
  return result
}

// One sentence for a form-level alert.
export function errorMessage(t: TFunction, error: unknown): string {
  if (!(error instanceof ApiError)) return t('common.unexpectedError')
  if (error.isNetworkError) return t('common.networkError')
  if (error.status === 429) {
    return error.retryAfterSeconds
      ? t('common.throttled', { seconds: error.retryAfterSeconds })
      : t('common.throttledNoTime')
  }
  if (error.detail) return translateServerMessage(t, error.detail)
  const nonField = error.fieldErrors.non_field_errors?.[0]
  if (nonField) return translateServerMessage(t, nonField)
  return t('common.unexpectedError')
}
