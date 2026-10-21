import type { ComponentType, SVGProps } from 'react'
import { can } from '../auth/access'
import { BankIcon, BanknoteIcon, BarsIcon, ChatIcon, DashboardIcon, DocumentIcon, MailIcon, HomeIcon, IdCardIcon, InboxIcon, ListIcon, MapPinIcon, PlusCircleIcon, SearchIcon, ShieldIcon, UserIcon, UsersIcon, WhatsAppIcon } from '../components/icons'
import type { User } from '../lib/authApi'

export type NavItem = {
  to: string
  labelKey: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  permission?: string
  // Hidden from people who hold any of these (e.g. "become a lister").
  hiddenWith?: string[]
  // After L11: a status submenu under the item while it is open.
  children?: { search: string; labelKey: string }[]
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
      { to: '/staff/checks', labelKey: 'nav.locationChecks', icon: MapPinIcon, permission: 'verification.record_result' },
      { to: '/staff/full-checks', labelKey: 'nav.fullChecks', icon: ShieldIcon, permission: 'complaint.handle' },
      { to: '/staff/identities', labelKey: 'nav.identities', icon: IdCardIcon, permission: 'identity.review' },
      { to: '/staff/deals', labelKey: 'nav.dealsDesk', icon: BanknoteIcon, permission: 'payment.confirm' },
      { to: '/staff/payouts', labelKey: 'nav.payoutsDesk', icon: BankIcon, permission: 'payout.record' },
      { to: '/staff/outbox', labelKey: 'nav.outbox', icon: WhatsAppIcon, permission: 'outbox.send' },
    ],
  },
  {
    // SRD 18 and 19: the market panel and the Marketer's tools.
    titleKey: 'nav.groupMarketing',
    items: [
      { to: '/staff/market', labelKey: 'nav.marketPanel', icon: BarsIcon, permission: 'analytics.view' },
      { to: '/staff/marketing/campaigns', labelKey: 'nav.campaigns', icon: MailIcon, permission: 'marketing.send_campaign' },
      { to: '/staff/marketing/featured', labelKey: 'nav.featured', icon: HomeIcon, permission: 'marketing.manage' },
      { to: '/staff/marketing/content', labelKey: 'nav.content', icon: DocumentIcon, permission: 'marketing.manage' },
    ],
  },
  {
    // The lister's own work: listings, enquiries and identity (SRD 15 to 18).
    titleKey: 'nav.groupListing',
    items: [
      { to: '/lister', labelKey: 'nav.listerHome', icon: DashboardIcon, permission: 'lister.area' },
      {
        to: '/lister/listings',
        labelKey: 'nav.myListings',
        icon: ListIcon,
        permission: 'lister.area',
        children: [
          { search: '', labelKey: 'lister.filters.all' },
          { search: '?status=draft', labelKey: 'lister.filters.draft' },
          { search: '?status=published', labelKey: 'lister.filters.published' },
          { search: '?status=unavailable', labelKey: 'lister.filters.unavailable' },
          { search: '?status=sold', labelKey: 'lister.filters.sold' },
        ],
      },
      { to: '/lister/listings/new', labelKey: 'nav.addListing', icon: PlusCircleIcon, permission: 'lister.area' },
      { to: '/lister/enquiries', labelKey: 'nav.enquiries', icon: InboxIcon, permission: 'lister.area' },
      { to: '/lister/deals', labelKey: 'nav.deals', icon: BanknoteIcon, permission: 'lister.area' },
      { to: '/lister/payouts', labelKey: 'nav.payouts', icon: BankIcon, permission: 'lister.area' },
      { to: '/lister/identity', labelKey: 'nav.identity', icon: IdCardIcon, permission: 'lister.area' },
      { to: '/lister/checks', labelKey: 'nav.locationRequest', icon: MapPinIcon, permission: 'lister.area' },
    ],
  },
  {
    titleKey: 'nav.groupAccount',
    items: [
      { to: '/account', labelKey: 'nav.account', icon: UserIcon },
      { to: '/purchases', labelKey: 'nav.purchases', icon: HomeIcon, hiddenWith: ['complaint.handle', 'authorization.view'] },
      { to: '/listings', labelKey: 'site.browse', icon: SearchIcon },
      { to: '/sell', labelKey: 'nav.sell', icon: HomeIcon, hiddenWith: ['lister.area', 'complaint.handle', 'authorization.view'] },
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
    items: group.items.filter(
      (item) => (!item.permission || can(user, item.permission)) && !item.hiddenWith?.some((permission) => can(user, permission)),
    ),
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
