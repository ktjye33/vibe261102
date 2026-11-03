"use client"

import { useActionState } from "react"

import type { FormState } from "@/lib/actions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

export function CommentForm({
  action,
}: {
  action: (prev: FormState, formData: FormData) => Promise<FormState>
}) {
  const [state, formAction, pending] = useActionState(action, {})

  return (
    // A successful submit returns no values, which resets the form via the key.
    <form action={formAction} className="grid gap-2" key={JSON.stringify(state)}>
      <div className="grid gap-2 sm:grid-cols-2">
        <Input
          name="author"
          placeholder="작성자"
          aria-label="작성자"
          maxLength={20}
          defaultValue={state.values?.author}
          required
        />
        <Input
          name="password"
          type="password"
          placeholder="비밀번호 (삭제 시 필요)"
          aria-label="비밀번호"
          minLength={4}
          required
        />
      </div>
      <Textarea
        name="content"
        placeholder="댓글을 입력하세요"
        aria-label="댓글 내용"
        rows={3}
        maxLength={1000}
        defaultValue={state.values?.content}
        required
      />
      <div className="flex items-center justify-between gap-2">
        <span role="alert" className="text-sm text-destructive">
          {state.error}
        </span>
        <Button type="submit" disabled={pending}>
          {pending ? "등록 중..." : "댓글 등록"}
        </Button>
      </div>
    </form>
  )
}
