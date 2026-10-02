import { useDocumentTitle } from '../hooks/useDocumentTitle'

export function AuthHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  useDocumentTitle(title)
  return (
    <div className="mb-8">
      <h1 className="font-display text-[2rem] leading-tight font-semibold tracking-tight text-navy sm:text-[2.25rem]">
        {title}
      </h1>
      {subtitle && <p className="mt-2 text-[15px] leading-relaxed text-muted">{subtitle}</p>}
    </div>
  )
}
