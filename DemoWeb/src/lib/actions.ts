"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

import * as db from "@/lib/db"

export type FormState = {
  error?: string
  values?: Record<string, string>
  /** Changes on every successful submit so clients can reset their form. */
  submittedAt?: number
}

function field(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim()
}

function postFields(formData: FormData) {
  return {
    title: field(formData, "title"),
    content: field(formData, "content"),
    author: field(formData, "author"),
    password: String(formData.get("password") ?? ""),
  }
}

function validatePost(p: ReturnType<typeof postFields>) {
  if (!p.title) return "제목을 입력해 주세요."
  if (p.title.length > 100) return "제목은 100자 이하로 입력해 주세요."
  if (!p.author) return "작성자를 입력해 주세요."
  if (p.author.length > 20) return "작성자는 20자 이하로 입력해 주세요."
  if (!p.content) return "내용을 입력해 주세요."
  if (p.content.length > 10_000) return "내용은 10,000자 이하로 입력해 주세요."
  if (p.password.length < 4) return "비밀번호는 4자 이상 입력해 주세요."
  return null
}

const RESULT_MESSAGES = {
  "not-found": "존재하지 않는 글입니다.",
  "bad-password": "비밀번호가 일치하지 않습니다.",
} as const

export async function createPostAction(
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const input = postFields(formData)
  const values = { title: input.title, content: input.content, author: input.author }
  const error = validatePost(input)
  if (error) return { error, values }

  const id = await db.createPost(input)
  revalidatePath("/")
  redirect(`/posts/${id}`)
}

export async function updatePostAction(
  id: number,
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const input = postFields(formData)
  const { password, ...values } = input
  const error = validatePost(input)
  if (error) return { error, values }

  const result = await db.updatePost(id, password, values)
  if (result !== "ok") return { error: RESULT_MESSAGES[result], values }
  revalidatePath("/")
  revalidatePath(`/posts/${id}`)
  redirect(`/posts/${id}`)
}

export async function deletePostAction(
  id: number,
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const result = await db.deletePost(id, String(formData.get("password") ?? ""))
  if (result !== "ok") return { error: RESULT_MESSAGES[result] }
  revalidatePath("/")
  redirect("/")
}

export async function addCommentAction(
  postId: number,
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const author = field(formData, "author")
  const content = field(formData, "content")
  const password = String(formData.get("password") ?? "")
  const values = { author, content }

  if (!author || author.length > 20) return { error: "작성자는 1~20자로 입력해 주세요.", values }
  if (!content || content.length > 1000) return { error: "댓글은 1~1,000자로 입력해 주세요.", values }
  if (password.length < 4) return { error: "비밀번호는 4자 이상 입력해 주세요.", values }

  const result = await db.addComment(postId, { author, content, password })
  if (result !== "ok") return { error: RESULT_MESSAGES[result], values }
  revalidatePath(`/posts/${postId}`)
  return { submittedAt: Date.now() }
}

export async function deleteCommentAction(
  postId: number,
  commentId: number,
  _prev: FormState,
  formData: FormData
): Promise<FormState> {
  const result = await db.deleteComment(
    postId,
    commentId,
    String(formData.get("password") ?? "")
  )
  if (result !== "ok") return { error: RESULT_MESSAGES[result] }
  revalidatePath(`/posts/${postId}`)
  return {}
}
