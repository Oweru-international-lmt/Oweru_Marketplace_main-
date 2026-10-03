// Mirrors authorization/catalog.py.
export const PUBLIC_ROLES = ['buyer', 'owner', 'agent'] as const
export const PARTNER_ROLES = ['local_official', 'professional'] as const
export const STAFF_ROLES = ['verifier', 'marketer', 'management'] as const

export const ROLE_GROUPS = [
  { key: 'public', roles: PUBLIC_ROLES },
  { key: 'partner', roles: PARTNER_ROLES },
  { key: 'staff', roles: STAFF_ROLES },
] as const

export const ALL_ROLES = [...PUBLIC_ROLES, ...PARTNER_ROLES, ...STAFF_ROLES]

// Management may assign only these; other operational roles need onboarding.
export const ASSIGNABLE_ROLES = ['verifier', 'marketer'] as const

// Operational roles Management may revoke (everything except Management itself).
export const REVOCABLE_ROLES = ['verifier', 'marketer', 'local_official', 'professional']

// The only runtime-adjustable grant: WhatsApp outbox sending for these roles.
export const OUTBOX_OPTIONAL_ROLES = ['verifier', 'marketer'] as const
export const OUTBOX_PERMISSION = 'outbox.send'

export function roleGroup(role: string): 'public' | 'partner' | 'staff' {
  if ((PUBLIC_ROLES as readonly string[]).includes(role)) return 'public'
  if ((PARTNER_ROLES as readonly string[]).includes(role)) return 'partner'
  return 'staff'
}

// "listing.view_owner_price" -> "listing"
export function permissionGroup(code: string): string {
  return code.split('.')[0]
}

// Reading order for the permission matrix: the user journey, then operations.
// Groups the backend adds later are appended after these.
export const PERMISSION_GROUP_ORDER = [
  'account',
  'property',
  'listing',
  'lead',
  'deal',
  'identity',
  'verification',
  'partner',
  'commission',
  'payment',
  'payout',
  'complaint',
  'outbox',
  'marketing',
  'analytics',
  'authorization',
  'settings',
  'audit',
]
