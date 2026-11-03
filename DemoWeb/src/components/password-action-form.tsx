"use client"

import { useActionState, useState } from "react"

import type { FormState } from "@/lib/actions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type PasswordActionFormProps = {
  action: (prev: FormState, formData: FormData) => Promise<FormState>
  label: string
  confirmLabel?: string
  size?: "sm" | "xs"
}

/** A destructive button that reveals a password prompt before running `action`. */
export function PasswordActionForm({
  action,
  label,
  confirmLabel = "확인",
  size = "sm",
}: PasswordActionFormProps) {
  const [open, setOpen] = useState(false)
  const [state, formAction, pending] = useActionState(action, {})

  if (!open) {
    return (
      <Button variant="destructive" size={size} onClick={() => setOpen(true)}>
        {label}
      </Button>
    )
  }

  return (
    <form action={formAction} className="flex flex-wrap items-center gap-2">
      <Input
        name="password"
        type="password"
        placeholder="비밀번호"
        aria-label="비밀번호"
        className="h-7 w-32"
        autoFocus
        required
      />
      <Button type="submit" variant="destructive" size={size} disabled={pending}>
        {pending ? "처리 중..." : confirmLabel}
      </Button>
      <Button type="button" variant="ghost" size={size} onClick={() => setOpen(false)}>
        취소
      </Button>
      {state.error && (
        <span role="alert" className="w-full text-xs text-destructive">
          {state.error}
        </span>
      )}
    </form>
  )
}
