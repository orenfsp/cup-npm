export type RuntimeConfig = Readonly<{
  apiBaseUrl: string
}>

const DEFAULT_API_BASE_URL = "http://localhost:8000"

function normalizeApiBaseUrl(value: string): string {
  const url = new URL(value)
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must use HTTP or HTTPS")
  }
  return url.toString().replace(/\/$/, "")
}

export const runtimeConfig: RuntimeConfig = Object.freeze({
  apiBaseUrl: normalizeApiBaseUrl(
    process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL
  ),
})

