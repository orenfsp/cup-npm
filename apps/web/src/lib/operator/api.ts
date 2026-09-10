import type { ApiRequestOptions } from "@/lib/api"
import type { ApplicantType, Category } from "@/lib/appeals"

export type AppealPriority = "low" | "standard" | "urgent"
export type AppealStatus = "new" | "assigned" | "returned" | "rejected"

export type OperatorQueueItem = {
  id: string
  applicant_type: ApplicantType
  category: Pick<Category, "id" | "slug" | "name"> | null
  status: AppealStatus
  priority: AppealPriority
  crisis_flag: boolean
  assigned: boolean
  created_at: string
  waiting_since: string
  waiting_seconds: number
  is_overdue: boolean
}

export type RoutingCandidate = {
  expert_id: string
  display_name: string
  groups: string[]
  current_load: number
  capacity: number
  available: boolean
}

export type OperatorAppealDetail = Omit<OperatorQueueItem, "assigned" | "waiting_since"> & {
  description: string | null
  intake_answers: Record<string, string | boolean | string[]>
  suggested_category: Pick<Category, "id" | "slug" | "name"> | null
  updated_at: string
  operator_accepted_at: string | null
  attachments: Array<{
    id: string
    mime_type: string
    byte_size: number
    created_at: string
  }>
  assigned_expert: { id: string; display_name: string } | null
  status_history: Array<{
    from_status: string | null
    to_status: string
    created_at: string
  }>
  assignment_history: Array<{
    from_expert_id: string | null
    to_expert_id: string | null
    created_at: string
  }>
  return_explanations: Array<{
    id: string
    return_number: number
    body: string
    created_at: string
  }>
  routing: {
    state: string
    recommended_expert: RoutingCandidate | null
    candidates: RoutingCandidate[]
    reason: string
  }
}

export type OperatorQueue = {
  items: OperatorQueueItem[]
  total: number
  page: number
  page_size: number
  counters: { crisis: number; new: number; returned: number; overdue: number }
}

export type OperatorReference = {
  categories: Array<Pick<Category, "id" | "slug" | "name">>
}

export type OperatorTransferRequest = {
  id: string
  appeal_id: string
  requester_display_name: string
  target_expert_id: string | null
  target_display_name: string | null
  reason: string
  status: "pending" | "approved" | "rejected"
  created_at: string
  request_kind: "targeted_transfer" | "cannot_take"
  eligible_experts: RoutingCandidate[]
}

export type StaffRequest = <T>(path: string, options?: ApiRequestOptions) => Promise<T>

export const operatorApi = {
  queue(request: StaffRequest, query = "") {
    return request<OperatorQueue>(`api/v1/operator/appeals${query}`)
  },
  reference(request: StaffRequest) {
    return request<OperatorReference>("api/v1/operator/reference")
  },
  detail(request: StaffRequest, appealId: string) {
    return request<OperatorAppealDetail>(`api/v1/operator/appeals/${appealId}`)
  },
  triage(
    request: StaffRequest,
    appealId: string,
    input: { category_id?: string; priority?: AppealPriority }
  ) {
    return request<{ status: "ok" }>(`api/v1/operator/appeals/${appealId}/triage`, {
      method: "PATCH",
      json: input,
    })
  },
  assign(request: StaffRequest, appealId: string, expertId: string) {
    return request<{ status: "ok" }>(`api/v1/operator/appeals/${appealId}/assign`, {
      method: "POST",
      json: { expert_id: expertId },
    })
  },
  reject(
    request: StaffRequest,
    appealId: string,
    kind: "spam" | "outside_competence",
    reason: string
  ) {
    return request<{ status: "ok" }>(`api/v1/operator/appeals/${appealId}/reject`, {
      method: "POST",
      json: { kind, reason },
    })
  },
  crisisContact(request: StaffRequest, appealId: string) {
    return request<{ contact: string }>(
      `api/v1/operator/appeals/${appealId}/crisis-contact`
    )
  },
  attachment(request: StaffRequest, appealId: string, attachmentId: string) {
    return request<Blob>(
      `api/v1/operator/appeals/${appealId}/attachments/${attachmentId}`,
      { responseType: "blob" }
    )
  },
  transferRequests(request: StaffRequest) {
    return request<OperatorTransferRequest[]>("api/v1/operator/transfer-requests")
  },
  resolveTransfer(
    request: StaffRequest,
    transferId: string,
    decision: "approve" | "reject",
    replacementExpertId?: string
  ) {
    return request<{ status: "ok" }>(
      `api/v1/operator/transfer-requests/${transferId}/resolve`,
      {
        method: "POST",
        json: { decision, replacement_expert_id: replacementExpertId ?? null },
      }
    )
  },
  complaints(request: StaffRequest, appealId: string) {
    return request<Array<{ id: string; body: string; created_at: string }>>(
      `api/v1/operator/appeals/${appealId}/complaints`
    )
  },
}
