import "server-only"

import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto"
import { neon } from "@neondatabase/serverless"

export type Comment = {
  id: number
  author: string
  content: string
  createdAt: string
}

export type Post = {
  id: number
  title: string
  content: string
  author: string
  views: number
  createdAt: string
  updatedAt: string
  comments: Comment[]
}

export type PostSummary = Omit<Post, "content" | "comments"> & {
  commentCount: number
}

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is not set. Copy .env.example to .env.local first.")
}

// Tables are created by `npm run db:setup` (scripts/db-setup.mjs).
const sql = neon(process.env.DATABASE_URL)

export function hashPassword(password: string) {
  const salt = randomBytes(16).toString("hex")
  return `${salt}:${scryptSync(password, salt, 32).toString("hex")}`
}

export function verifyPassword(password: string, stored: string) {
  const [salt, hash] = stored.split(":")
  const expected = Buffer.from(hash, "hex")
  const actual = scryptSync(password, salt, expected.length)
  return timingSafeEqual(expected, actual)
}

const iso = (value: Date | string) => new Date(value).toISOString()

/** Escapes LIKE wildcards so user input matches literally. */
const likePattern = (q: string) => `%${q.replace(/[\\%_]/g, "\\$&")}%`

export async function listPosts({
  query = "",
  page = 1,
  pageSize = 10,
}: {
  query?: string
  page?: number
  pageSize?: number
}) {
  const pattern = likePattern(query.trim())
  const [{ total }] = await sql`
    SELECT count(*)::int AS total FROM posts
    WHERE title ILIKE ${pattern} OR content ILIKE ${pattern} OR author ILIKE ${pattern}`
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const current = Math.min(Math.max(1, page), totalPages)

  const rows = await sql`
    SELECT p.id, p.title, p.author, p.views, p.created_at, p.updated_at,
           (SELECT count(*)::int FROM comments c WHERE c.post_id = p.id) AS comment_count
    FROM posts p
    WHERE p.title ILIKE ${pattern} OR p.content ILIKE ${pattern} OR p.author ILIKE ${pattern}
    ORDER BY p.id DESC
    LIMIT ${pageSize} OFFSET ${(current - 1) * pageSize}`

  const items: PostSummary[] = rows.map((r) => ({
    id: r.id,
    title: r.title,
    author: r.author,
    views: r.views,
    createdAt: iso(r.created_at),
    updatedAt: iso(r.updated_at),
    commentCount: r.comment_count,
  }))
  return { items, total: total as number, page: current, totalPages }
}

export async function getPost(id: number): Promise<Post | null> {
  const [post] = await sql`
    SELECT id, title, content, author, views, created_at, updated_at
    FROM posts WHERE id = ${id}`
  if (!post) return null
  const comments = await sql`
    SELECT id, author, content, created_at
    FROM comments WHERE post_id = ${id} ORDER BY id`
  return {
    id: post.id,
    title: post.title,
    content: post.content,
    author: post.author,
    views: post.views,
    createdAt: iso(post.created_at),
    updatedAt: iso(post.updated_at),
    comments: comments.map((c) => ({
      id: c.id,
      author: c.author,
      content: c.content,
      createdAt: iso(c.created_at),
    })),
  }
}

export async function incrementViews(id: number) {
  await sql`UPDATE posts SET views = views + 1 WHERE id = ${id}`
}

export async function createPost(input: {
  title: string
  content: string
  author: string
  password: string
}) {
  const [row] = await sql`
    INSERT INTO posts (title, content, author, password_hash)
    VALUES (${input.title}, ${input.content}, ${input.author}, ${hashPassword(input.password)})
    RETURNING id`
  return row.id as number
}

type Result = "ok" | "not-found" | "bad-password"

async function checkPostPassword(id: number, password: string): Promise<Result> {
  const [row] = await sql`SELECT password_hash FROM posts WHERE id = ${id}`
  if (!row) return "not-found"
  return verifyPassword(password, row.password_hash) ? "ok" : "bad-password"
}

export async function updatePost(
  id: number,
  password: string,
  input: { title: string; content: string; author: string }
): Promise<Result> {
  const result = await checkPostPassword(id, password)
  if (result !== "ok") return result
  await sql`
    UPDATE posts
    SET title = ${input.title}, content = ${input.content}, author = ${input.author},
        updated_at = now()
    WHERE id = ${id}`
  return "ok"
}

export async function deletePost(id: number, password: string): Promise<Result> {
  const result = await checkPostPassword(id, password)
  if (result !== "ok") return result
  // Comments are removed by ON DELETE CASCADE.
  await sql`DELETE FROM posts WHERE id = ${id}`
  return "ok"
}

export async function addComment(
  postId: number,
  input: { author: string; content: string; password: string }
): Promise<Result> {
  const rows = await sql`
    INSERT INTO comments (post_id, author, content, password_hash)
    SELECT id, ${input.author}, ${input.content}, ${hashPassword(input.password)}
    FROM posts WHERE id = ${postId}
    RETURNING id`
  return rows.length ? "ok" : "not-found"
}

export async function deleteComment(
  postId: number,
  commentId: number,
  password: string
): Promise<Result> {
  const [row] = await sql`
    SELECT password_hash FROM comments WHERE id = ${commentId} AND post_id = ${postId}`
  if (!row) return "not-found"
  if (!verifyPassword(password, row.password_hash)) return "bad-password"
  await sql`DELETE FROM comments WHERE id = ${commentId}`
  return "ok"
}
