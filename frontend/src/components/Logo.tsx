import { Link } from 'react-router-dom'

type LogoProps = {
  tone?: 'dark' | 'light'
  to?: string
  // Hide the "Marketplace" label on phones where the header is crowded.
  compact?: boolean
}

// Full logo (mark + "oweru" wordmark) per the brand kit's header usage,
// followed by the product name.
export function Logo({ tone = 'dark', to = '/', compact = false }: LogoProps) {
  return (
    <Link to={to} className="group inline-flex shrink-0 items-center gap-3 rounded-xl" aria-label="Oweru Marketplace">
      <span className="block size-11 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-navy/10 transition-transform duration-300 group-hover:-rotate-3">
        <img src="/oweru-logo-print.jpg" alt="" width={44} height={44} className="size-full object-cover" />
      </span>
      <span
        className={`font-display text-sm font-medium tracking-[0.28em] uppercase ${
          tone === 'light' ? 'text-white' : 'text-navy'
        } ${compact ? 'hidden sm:inline' : ''}`}
      >
        Marketplace
      </span>
    </Link>
  )
}
