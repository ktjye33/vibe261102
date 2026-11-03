import Link from "next/link";
import { Suspense } from "react";
import { MessageSquare, PenSquare, Search } from "lucide-react";

import { listPosts } from "@/lib/db";
import { formatDate } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function Home({ searchParams }: PageProps<"/">) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">자유게시판</CardTitle>
        <CardAction>
          <Link href="/posts/new" className={buttonVariants()}>
            <PenSquare />
            글쓰기
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
          <PostList searchParams={searchParams} />
        </Suspense>
      </CardContent>
    </Card>
  );
}

async function PostList({ searchParams }: Pick<PageProps<"/">, "searchParams">) {
  const params = await searchParams;
  const query = typeof params.q === "string" ? params.q : "";
  const page = Number(params.page) || 1;
  const { items, total, page: current, totalPages } = await listPosts({ query, page });

  const pageHref = (p: number) => {
    const sp = new URLSearchParams();
    if (query) sp.set("q", query);
    if (p > 1) sp.set("page", String(p));
    const qs = sp.toString();
    return qs ? `/?${qs}` : "/";
  };

  return (
    <div className="grid gap-4">
      <form className="flex gap-2" action="/">
        <Input
          name="q"
          defaultValue={query}
          placeholder="제목, 내용, 작성자 검색"
          aria-label="검색어"
        />
        <Button type="submit" variant="outline">
          <Search />
          검색
        </Button>
      </form>

      <p className="text-sm text-muted-foreground">
        {query ? `"${query}" 검색 결과 ` : "전체 "}
        {total}건
      </p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16 text-center">번호</TableHead>
            <TableHead>제목</TableHead>
            <TableHead className="w-28">작성자</TableHead>
            <TableHead className="hidden w-24 text-center sm:table-cell">작성일</TableHead>
            <TableHead className="hidden w-16 text-center sm:table-cell">조회</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                게시글이 없습니다.
              </TableCell>
            </TableRow>
          ) : (
            items.map((post) => (
              <TableRow key={post.id}>
                <TableCell className="text-center text-muted-foreground">{post.id}</TableCell>
                <TableCell className="max-w-0">
                  <div className="flex items-center gap-2">
                    <Link href={`/posts/${post.id}`} className="truncate font-medium hover:underline">
                      {post.title}
                    </Link>
                    {post.commentCount > 0 && (
                      <Badge variant="secondary" className="shrink-0">
                        <MessageSquare />
                        {post.commentCount}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="truncate">{post.author}</TableCell>
                <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                  {formatDate(post.createdAt)}
                </TableCell>
                <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                  {post.views}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {totalPages > 1 && (
        <nav aria-label="페이지" className="flex flex-wrap justify-center gap-1">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <Link
              key={p}
              href={pageHref(p)}
              aria-current={p === current ? "page" : undefined}
              className={buttonVariants({
                variant: p === current ? "default" : "ghost",
                size: "icon",
              })}
            >
              {p}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
