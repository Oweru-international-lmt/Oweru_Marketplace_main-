import { request } from './api'

// Phase 2: verification tasks (FUL-03 to FUL-06, LOC-03 to 05, PRO-02 to 05)
// and site capture (MAP-01 to MAP-05). One task list serves listers (site
// capture), local officials (local office), professionals and verifiers; the
// API decides which tasks each person may see.

export type TaskKind = 'SITE_CAPTURE' | 'LOCAL_OFFICE' | 'PROFESSIONAL' | 'REGISTRY'
export type TaskStatus = 'UNASSIGNED' | 'NEEDS_OFFICIAL' | 'ASSIGNED' | 'ACCEPTED' | 'SUBMITTED' | 'TIMED_OUT'
export type ProfessionalType = 'AFISA_MIPANGO_MIJI' | 'PLANNER' | 'SURVEYOR'

export type Task = {
  id: string
  job_id: string
  kind: TaskKind
  status: TaskStatus
  professional_type: ProfessionalType | ''
  due_at: string | null
  property_id: string
  locality: string
  area: string
  owner_name: string
  assignee_name: string
  submitted_versions: number
  approx_point: [number, number] | null
}

export type Submission = { id: string; version: number; findings: Record<string, unknown>; author_name: string; registration_number: string; created_at: string }
export type TaskDetail = Task & { questions?: string[]; submissions: Submission[] }

export type Answer = 'YES' | 'NO'

export type Professional = { id: string; name: string; professional_type: ProfessionalType; registration_number: string; status: 'ACTIVE' | 'INACTIVE'; regions: string[]; districts: string[] }

// The findings fields each professional type fills in (task_services.validate_findings).
export const FINDING_FIELDS: Record<ProfessionalType | 'REGISTRY', string[]> = {
  AFISA_MIPANGO_MIJI: ['permitted_use', 'planned_roads_or_reserves', 'supporting_extracts'],
  PLANNER: ['layout', 'development_restrictions', 'planning_context'],
  SURVEYOR: ['beacon_photos', 'overlap_notes'],
  REGISTRY: ['search_result', 'reference'],
}

type Page<T> = { count: number; results: T[] }

export function deviceName(): string {
  const agent = navigator.userAgent
  const model = /\(([^)]+)\)/.exec(agent)?.[1] ?? 'browser'
  return model.slice(0, 200)
}

export const tasksApi = {
  list: (job?: string) => request<Page<Task>>(`/verification-tasks/?page_size=100${job ? `&job=${encodeURIComponent(job)}` : ''}`, { auth: true }),
  get: (id: string) => request<TaskDetail>(`/verification-tasks/${id}/`, { auth: true }),
  decide: (id: string, decision: 'ACCEPT' | 'DECLINE', reason = '') => request<Task>(`/verification-tasks/${id}/decision/`, { method: 'POST', body: { decision, reason }, auth: true }),
  declareRelationship: (id: string, reason: string) => request<unknown>(`/verification-tasks/${id}/declare-relationship/`, { method: 'POST', body: { reason }, auth: true }),
  submit: (id: string, values: { findings: Record<string, unknown>; report?: File | null; capture_id?: string; signed_and_stamped?: boolean }) => {
    const form = new FormData()
    form.append('findings', JSON.stringify(values.findings))
    form.append('device', deviceName())
    if (values.report) form.append('report', values.report)
    if (values.capture_id) form.append('capture_id', values.capture_id)
    if (values.signed_and_stamped !== undefined) form.append('signed_and_stamped', String(values.signed_and_stamped))
    return request<{ submission_id: string; version: number }>(`/verification-tasks/${id}/submit/`, { method: 'POST', body: form, auth: true })
  },
  report: (submissionId: string) => request<{ url: string }>(`/verification-tasks/submissions/${submissionId}/report/`, { auth: true }),

  // Verifier (FUL-05, PRO-02).
  startTasks: (jobId: string, professionalTypes: ProfessionalType[], surveyorCapture: boolean) =>
    request<Task[]>(`/full-checks/${jobId}/start/`, { method: 'POST', body: { professional_types: professionalTypes, surveyor_capture: surveyorCapture }, auth: true }),
  eligible: (jobId: string, type: ProfessionalType) => request<Professional[]>(`/full-checks/${jobId}/professionals/?type=${type}`, { auth: true }),
  assign: (taskId: string, profileId: string) => request<Task>(`/verification-tasks/${taskId}/assign/`, { method: 'POST', body: { profile_id: profileId }, auth: true }),
  correction: (taskId: string, reason: string) => request<Task>(`/verification-tasks/${taskId}/correction/`, { method: 'POST', body: { reason }, auth: true }),
}

// ---------------------------------------------------------------- site capture

export type CaptureCorner = { sequence: number; point: [number, number]; accuracy_m: string; observed_at: string }
export type CaptureAsset = { media_id: string; mime_type: string; source: 'CAMERA' | 'UPLOAD'; flags: string[]; distance_m: string | null }

export type Capture = {
  capture_id: string
  property_id: string
  status: 'DRAFT' | 'SUBMITTED'
  verification_task_id: string | null
  captured_at: string
  observed_point: { type: 'Point'; coordinates: [number, number] } | null
  observed_boundary: { type: 'Polygon'; coordinates: [number, number][][] } | null
  corners: CaptureCorner[]
  measured_area_sqm: string | null
  area_difference_percent: string | null
  review_flags: string[]
  overlap_findings: { kind: string; reference: string; name?: string }[]
  map_context: { corner_accuracy_m: number; attribution: string }
  assets: CaptureAsset[]
}

const point = (lng: number, lat: number) => ({ type: 'Point', coordinates: [lng, lat] })

export const captureApi = {
  list: (propertyId: string) => request<Page<Capture>>(`/properties/${encodeURIComponent(propertyId)}/site-captures/`, { auth: true }),
  get: (id: string) => request<Capture>(`/site-captures/${encodeURIComponent(id)}/`, { auth: true }),
  create: (propertyId: string, lng: number, lat: number, taskId?: string) =>
    request<Capture>(`/properties/${encodeURIComponent(propertyId)}/site-captures/`, { method: 'POST', body: { observed_point: point(lng, lat), ...(taskId ? { verification_task_id: taskId } : {}) }, auth: true }),
  corner: (id: string, lng: number, lat: number, accuracy: number, observedAt: string) =>
    request<{ sequence: number; accuracy_m: string }>(`/site-captures/${encodeURIComponent(id)}/corners/`, {
      method: 'POST',
      body: { point: point(lng, lat), accuracy_m: accuracy.toFixed(2), observed_at: observedAt, device: deviceName() },
      auth: true,
    }),
  undoCorner: (id: string) => request<{ removed_sequence: number }>(`/site-captures/${encodeURIComponent(id)}/corners/`, { method: 'DELETE', auth: true }),
  asset: (id: string, file: File, source: 'CAMERA' | 'UPLOAD') => {
    const form = new FormData()
    form.append('file', file)
    form.append('source', source)
    form.append('device', deviceName())
    return request<CaptureAsset>(`/site-captures/${encodeURIComponent(id)}/assets/`, { method: 'POST', body: form, auth: true })
  },
  submit: (id: string) => request<Capture>(`/site-captures/${encodeURIComponent(id)}/submit/`, { method: 'POST', body: {}, auth: true }),
  media: (mediaId: string) => request<{ url: string }>(`/media/${encodeURIComponent(mediaId)}/access/`, { auth: true }),
}
