import { motion } from 'motion/react'
import type { ComponentType, ReactNode, SVGProps } from 'react'
import { CheckIcon } from '../../../components/icons'

type Icon = ComponentType<SVGProps<SVGSVGElement>>

export type Stage = { label: string; body: string; icon: Icon }

type Fact = { label: string; value: ReactNode }

type TrackingProps = {
  title: string
  facts: Fact[]
  stages: Stage[]
  // Index of the stage reached. `stopped` marks a path that ended badly there.
  current: number
  stopped?: boolean
  label: string
  action?: { href: string; label: string; icon: Icon }
}

function stateOf(index: number, current: number, last: number, stopped: boolean) {
  if (index < current || (index === current && index === last && !stopped)) return 'done'
  return index === current ? 'here' : 'later'
}

// Desktop, after S10: a navy title strip, a lighter strip of three facts,
// then the stages as large circles on one line, and a round action button
// on the card's corner.
export function TrackingCard({ title, facts, stages, current, stopped = false, label, action }: TrackingProps) {
  const last = stages.length - 1
  return (
    <section aria-label={label} className="relative rounded-md bg-white shadow-lift">
      <p className="rounded-t-md bg-navy px-7 py-3 text-sm text-white/80">{title}</p>
      <dl className="grid grid-cols-3 gap-6 bg-navy-soft px-7 py-4">
        {facts.map((fact) => (
          <div key={fact.label} className="min-w-0">
            <dt className="text-[11px] font-semibold tracking-[0.08em] text-white/65 uppercase">{fact.label}</dt>
            <dd className="mt-0.5 truncate text-[15px] font-medium text-white">{fact.value}</dd>
          </div>
        ))}
      </dl>
      <ol className="flex items-start px-7 pt-12 pb-14">
        {stages.map((stage, index) => {
          const state = stateOf(index, current, last, stopped)
          const failed = stopped && index === current
          return (
            <li key={stage.label} aria-current={index === current ? 'step' : undefined} className="relative flex flex-1 flex-col items-center text-center">
              {index > 0 && (
                <span aria-hidden="true" className="absolute top-[26px] right-[calc(50%+26px)] left-[calc(-50%+26px)] h-[3px] rounded-full bg-mist/70">
                  <motion.span
                    className={`block h-full origin-left rounded-full ${index === current ? 'bg-gradient-to-r from-navy-soft to-gold' : 'bg-navy-soft'}`}
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: index <= current ? 1 : 0 }}
                    transition={{ duration: 0.6, delay: 0.15 + index * 0.12, ease: 'easeOut' }}
                  />
                </span>
              )}
              <span
                className={`relative grid size-[52px] place-items-center rounded-full ring-[3px] ring-white ${
                  failed
                    ? 'bg-danger text-white shadow-[0_0_0_5px_rgba(180,35,24,0.18)]'
                    : state === 'done'
                      ? 'bg-navy-soft text-gold-light shadow-[0_0_0_5px_rgba(45,58,88,0.15)]'
                      : state === 'here'
                        ? 'bg-gold text-navy shadow-[0_0_0_5px_rgba(200,145,40,0.25)]'
                        : 'bg-paper text-mist'
                }`}
              >
                {state === 'later' ? <CheckIcon className="size-6" /> : <stage.icon className="size-6" />}
              </span>
              <span className={`mt-3 px-1 text-[15px] leading-snug ${index === current ? 'font-medium text-navy' : 'text-navy/70'}`}>{stage.label}</span>
            </li>
          )
        })}
      </ol>
      <div aria-hidden="true" className="h-1.5 rounded-b-md bg-navy-soft" />
      {action && (
        <a
          href={action.href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={action.label}
          title={action.label}
          className="absolute -right-5 -bottom-6 grid size-14 place-items-center rounded-full bg-gold text-navy shadow-lift transition-transform hover:scale-105"
        >
          <action.icon className="size-6" />
        </a>
      )}
    </section>
  )
}

type TimelineProps = {
  summary: [Fact, Fact]
  stages: Stage[]
  current: number
  stopped?: boolean
  label: string
}

// Phones, after S11: a grey strip with two facts, then a vertical timeline
// where each stage has a dot, an icon, a title and one plain sentence.
export function Timeline({ summary, stages, current, stopped = false, label }: TimelineProps) {
  const last = stages.length - 1
  return (
    <section aria-label={label} className="bg-white">
      <dl className="grid grid-cols-2 border-b border-mist bg-paper py-5 text-center">
        {summary.map((fact) => (
          <div key={fact.label} className="min-w-0 px-3">
            <dt className="text-[13px] tracking-[0.04em] text-muted uppercase">{fact.label}</dt>
            <dd className="mt-1 truncate text-lg font-medium text-navy">{fact.value}</dd>
          </div>
        ))}
      </dl>
      <ol className="space-y-9 px-6 py-10">
        {stages.map((stage, index) => {
          const state = stateOf(index, current, last, stopped)
          const failed = stopped && index === current
          const reached = index <= current
          return (
            <li key={stage.label} aria-current={index === current ? 'step' : undefined} className="relative grid grid-cols-[18px_52px_minmax(0,1fr)] items-center gap-4">
              {index < last && (
                <span
                  aria-hidden="true"
                  className={`absolute top-1/2 left-[8px] h-[calc(100%+2.25rem)] w-0.5 ${index + 1 <= current ? 'bg-gold' : 'bg-mist'}`}
                />
              )}
              <span
                className={`relative size-[18px] rounded-full ${
                  failed ? 'bg-danger' : state === 'done' ? 'bg-gold' : state === 'here' ? 'bg-navy ring-4 ring-navy/15' : 'bg-mist'
                }`}
              />
              <stage.icon className={`size-12 ${reached ? (failed ? 'text-danger' : 'text-navy') : 'text-mist'}`} strokeWidth={1.3} />
              <div className="min-w-0">
                <p className={`text-[19px] leading-snug ${index === current ? (failed ? 'font-medium text-danger' : 'font-medium text-navy') : reached ? 'text-navy/80' : 'text-muted/50'}`}>
                  {stage.label}
                </p>
                <p className={`mt-1 text-[15px] leading-snug ${index === current ? 'text-navy/85' : reached ? 'text-muted' : 'text-muted/50'}`}>{stage.body}</p>
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
