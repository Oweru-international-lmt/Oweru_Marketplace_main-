import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { SearchIcon } from '../../../components/icons'
import type { ComplaintStatus, FullCheckStatus } from '../../../lib/servicesApi'

// Pieces shared by the staff screens: W4's soft status chips and row table,
// W5's radio tabs and search, and the plain white cards of W1 and W2.

const COMPLAINT_CHIP: Record<ComplaintStatus, string> = {
  RECEIVED: 'bg-[#e8eefb] text-[#3552a8]',
  IN_REVIEW: 'bg-gold/15 text-[#7a5410]',
  WAITING_INFORMATION: 'bg-[#f1e9fa] text-[#6b3fa0]',
  RESOLVED: 'bg-success-soft text-success',
  UNDER_FINAL_REVIEW: 'bg-navy/10 text-navy',
  CLOSED: 'bg-mist/70 text-muted',
}

const CHECK_CHIP: Record<FullCheckStatus, string> = {
  AWAITING_PAYMENT: 'bg-gold/15 text-[#7a5410]',
  AWAITING_CONSENT: 'bg-[#e8eefb] text-[#3552a8]',
  IN_PROGRESS: 'bg-[#e8eefb] text-[#3552a8]',
  UNDER_REVIEW: 'bg-[#f1e9fa] text-[#6b3fa0]',
  PASSED: 'bg-success-soft text-success',
  PROBLEM_FOUND: 'bg-danger-soft text-danger',
  NOT_COMPLETED: 'bg-mist/70 text-muted',
}

export function ComplaintChip({ status }: { status: ComplaintStatus }) {
  const { t } = useTranslation()
  return <Chip className={COMPLAINT_CHIP[status]}>{t(`staff.statuses.${status}`)}</Chip>
}

export function CheckChip({ status }: { status: FullCheckStatus }) {
  const { t } = useTranslation()
  return <Chip className={CHECK_CHIP[status]}>{t(`fullCheck.statuses.${status}`)}</Chip>
}

export function Chip({ className, children }: { className: string; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium whitespace-nowrap ${className}`}>{children}</span>
}

// W1 and W2 cards: white, a hairline edge, square-ish corners.
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-[6px] border border-mist/70 bg-white ${className}`}>{children}</section>
}

export function CardTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-[15px] font-semibold text-navy">{children}</h2>
      {action}
    </div>
  )
}

type TabsProps<T extends string> = {
  label: string
  options: { value: T; label: string; count?: number }[]
  value: T
  onChange: (value: T) => void
}

// W5: one rounded box of radio options to filter by status.
export function RadioTabs<T extends string>({ label, options, value, onChange }: TabsProps<T>) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-mist bg-white px-4 py-2.5">
      {options.map((option) => {
        const on = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(option.value)}
            className={`inline-flex items-center gap-2 text-[13px] ${on ? 'font-medium text-navy' : 'text-muted hover:text-navy'}`}
          >
            <span className={`grid size-3.5 place-items-center rounded-full border ${on ? 'border-gold' : 'border-mist'}`}>
              {on && <span className="size-1.5 rounded-full bg-gold" />}
            </span>
            {option.label}
            {option.count !== undefined && <span className="text-[11px] text-muted">({option.count})</span>}
          </button>
        )
      })}
    </div>
  )
}

export function SearchBox({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="relative block w-full sm:w-60">
      <span className="sr-only">{label}</span>
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={label}
        className="h-10 w-full rounded-[6px] border border-mist bg-white pr-10 pl-3.5 text-[13px] text-navy outline-none placeholder:text-muted/70 focus:border-gold focus:ring-2 focus:ring-gold/20"
      />
      <SearchIcon className="pointer-events-none absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-muted" />
    </label>
  )
}

export type Column<Row> = { key: string; label: string; className?: string; render: (row: Row) => ReactNode }

// W4: grey column labels, then each row as its own white strip.
export function RowTable<Row>({ columns, rows, rowKey, onOpen, empty, caption }: {
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string
  onOpen?: (row: Row) => void
  empty: string
  caption: string
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] border-separate border-spacing-y-1 text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={`px-3 pb-1 text-[10px] font-semibold tracking-[0.08em] text-muted uppercase ${column.className ?? ''}`}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="rounded-[6px] bg-white px-4 py-10 text-center text-sm text-muted">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={onOpen ? () => onOpen(row) : undefined}
                className={`group bg-white text-[13px] text-navy shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${onOpen ? 'cursor-pointer' : ''}`}
              >
                {columns.map((column, index) => (
                  <td
                    key={column.key}
                    className={`px-3 py-2.5 align-middle whitespace-nowrap transition-colors group-hover:bg-paper ${index === 0 ? 'rounded-l-[6px]' : ''} ${
                      index === columns.length - 1 ? 'rounded-r-[6px]' : ''
                    } ${column.className ?? ''}`}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
