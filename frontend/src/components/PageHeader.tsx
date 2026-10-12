import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { findNavItem } from '../layouts/navigation'
import { ChevronRightIcon } from './icons'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

type Crumb = { label: string; to?: string }

type PageHeaderProps = {
  title: string
  description?: string
  // Older pages pass a kicker; the W1 header shows the breadcrumb instead.
  eyebrow?: string
  actions?: ReactNode
  // Browser tab title when it should differ from the heading (e.g. a greeting).
  documentTitle?: string
  // Detail pages add their own trail; otherwise it comes from the sidebar.
  crumbs?: Crumb[]
}

// After W1: the page name in the accent colour with the trail under it, and
// any actions on the right.
export function PageHeader({ title, description, actions, documentTitle, crumbs }: PageHeaderProps) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const root = useRef<HTMLDivElement>(null)
  useDocumentTitle(documentTitle ?? title)
  const current = findNavItem(pathname)
  const trail: Crumb[] = crumbs ?? (current ? [{ label: t(current.group.titleKey) }, { label: t(current.item.labelKey) }] : [])

  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.from('[data-reveal]', { y: 10, opacity: 0, duration: 0.5, stagger: 0.06, ease: 'power3.out' })
      })
    },
    { scope: root, dependencies: [title], revertOnUpdate: true },
  )

  return (
    <div ref={root} className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 data-reveal className="text-[22px] leading-tight font-medium text-[#9a6c12]">
          {title}
        </h1>
        {trail.length > 0 && (
          <nav data-reveal aria-label={t('nav.breadcrumb')} className="mt-1">
            <ol className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
              {trail.map((crumb, index) => (
                <li key={`${crumb.label}-${index}`} className="flex items-center gap-1.5">
                  {index > 0 && <ChevronRightIcon className="size-3 text-muted/60" />}
                  {crumb.to ? (
                    <Link to={crumb.to} className="hover:text-navy">
                      {crumb.label}
                    </Link>
                  ) : (
                    <span aria-current={index === trail.length - 1 ? 'page' : undefined}>{crumb.label}</span>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        )}
        {description && (
          <p data-reveal className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
            {description}
          </p>
        )}
      </div>
      {actions && <div data-reveal>{actions}</div>}
    </div>
  )
}
