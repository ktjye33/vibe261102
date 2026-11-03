"use client"

import Link from "next/link"
import { useActionState } from "react"

import type { FormState } from "@/lib/actions"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

type PostFormProps = {
  action: (prev: FormState, formData: FormData) => Promise<FormState>
  defaultValues?: { title: string; content: string; author: string }
  submitLabel: string
  cancelHref: string
}

export function PostForm({ action, defaultValues, submitLabel, cancelHref }: PostFormProps) {
  const [state, formAction, pending] = useActionState(action, {})
  const values = state.values ?? defaultValues

  return (
    // key forces inputs to pick up returned values after a failed submit
    <form action={formAction} className="grid gap-5" key={JSON.stringify(values)}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="author">작성자</Label>
          <Input id="author" name="author" maxLength={20} defaultValue={values?.author} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="password">비밀번호</Label>
          <Input
            id="password"
            name="password"
            type="password"
            minLength={4}
            placeholder={defaultValues ? "작성 시 입력한 비밀번호" : "수정/삭제 시 필요합니다"}
            required
          />
        </div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="title">제목</Label>
        <Input id="title" name="title" maxLength={100} defaultValue={values?.title} required />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="content">내용</Label>
        <Textarea
          id="content"
          name="content"
          rows={12}
          maxLength={10000}
          defaultValue={values?.content}
          required
        />
      </div>
      {state.error && (
        <p role="alert" className="text-sm text-destructive">
          {state.error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Link href={cancelHref} className={buttonVariants({ variant: "outline" })}>
          취소
        </Link>
        <Button type="submit" disabled={pending}>
          {pending ? "저장 중..." : submitLabel}
        </Button>
      </div>
    </form>
  )
}
