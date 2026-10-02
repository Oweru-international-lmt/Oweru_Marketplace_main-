export type Tokens = { access: string; refresh: string }

const STORAGE_KEY = 'oweru.auth'

export function getTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (
      parsed &&
      typeof parsed === 'object' &&
      typeof (parsed as Tokens).access === 'string' &&
      typeof (parsed as Tokens).refresh === 'string'
    ) {
      return parsed as Tokens
    }
  } catch {
    // Blocked storage or corrupt value: treat as signed out.
  }
  return null
}

export function setTokens(tokens: Tokens): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens))
  } catch {
    // Without storage the session lasts until the tab reloads.
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Nothing to clear.
  }
}
