import { SetupPasswordForm } from "./setup-form"

export default async function SetupPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>
}) {
  const { token = "" } = await searchParams
  return <SetupPasswordForm token={token} />
}
