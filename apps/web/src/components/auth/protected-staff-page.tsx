"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { staffHome, useAuth, type StaffRole } from "@/lib/auth"

export function ProtectedStaffPage({
  requiredRole,
  title,
}: {
  requiredRole: StaffRole
  title: string
}) {
  const router = useRouter()
  const { staff, status, logout } = useAuth()

  useEffect(() => {
    if (status === "anonymous") {
      router.replace("/staff/login")
    } else if (status === "authenticated" && staff?.must_change_password) {
      router.replace("/staff/change-password")
    } else if (
      status === "authenticated" &&
      staff &&
      staff.role !== requiredRole
    ) {
      router.replace(staffHome(staff.role))
    }
  }, [requiredRole, router, staff, status])

  if (status === "checking") {
    return <main className="m-auto p-6 text-sm text-muted-foreground">Checking session…</main>
  }

  if (status !== "authenticated" || !staff || staff.role !== requiredRole) {
    return <main className="m-auto p-6 text-sm text-muted-foreground">Authentication required.</main>
  }

  return (
    <main className="m-auto w-full max-w-lg p-6">
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>
            Phase 2B protected placeholder. Workflow features are not implemented yet.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>
            Signed in as <span className="font-medium">{staff.display_name}</span> ({staff.role}).
          </p>
          <Button
            variant="outline"
            onClick={() => void logout().finally(() => router.replace("/staff/login"))}
          >
            Sign out
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}
