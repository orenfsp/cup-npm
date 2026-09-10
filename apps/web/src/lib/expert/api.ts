import type { ApiRequestOptions } from "@/lib/api"
import type { ApplicantType, Category } from "@/lib/appeals"
import type { AppealPriority } from "@/lib/operator"

export type ExpertStatus =
  | "assigned"
  | "in_progress"
  | "needs_clarification"
  | "answer_ready"

export type ExpertQueueItem = {
  id: string
  applicant_type: ApplicantType
  category: Pick<Category, "id" | "slug" | "name"> | null
  status: ExpertStatus
  priority: AppealPriority
  crisis_flag: boolean
  created_at: string
  waiting_seconds: number
}

export type ExpertMessage = {
  id: string
  author_type: "applicant" | "specialist"
  author_label: string
  body: string
  created_at: string
}

export type ExpertDetail = ExpertQueueItem & {
  description: string | null
  intake_answers: Record<string, string | boolean | string[]>
  attachments: Array<{ id: string; mime_type: string; byte_size: number; created_at: string }>
  messages: ExpertMessage[]
  internal_notes: Array<{
    id: string
    author_staff_user_id: string
    author_label: string
    body: string
    created_at: string
  }>
  participants: Array<{
    staff_user_id: string
    display_name: string
    role: "primary" | "coexecutor"
    joined_at: string
  }>
  transfers: Array<{
    id: string
    target_staff_user_id: string | null
    status: "pending" | "approved" | "rejected"
    created_at: string
    resolved_at: string | null
  }>
  collaboration_candidates: Array<{
    expert_id: string
    display_name: string
    groups: string[]
    current_load: number
    capacity: number
    available: boolean
  }>
  is_primary: boolean
  updated_at: string
}

export type StaffRequest = <T>(path: string, options?: ApiRequestOptions) => Promise<T>

const action = (request: StaffRequest, path: string, json?: unknown) =>
  request<{ status: string }>(path, { method: "POST", json })

export const expertApi = {
  queue(request: StaffRequest, query = "") {
    return request<{ items: ExpertQueueItem[]; total: number; page: number; page_size: number }>(
      `api/v1/expert/appeals${query}`
    )
  },
  detail(request: StaffRequest, appealId: string) {
    return request<ExpertDetail>(`api/v1/expert/appeals/${appealId}`)
  },
  take(request: StaffRequest, appealId: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/take`)
  },
  message(request: StaffRequest, appealId: string, body: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/messages`, { body })
  },
  clarify(request: StaffRequest, appealId: string, message: string | null) {
    return action(request, `api/v1/expert/appeals/${appealId}/clarification`, { message })
  },
  note(request: StaffRequest, appealId: string, body: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/notes`, { body })
  },
  coexecutor(request: StaffRequest, appealId: string, expertId: string, reason: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/coexecutors`, {
      expert_id: expertId,
      reason,
    })
  },
  transfer(request: StaffRequest, appealId: string, expertId: string, reason: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/transfer-requests`, {
      target_expert_id: expertId,
      reason,
    })
  },
  cannotTake(request: StaffRequest, appealId: string, reason: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/cannot-take`, { reason })
  },
  recommendations(request: StaffRequest, appealId: string, body: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/recommendations`, { body })
  },
  acquireLock(request: StaffRequest, appealId: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/composer-lock`)
  },
  heartbeatLock(request: StaffRequest, appealId: string) {
    return action(request, `api/v1/expert/appeals/${appealId}/composer-lock/heartbeat`)
  },
  releaseLock(request: StaffRequest, appealId: string) {
    return request<{ status: string }>(`api/v1/expert/appeals/${appealId}/composer-lock`, {
      method: "DELETE",
    })
  },
  attachment(request: StaffRequest, appealId: string, attachmentId: string) {
    return request<Blob>(`api/v1/expert/appeals/${appealId}/attachments/${attachmentId}`, {
      responseType: "blob",
    })
  },
}
