import { apiClient, type ApiRequestOptions } from "@/lib/api/client"

export type StaffRole = "operator" | "expert" | "admin"

export type StaffProfile = {
  id: string
  login: string
  display_name: string
  role: StaffRole
  must_change_password: boolean
}

export type AuthResponse = {
  access_token: string
  token_type: "bearer"
  expires_in: number
  staff: StaffProfile
}

export function loginStaff(login: string, password: string, signal?: AbortSignal) {
  return apiClient.request<AuthResponse>("api/v1/auth/login", {
    method: "POST",
    credentials: "include",
    json: { login, password },
    signal,
  })
}

export function refreshStaffSession(signal?: AbortSignal) {
  return apiClient.request<AuthResponse>("api/v1/auth/refresh", {
    method: "POST",
    credentials: "include",
    signal,
  })
}

export function getCurrentStaff(accessToken: string, signal?: AbortSignal) {
  return apiClient.request<StaffProfile>("api/v1/auth/me", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
    signal,
  })
}

export function logoutStaff(signal?: AbortSignal) {
  return apiClient.request<{ status: "ok" }>("api/v1/auth/logout", {
    method: "POST",
    credentials: "include",
    signal,
  })
}

export function withAccessToken(
  accessToken: string,
  options: ApiRequestOptions = {}
): ApiRequestOptions {
  const headers = new Headers(options.headers)
  headers.set("Authorization", `Bearer ${accessToken}`)
  return { ...options, headers }
}

export function staffHome(role: StaffRole) {
  return `/staff/${role}`
}
