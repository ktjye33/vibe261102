// Creates the board tables in the database at DATABASE_URL and seeds sample posts
// when the board is empty. Safe to run repeatedly: `npm run db:setup`.
import { randomBytes, scryptSync } from "node:crypto"
import { neon } from "@neondatabase/serverless"

if (!process.env.DATABASE_URL) {
  console.error("DATABASE_URL is not set. Copy .env.example to .env.local first.")
  process.exit(1)
}

const sql = neon(process.env.DATABASE_URL)

// Must match hashPassword in src/lib/db.ts.
function hashPassword(password) {
  const salt = randomBytes(16).toString("hex")
  return `${salt}:${scryptSync(password, salt, 32).toString("hex")}`
}

await sql`
  CREATE TABLE IF NOT EXISTS posts (
    id            SERIAL PRIMARY KEY,
    title         VARCHAR(100) NOT NULL,
    content       TEXT NOT NULL,
    author        VARCHAR(20) NOT NULL,
    password_hash TEXT NOT NULL,
    views         INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  )`
await sql`
  CREATE TABLE IF NOT EXISTS comments (
    id            SERIAL PRIMARY KEY,
    post_id       INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author        VARCHAR(20) NOT NULL,
    content       TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  )`
await sql`CREATE INDEX IF NOT EXISTS comments_post_id_idx ON comments (post_id)`

const [{ count }] = await sql`SELECT count(*)::int AS count FROM posts`
if (count === 0) {
  const pw = hashPassword("1234")
  const samples = [
    ["게시판에 오신 것을 환영합니다", "관리자", "자유롭게 글을 작성해 주세요.\n작성 시 입력한 비밀번호로 수정/삭제할 수 있습니다."],
    ["Next.js 16 사용 후기", "개발자", "Cache Components와 Server Actions 조합이 꽤 편리하네요."],
    ["shadcn/ui 컴포넌트 추천", "디자이너", "Card, Table, Badge 정도만 있어도 게시판 UI는 충분합니다."],
  ]
  const ids = []
  for (const [title, author, content] of samples) {
    const [row] = await sql`
      INSERT INTO posts (title, author, content, password_hash)
      VALUES (${title}, ${author}, ${content}, ${pw})
      RETURNING id`
    ids.push(row.id)
  }
  await sql`
    INSERT INTO comments (post_id, author, content, password_hash)
    VALUES (${ids[0]}, '방문자', '첫 댓글입니다!', ${pw})`
  console.log(`Seeded ${samples.length} sample posts (password: 1234).`)
}

console.log("Database is ready.")
