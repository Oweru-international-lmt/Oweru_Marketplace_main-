import { DEAL_STEPS, stepTimes, type Deal, type DealStep, type DealSteps } from '../../lib/dealsApi'

export type TimelineItem = { key: DealStep; title: string; body: string; at: string | null }

export function timelineItems(steps: DealSteps, text: (step: DealStep) => { title: string; body: string }, include: DealStep[] = [...DEAL_STEPS]): TimelineItem[] {
  const times = stepTimes(steps)
  return include.map((key) => ({ key, ...text(key), at: times[key] }))
}

export const DOCUMENT_ACCEPT = 'application/pdf,image/jpeg,image/png'

// The same bank list the owner's confirmation link offers.
export const TANZANIAN_BANKS = ['CRDB', 'NMB', 'NBC', 'Stanbic', 'Equity', 'Exim', 'Absa', 'Azania', 'DTB', 'KCB', 'I&M'] as const

export type ReviewKind = 'oweruSlip' | 'agreement' | 'taxReceipt' | 'complete'

// D18: what each open deal is waiting on from management, in the order the
// work happens (PAY-09, LEAD-05, PAY-11).
export function reviewFor(deal: Deal): ReviewKind[] {
  if (deal.state !== 'OPEN') return []
  const steps = deal.steps
  const items: ReviewKind[] = []
  if (steps.oweru_paid_at && !steps.oweru_confirmed_at) items.push('oweruSlip')
  if (steps.agreement_price_confirmed_at && !steps.agreement_approved_at) items.push('agreement')
  if (steps.oweru_confirmed_at && !deal.tax_receipt) items.push('taxReceipt')
  if (steps.owner_confirmed_at && steps.oweru_confirmed_at && steps.agreement_approved_at) items.push('complete')
  return items
}

// D18's pipeline: where each deal stands.
export type PipelineStage = 'waiting' | 'slips' | 'confirmed' | 'complete'

export function pipelineStage(deal: Deal): PipelineStage | null {
  if (deal.state === 'CANCELLED') return null
  if (deal.state === 'COMPLETE') return 'complete'
  if (deal.steps.owner_confirmed_at && deal.steps.oweru_confirmed_at) return 'confirmed'
  if (deal.steps.owner_paid_at || deal.steps.oweru_paid_at) return 'slips'
  return 'waiting'
}
