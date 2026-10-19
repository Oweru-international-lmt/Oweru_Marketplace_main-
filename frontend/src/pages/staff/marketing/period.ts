// When a featured listing or a content item runs.

export type Period = { starts_at: string; ends_at: string; enabled: boolean }

export function periodState(row: Period, now = Date.now()): 'live' | 'scheduled' | 'ended' | 'off' {
  if (!row.enabled) return 'off'
  if (new Date(row.starts_at).getTime() > now) return 'scheduled'
  if (new Date(row.ends_at).getTime() <= now) return 'ended'
  return 'live'
}

export const STATE_TONE = { live: 'good', scheduled: 'gold', ended: 'muted', off: 'bad' } as const

// <input type="datetime-local"> wants local time without a zone.
export function toLocalInput(value: string) {
  const date = new Date(value)
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
