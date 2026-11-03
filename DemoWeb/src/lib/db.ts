import "server-only"

import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto"
import { mkdir, readFile, rename, writeFile } from "node:fs/promises"
import path from "node:path"

export type Comment = {
  id: number
  author: string
  content: string
  passwordHash: string
  createdAt: string
}

export type Post = {
  id: number
  title: string
  content: string
  author: string
  passwordHash: string
  views: number
  createdAt: string
  updatedAt: string
  comments: Comment[]
}

type Database = {
  nextPostId: number
  nextCommentId: number
  posts: Post[]
}

const DATA_DIR = path.join(process.cwd(), "data")
const DATA_FILE = path.join(DATA_DIR, "board.json")

// Serialize writes so concurrent requests don't clobber each other.
let queue: Promise<unknown> = Promise.resolve()

async function load(): Promise<Database> {
  try {
    return JSON.parse(await readFile(DATA_FILE, "utf8")) as Database
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error
    return seed()
  }
}

async function save(db: Database) {
  await mkdir(DATA_DIR, { recursive: true })
  const tmp = `${DATA_FILE}.tmp`
  await writeFile(tmp, JSON.stringify(db, null, 2), "utf8")
  await rename(tmp, DATA_FILE)
}

function mutate<T>(fn: (db: Database) => T): Promise<T> {
  const run = queue.then(async () => {
    const db = await load()
    const result = fn(db)
    await save(db)
    return result
  })
  queue = run.catch(() => {})
  return run
}

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

function seed(): Database {
  const now = Date.now()
  const at = (minutesAgo: number) =>
    new Date(now - minutesAgo * 60_000).toISOString()
  const pw = hashPassword("1234")
  const samples = [
    ["게시판에 오신 것을 환영합니다", "관리자", "자유롭게 글을 작성해 주세요.\n작성 시 입력한 비밀번호로 수정/삭제할 수 있습니다."],
    ["Next.js 16 사용 후기", "개발자", "Cache Components와 Server Actions 조합이 꽤 편리하네요."],
    ["shadcn/ui 컴포넌트 추천", "디자이너", "Card, Table, Badge 정도만 있어도 게시판 UI는 충분합니다."],
  ] as const
  return {
    nextPostId: samples.length + 1,
    nextCommentId: 2,
    posts: samples.map(([title, author, content], i) => ({
      id: i + 1,
      title,
      author,
      content,
      passwordHash: pw,
      views: 0,
      createdAt: at((samples.length - i) * 90),
      updatedAt: at((samples.length - i) * 90),
      comments:
        i === 0
          ? [{ id: 1, author: "방문자", content: "첫 댓글입니다!", passwordHash: pw, createdAt: at(30) }]
          : [],
    })),
  }
}

export type PostSummary = Omit<Post, "content" | "passwordHash" | "comments"> & {
  commentCount: number
}

export async function listPosts({
  query = "",
  page = 1,
  pageSize = 10,
}: {
  query?: string
  page?: number
  pageSize?: number
}) {
  const db = await load()
  const q = query.trim().toLowerCase()
  const filtered = db.posts
    .filter(
      (p) =>
        !q ||
        p.title.toLowerCase().includes(q) ||
        p.content.toLowerCase().includes(q) ||
        p.author.toLowerCase().includes(q)
    )
    .sort((a, b) => b.id - a.id)
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const current = Math.min(Math.max(1, page), totalPages)
  const items: PostSummary[] = filtered
    .slice((current - 1) * pageSize, current * pageSize)
    .map((p) => ({
      id: p.id,
      title: p.title,
      author: p.author,
      views: p.views,
      createdAt: p.createdAt,
      updatedAt: p.updatedAt,
      commentCount: p.comments.length,
    }))
  return { items, total: filtered.length, page: current, totalPages }
}

export async function getPost(id: number) {
  const db = await load()
  return db.posts.find((p) => p.id === id) ?? null
}

export function incrementViews(id: number) {
  return mutate((db) => {
    const post = db.posts.find((p) => p.id === id)
    if (post) post.views += 1
  })
}

export function createPost(input: {
  title: string
  content: string
  author: string
  password: string
}) {
  return mutate((db) => {
    const now = new Date().toISOString()
    const post: Post = {
      id: db.nextPostId++,
      title: input.title,
      content: input.content,
      author: input.author,
      passwordHash: hashPassword(input.password),
      views: 0,
      createdAt: now,
      updatedAt: now,
      comments: [],
    }
    db.posts.push(post)
    return post.id
  })
}

export function updatePost(
  id: number,
  password: string,
  input: { title: string; content: string; author: string }
) {
  return mutate((db) => {
    const post = db.posts.find((p) => p.id === id)
    if (!post) return "not-found" as const
    if (!verifyPassword(password, post.passwordHash)) return "bad-password" as const
    Object.assign(post, input, { updatedAt: new Date().toISOString() })
    return "ok" as const
  })
}

export function deletePost(id: number, password: string) {
  return mutate((db) => {
    const index = db.posts.findIndex((p) => p.id === id)
    if (index === -1) return "not-found" as const
    if (!verifyPassword(password, db.posts[index].passwordHash)) return "bad-password" as const
    db.posts.splice(index, 1)
    return "ok" as const
  })
}

export function addComment(
  postId: number,
  input: { author: string; content: string; password: string }
) {
  return mutate((db) => {
    const post = db.posts.find((p) => p.id === postId)
    if (!post) return "not-found" as const
    post.comments.push({
      id: db.nextCommentId++,
      author: input.author,
      content: input.content,
      passwordHash: hashPassword(input.password),
      createdAt: new Date().toISOString(),
    })
    return "ok" as const
  })
}

export function deleteComment(postId: number, commentId: number, password: string) {
  return mutate((db) => {
    const post = db.posts.find((p) => p.id === postId)
    const index = post?.comments.findIndex((c) => c.id === commentId) ?? -1
    if (!post || index === -1) return "not-found" as const
    if (!verifyPassword(password, post.comments[index].passwordHash)) return "bad-password" as const
    post.comments.splice(index, 1)
    return "ok" as const
  })
}
