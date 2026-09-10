import { runtimeConfig } from "@/lib/config"

type ApiErrorEnvelope = {
  error?: {
    code?: unknown
    message?: unknown
  }
}

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  json?: unknown
  body?: BodyInit
  responseType?: "json" | "blob"
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
  }
}

export class ApiClient {
  constructor(private readonly baseUrl: string) {}

  async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    if (/^https?:\/\//i.test(path)) {
      throw new Error("API paths must be relative to the configured base URL")
    }

    const {
      headers: suppliedHeaders,
      json,
      body,
      responseType = "json",
      ...requestOptions
    } = options
    if (json !== undefined && body !== undefined) {
      throw new Error("API requests cannot include both JSON and a raw body")
    }
    const headers = new Headers(suppliedHeaders)
    headers.set("Accept", responseType === "blob" ? "image/*" : "application/json")
    if (json !== undefined) {
      headers.set("Content-Type", "application/json")
    }

    const normalizedPath = path.replace(/^\/+/, "")
    const response = await fetch(`${this.baseUrl}/${normalizedPath}`, {
      ...requestOptions,
      headers,
      body: json === undefined ? body : JSON.stringify(json),
    })

    if (response.status === 204) {
      if (!response.ok) {
        throw new ApiError(response.status, "http_error", response.statusText)
      }
      return undefined as T
    }

    if (response.ok && responseType === "blob") {
      return (await response.blob()) as T
    }

    const responseText = await response.text()
    let payload: unknown
    try {
      payload = responseText ? JSON.parse(responseText) : undefined
    } catch {
      throw new ApiError(
        response.status,
        "invalid_response",
        "The API returned an invalid JSON response."
      )
    }

    if (!response.ok) {
      const envelope = payload as ApiErrorEnvelope | undefined
      const code =
        typeof envelope?.error?.code === "string"
          ? envelope.error.code
          : "http_error"
      const message =
        typeof envelope?.error?.message === "string"
          ? envelope.error.message
          : `API request failed with status ${response.status}.`
      throw new ApiError(response.status, code, message)
    }

    return payload as T
  }

  get<T>(path: string, options: Omit<ApiRequestOptions, "method" | "json"> = {}) {
    return this.request<T>(path, { ...options, method: "GET" })
  }
}

export const apiClient = new ApiClient(runtimeConfig.apiBaseUrl)
