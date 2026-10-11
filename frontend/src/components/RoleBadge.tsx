import { useTranslation } from 'react-i18next'
import { roleGroup } from '../lib/roles'

const STYLES = {
  public: 'bg-mist/70 text-navy',
  partner: 'bg-gold-light/40 text-navy',
  staff: 'bg-navy text-white',
}

// active: role grants access; revoked: was assigned, now removed; absent: never given.
type RoleState = 'active' | 'revoked' | 'absent'

export function RoleBadge({ role, state = 'active' }: { role: string; state?: RoleState }) {
  const { t } = useTranslation()
  const style =
    state === 'active'
      ? STYLES[roleGroup(role)]
      : `bg-paper text-muted ring-1 ring-mist ${state === 'revoked' ? 'line-through' : ''}`
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${style}`}>
      {t(`roleNames.${role}`, { defaultValue: role })}
    </span>
  )
}
