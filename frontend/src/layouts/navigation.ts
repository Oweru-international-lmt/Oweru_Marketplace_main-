import type { ComponentType, SVGProps } from 'react'
import { can } from '../auth/access'
import { ChatIcon, DashboardIcon, SearchIcon, ShieldIcon, UserIcon, UsersIcon } from '../components/icons'
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
    // Oweru's daily work: complaints, full check payments and results.
    titleKey: 'nav.groupOperations',
    items: [
      { to: '/staff', labelKey: 'nav.overview', icon: DashboardIcon, permission: 'complaint.handle' },
      { to: '/staff/complaints', labelKey: 'nav.complaints', icon: ChatIcon, permission: 'complaint.handle' },
      { to: '/staff/full-checks', labelKey: 'nav.fullChecks', icon: ShieldIcon, permission: 'complaint.handle' },
    ],
  },
  {
    titleKey: 'nav.groupAccount',
    items: [
      { to: '/account', labelKey: 'nav.account', icon: UserIcon },
      { to: '/listings', labelKey: 'site.browse', icon: SearchIcon },
    ],
  },
  {
    titleKey: 'nav.groupManagement',
    items: [
      { to: '/management/roles', labelKey: 'nav.roles', icon: ShieldIcon, permission: 'authorization.view' },
      { to: '/management/staff', labelKey: 'nav.staff', icon: UsersIcon, permission: 'authorization.view' },
    ],
  },
]

export function visibleGroups(user: User | null): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.permission || can(user, item.permission)),
  })).filter((group) => group.items.length > 0)
}

// The longest matching path wins, so /staff/complaints/x is "Complaints", not "Overview".
export function findNavItem(pathname: string): { group: NavGroup; item: NavItem } | null {
  let best: { group: NavGroup; item: NavItem } | null = null
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      const matches = pathname === item.to || pathname.startsWith(`${item.to}/`)
      if (matches && (!best || item.to.length > best.item.to.length)) best = { group, item }
    }
  }
  return best
}
