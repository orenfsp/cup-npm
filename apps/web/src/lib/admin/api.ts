import { apiClient, type ApiRequestOptions } from "@/lib/api"

export type StaffRequest = <T>(path: string, options?: ApiRequestOptions) => Promise<T>
export type StaffRole = "operator" | "expert" | "admin"

export type StaffItem = {
  id: string
  login: string
  email: string | null
  display_name: string
  role: StaffRole
  is_active: boolean
  created_at: string
  last_login_at: string | null
  public_specialist_label: string | null
  max_active_appeals: number | null
  active_appeals: number
  group_ids: string[]
  password_configured: boolean
}

export type StaffCreateResult = {
  staff: StaffItem
  temporary_password: string
}

export type ApplicantTypeItem = {
  id: string
  code: string
  label: string
  description: string | null
  tone: "informal" | "formal"
  is_active: boolean
  sort_order: number
}

export type CategoryItem = {
  id: string
  slug: string
  name: string
  description: string | null
  is_active: boolean
  sort_order: number
}

export type QuestionItem = {
  id: string
  code: string
  label: string
  help_text: string | null
  field_type: "short_text" | "long_text" | "single_choice" | "multi_choice" | "boolean"
  options: string[]
  required: boolean
  is_active: boolean
  sort_order: number
  category_ids: string[]
}

export type GroupItem = {
  id: string
  slug: string
  name: string
  description: string | null
  is_active: boolean
  member_ids: string[]
  active_experts: number
  available_experts: number
  active_load: number
  total_capacity: number
}

export type RoutingItem = { category_id: string; group_ids: string[] }

export type CrisisRuleItem = {
  id: string
  phrase: string
  normalized_phrase: string
  is_active: boolean
  allow_compact_match: boolean
  sort_order: number
}

export type SupportResourceItem = {
  id: string
  title: string
  description: string
  phone: string | null
  url: string | null
  region: string | null
  is_active: boolean
  sort_order: number
}

export type SafeSettings = {
  settings: Array<{ key: string; value: string | number; editable: false; source: "environment" }>
  secret_settings_excluded: true
}

export type AdminAppealItem = {
  id: string
  applicant_type: string
  category_id: string | null
  category_name: string | null
  status: string
  priority: "low" | "standard" | "urgent"
  crisis_flag: boolean
  assigned_expert_id: string | null
  assigned_expert_display_name: string | null
  created_at: string
  updated_at: string
  operator_accepted_at: string | null
  first_specialist_response_at: string | null
  answer_ready_at: string | null
  completed_at: string | null
}

export type AuditItem = {
  id: string
  actor_staff_user_id: string | null
  actor_display_name: string | null
  action: string
  entity_type: string
  entity_id: string | null
  reason: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export type Analytics = {
  date_from: string
  date_to: string
  total: number
  new: number
  active: number
  completed: number
  urgent_share: number | null
  returned_share: number | null
  avg_operator_acceptance_seconds: number | null
  avg_first_response_seconds: number | null
  avg_resolution_seconds: number | null
  by_category: Array<{ key: string; count: number }>
  by_applicant_type: Array<{ key: string; count: number }>
  by_status: Array<{ key: string; count: number }>
  daily: Array<{ date: string; count: number }>
  workloads: Array<{
    staff_user_id: string
    display_name: string
    role: StaffRole
    active_appeals: number
    capacity: number | null
  }>
}

const json = (method: string, value?: unknown): ApiRequestOptions => ({ method, json: value })

export const adminApi = {
  staff: (request: StaffRequest) => request<StaffItem[]>("api/v1/admin/staff"),
  createStaff: (request: StaffRequest, value: unknown) =>
    request<StaffCreateResult>(
      "api/v1/admin/staff",
      json("POST", value)
    ),
  updateStaff: (request: StaffRequest, id: string, value: unknown) =>
    request<StaffItem>(`api/v1/admin/staff/${id}`, json("PATCH", value)),
  invitation: (request: StaffRequest, id: string, reset = false) =>
    request<{ staff: StaffItem; email_sent: boolean; message: string }>(
      `api/v1/admin/staff/${id}/${reset ? "password-reset" : "invitation"}`,
      json("POST")
    ),
  applicantTypes: (request: StaffRequest) =>
    request<ApplicantTypeItem[]>("api/v1/admin/applicant-types"),
  createApplicantType: (request: StaffRequest, value: unknown) =>
    request<ApplicantTypeItem>("api/v1/admin/applicant-types", json("POST", value)),
  updateApplicantType: (request: StaffRequest, id: string, value: unknown) =>
    request<ApplicantTypeItem>(`api/v1/admin/applicant-types/${id}`, json("PATCH", value)),
  categories: (request: StaffRequest) => request<CategoryItem[]>("api/v1/admin/categories"),
  createCategory: (request: StaffRequest, value: unknown) =>
    request<CategoryItem>("api/v1/admin/categories", json("POST", value)),
  updateCategory: (request: StaffRequest, id: string, value: unknown) =>
    request<CategoryItem>(`api/v1/admin/categories/${id}`, json("PATCH", value)),
  questions: (request: StaffRequest) => request<QuestionItem[]>("api/v1/admin/questions"),
  createQuestion: (request: StaffRequest, value: unknown) =>
    request<QuestionItem>("api/v1/admin/questions", json("POST", value)),
  updateQuestion: (request: StaffRequest, id: string, value: unknown) =>
    request<QuestionItem>(`api/v1/admin/questions/${id}`, json("PATCH", value)),
  setCategoryQuestions: (request: StaffRequest, id: string, questions: unknown[]) =>
    request<{ status: "saved" }>(
      `api/v1/admin/categories/${id}/questions`,
      json("PUT", { questions })
    ),
  groups: (request: StaffRequest) => request<GroupItem[]>("api/v1/admin/groups"),
  createGroup: (request: StaffRequest, value: unknown) =>
    request<GroupItem>("api/v1/admin/groups", json("POST", value)),
  updateGroup: (request: StaffRequest, id: string, value: unknown) =>
    request<GroupItem>(`api/v1/admin/groups/${id}`, json("PATCH", value)),
  setMembers: (request: StaffRequest, id: string, expertIds: string[]) =>
    request<{ status: "saved" }>(
      `api/v1/admin/groups/${id}/members`,
      json("PUT", { expert_ids: expertIds })
    ),
  routing: (request: StaffRequest) => request<RoutingItem[]>("api/v1/admin/routing"),
  setRouting: (request: StaffRequest, id: string, groupIds: string[]) =>
    request<{ status: "saved" }>(
      `api/v1/admin/routing/${id}`,
      json("PUT", { group_ids: groupIds })
    ),
  crisisRules: (request: StaffRequest) =>
    request<CrisisRuleItem[]>("api/v1/admin/crisis-rules"),
  createCrisisRule: (request: StaffRequest, value: unknown) =>
    request<CrisisRuleItem>("api/v1/admin/crisis-rules", json("POST", value)),
  updateCrisisRule: (request: StaffRequest, id: string, value: unknown) =>
    request<CrisisRuleItem>(`api/v1/admin/crisis-rules/${id}`, json("PATCH", value)),
  testCrisisRule: (request: StaffRequest, text: string) =>
    request<{ crisis_detected: boolean; matched_rules: Array<{ id: string; phrase: string }> }>(
      "api/v1/admin/crisis-rules/test",
      json("POST", { text })
    ),
  supportResources: (request: StaffRequest) =>
    request<SupportResourceItem[]>("api/v1/admin/support-resources"),
  createSupportResource: (request: StaffRequest, value: unknown) =>
    request<SupportResourceItem>("api/v1/admin/support-resources", json("POST", value)),
  updateSupportResource: (request: StaffRequest, id: string, value: unknown) =>
    request<SupportResourceItem>(`api/v1/admin/support-resources/${id}`, json("PATCH", value)),
  settings: (request: StaffRequest) => request<SafeSettings>("api/v1/admin/settings"),
  appeals: (request: StaffRequest) =>
    request<{ items: AdminAppealItem[]; total: number }>("api/v1/admin/appeals"),
  interveneAppeal: (request: StaffRequest, id: string, value: unknown) =>
    request<AdminAppealItem>(`api/v1/admin/appeals/${id}`, json("PATCH", value)),
  audit: (request: StaffRequest, query = "") =>
    request<{ items: AuditItem[]; total: number }>(`api/v1/admin/audit${query}`),
  analytics: (request: StaffRequest, dateFrom: string, dateTo: string) =>
    request<Analytics>(
      `api/v1/admin/analytics?date_from=${encodeURIComponent(dateFrom)}&date_to=${encodeURIComponent(dateTo)}`
    ),
  exportAnalytics: (request: StaffRequest, dateFrom: string, dateTo: string) =>
    request<Blob>(
      `api/v1/admin/analytics/export?date_from=${encodeURIComponent(dateFrom)}&date_to=${encodeURIComponent(dateTo)}`,
      { responseType: "blob" }
    ),
}

export function setupStaffPassword(token: string, password: string) {
  return apiClient.request<{ status: "password_set" }>("api/v1/auth/setup-password", {
    method: "POST",
    json: { token, password },
  })
}
