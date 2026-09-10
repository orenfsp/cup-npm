"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"

import { ApiError, apiClient, type ApiRequestOptions } from "@/lib/api/client"
import {
  loginStaff,
  logoutStaff,
  refreshStaffSession,
  withAccessToken,
  type AuthResponse,
  type StaffProfile,
} from "@/lib/auth/api"

type AuthStatus = "checking" | "authenticated" | "anonymous"

type AuthContextValue = {
  staff: StaffProfile | null
  status: AuthStatus
  login: (login: string, password: string) => Promise<StaffProfile>
  logout: () => Promise<void>
  request: <T>(path: string, options?: ApiRequestOptions) => Promise<T>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [staff, setStaff] = useState<StaffProfile | null>(null)
  const [status, setStatus] = useState<AuthStatus>("checking")
  const accessTokenRef = useRef<string | null>(null)
  const refreshPromiseRef = useRef<Promise<AuthResponse> | null>(null)

  const acceptAuthentication = useCallback((result: AuthResponse) => {
    accessTokenRef.current = result.access_token
    setStaff(result.staff)
    setStatus("authenticated")
    return result
  }, [])

  const clearAuthentication = useCallback(() => {
    accessTokenRef.current = null
    setStaff(null)
    setStatus("anonymous")
  }, [])

  const refresh = useCallback(() => {
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current
    }
    const pending = refreshStaffSession()
      .then(acceptAuthentication)
      .catch((error: unknown) => {
        clearAuthentication()
        throw error
      })
      .finally(() => {
        refreshPromiseRef.current = null
      })
    refreshPromiseRef.current = pending
    return pending
  }, [acceptAuthentication, clearAuthentication])

  useEffect(() => {
    void refresh().catch(() => undefined)
  }, [refresh])

  const login = useCallback(
    async (loginValue: string, password: string) => {
      const result = await loginStaff(loginValue, password)
      acceptAuthentication(result)
      return result.staff
    },
    [acceptAuthentication]
  )

  const logout = useCallback(async () => {
    try {
      await logoutStaff()
    } finally {
      clearAuthentication()
    }
  }, [clearAuthentication])

  const request = useCallback(
    async <T,>(path: string, options: ApiRequestOptions = {}) => {
      let accessToken = accessTokenRef.current
      if (!accessToken) {
        accessToken = (await refresh()).access_token
      }
      try {
        return await apiClient.request<T>(path, withAccessToken(accessToken, options))
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) {
          throw error
        }
        const renewed = await refresh()
        return apiClient.request<T>(
          path,
          withAccessToken(renewed.access_token, options)
        )
      }
    },
    [refresh]
  )

  const value = useMemo<AuthContextValue>(
    () => ({ staff, status, login, logout, request }),
    [staff, status, login, logout, request]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider")
  }
  return context
}
