import type { ComponentType, SVGProps } from 'react'
import { can } from '../auth/access'
import { ShieldIcon, TrashIcon, UserIcon, UsersIcon } from '../components/icons'
import type { User } from '../lib/authApi'

export type NavItem = {
  to: string
  labelKey: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  permission?: string
}

export type NavGroup = { titleKey: string; items: NavItem[] }

// Single source for the sidebar and the top bar breadcrumb. Items appear only
// for people whose permissions allow the page (UX only; the API enforces access).
const NAV_GROUPS: NavGroup[] = [
  {
    titleKey: 'nav.groupAccount',
    items: [{ to: '/account', labelKey: 'nav.account', icon: UserIcon }],
  },
  {
    titleKey: 'nav.groupManagement',
    items: [
      { to: '/management/roles', labelKey: 'nav.roles', icon: ShieldIcon, permission: 'authorization.view' },
      { to: '/management/staff', labelKey: 'nav.staff', icon: UsersIcon, permission: 'authorization.view' },
      { to: '/management/deletion-requests', labelKey: 'nav.deletions', icon: TrashIcon, permission: 'account.manage' },
    ],
  },
]

export function visibleGroups(user: User | null): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.permission || can(user, item.permission)),
  })).filter((group) => group.items.length > 0)
}

export function findNavItem(pathname: string): { group: NavGroup; item: NavItem } | null {
  for (const group of NAV_GROUPS) {
    const item = group.items.find((candidate) => pathname.startsWith(candidate.to))
    if (item) return { group, item }
  }
  return null
}
