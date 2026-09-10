import { apiClient } from "@/lib/api"

export type ApplicantType = string

export type ApplicantTypeConfig = {
  code: string
  label: string
  description: string | null
  tone: "informal" | "formal"
}

export type Category = {
  id: string
  slug: string
  name: string
  description: string | null
  requires_description: boolean
}

export type IntakeQuestion = {
  id: string
  prompt_student: string
  prompt_formal: string
  max_length: number
  optional: boolean
  label: string
  help_text: string | null
  field_type: "short_text" | "long_text" | "single_choice" | "multi_choice" | "boolean"
  options: string[]
  required: boolean
  category_ids: string[]
  required_category_ids: string[]
}

export type CrisisResource = {
  title: string
  message: string
  phone: string | null
  url: string | null
  requires_organizer_verification: boolean
}

export type PublicReference = {
  applicant_types: ApplicantTypeConfig[]
  categories: Category[]
  intake_questions: IntakeQuestion[]
  crisis_support_resources: CrisisResource[]
}

export type CreatedAppeal = {
  track_number: string
  status: string
  status_text: string
  crisis_flag: boolean
  show_crisis_support: boolean
  crisis_support_resources: CrisisResource[]
}

export type CurrentAppeal = {
  applicant_type: ApplicantType
  category: Category | null
  status: string
  status_text: string
  crisis_flag: boolean
  show_crisis_support: boolean
  crisis_support_resources: CrisisResource[]
  created_at: string
  updated_at: string
  timeline: Array<{ status: string; text: string; occurred_at: string }>
  rejection_reason: string | null
  return_count: number
  max_returns: number
}

export type PublicMessage = {
  id: string
  author_type: "applicant" | "specialist"
  author_label: string
  body: string
  created_at: string
}

export type CreateAppealInput = {
  applicant_type: ApplicantType
  category_id: string | null
  description: string | null
  intake_answers: Record<string, string | boolean | string[]> | null
}

const credentialed = { credentials: "include" as const }

export const publicAppealsApi = {
  reference(signal?: AbortSignal) {
    return apiClient.get<PublicReference>("api/v1/public/reference", { signal })
  },
  create(input: CreateAppealInput, signal?: AbortSignal) {
    return apiClient.request<CreatedAppeal>("api/v1/public/appeals", {
      method: "POST",
      json: input,
      signal,
      ...credentialed,
    })
  },
  access(trackNumber: string) {
    return apiClient.request<{ status: "ok" }>("api/v1/public/appeals/access", {
      method: "POST",
      json: { track_number: trackNumber },
      ...credentialed,
    })
  },
  current(signal?: AbortSignal) {
    return apiClient.get<CurrentAppeal>("api/v1/public/appeals/current", {
      signal,
      ...credentialed,
    })
  },
  leave() {
    return apiClient.request<{ status: "left" }>("api/v1/public/appeals/leave", {
      method: "POST",
      ...credentialed,
    })
  },
  saveCrisisContact(contact: string) {
    return apiClient.request<{ status: "saved" }>(
      "api/v1/public/appeals/current/crisis-contact",
      { method: "PUT", json: { contact }, ...credentialed }
    )
  },
  uploadAttachment(file: File) {
    const body = new FormData()
    body.append("file", file)
    return apiClient.request<{ status: "stored"; mime_type: string; byte_size: number }>(
      "api/v1/public/appeals/current/attachments",
      { method: "POST", body, ...credentialed }
    )
  },
  messages(signal?: AbortSignal) {
    return apiClient.get<{ messages: PublicMessage[] }>(
      "api/v1/public/appeals/current/messages",
      { signal, ...credentialed }
    )
  },
  sendMessage(body: string) {
    return apiClient.request<{ status: "saved" }>(
      "api/v1/public/appeals/current/messages",
      { method: "POST", json: { body }, ...credentialed }
    )
  },
  resolve(choice: "helped" | "not_helped", explanation?: string) {
    return apiClient.request<{ status: "saved" }>("api/v1/public/appeals/current/resolve", {
      method: "POST",
      json: { choice, explanation: explanation || null },
      ...credentialed,
    })
  },
  feedback(rating: number, comment?: string) {
    return apiClient.request<{ status: "saved" }>(
      "api/v1/public/appeals/current/feedback",
      { method: "POST", json: { rating, comment: comment || null }, ...credentialed }
    )
  },
  complaint(body: string) {
    return apiClient.request<{ status: "saved" }>(
      "api/v1/public/appeals/current/complaints",
      { method: "POST", json: { body }, ...credentialed }
    )
  },
}
