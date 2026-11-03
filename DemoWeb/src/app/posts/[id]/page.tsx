import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { Suspense } from "react";
import { ArrowLeft, Eye, Pencil } from "lucide-react";

import {
  addCommentAction,
  deleteCommentAction,
  deletePostAction,
} from "@/lib/actions";
import { getPost, incrementViews } from "@/lib/db";
import { formatDateTime } from "@/lib/format";
import { CommentForm } from "@/components/comment-form";
import { PasswordActionForm } from "@/components/password-action-form";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export default function PostPage({ params }: PageProps<"/posts/[id]">) {
  return (
    <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
      <PostDetail params={params} />
    </Suspense>
  );
}

async function PostDetail({ params }: Pick<PageProps<"/posts/[id]">, "params">) {
  await connection();
  const id = Number((await params).id);
  if (!Number.isInteger(id)) notFound();

  await incrementViews(id);
  const post = await getPost(id);
  if (!post) notFound();

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{post.title}</CardTitle>
          <CardDescription className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-medium text-foreground">{post.author}</span>
            <span>{formatDateTime(post.createdAt)}</span>
            {post.updatedAt !== post.createdAt && <span>(수정됨)</span>}
            <span className="inline-flex items-center gap-1">
              <Eye className="size-3.5" />
              {post.views}
            </span>
          </CardDescription>
        </CardHeader>
        <Separator />
        <CardContent>
          <div className="min-h-40 whitespace-pre-wrap break-words leading-7">{post.content}</div>
        </CardContent>
        <CardFooter className="flex flex-wrap justify-between gap-2 border-t py-3">
          <Link href="/" className={buttonVariants({ variant: "outline", size: "sm" })}>
            <ArrowLeft />
            목록
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/posts/${post.id}/edit`}
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <Pencil />
              수정
            </Link>
            <PasswordActionForm
              action={deletePostAction.bind(null, post.id)}
              label="삭제"
              confirmLabel="삭제하기"
            />
          </div>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>댓글 {post.comments.length}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          {post.comments.length === 0 ? (
            <p className="text-sm text-muted-foreground">첫 댓글을 남겨보세요.</p>
          ) : (
            <ul className="grid gap-3">
              {post.comments.map((comment) => (
                <li key={comment.id} className="rounded-lg border bg-background p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="text-sm">
                      <span className="font-medium">{comment.author}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {formatDateTime(comment.createdAt)}
                      </span>
                    </div>
                    <PasswordActionForm
                      action={deleteCommentAction.bind(null, post.id, comment.id)}
                      label="삭제"
                      size="xs"
                    />
                  </div>
                  <p className="mt-2 whitespace-pre-wrap break-words text-sm">{comment.content}</p>
                </li>
              ))}
            </ul>
          )}
          <Separator />
          <CommentForm action={addCommentAction.bind(null, post.id)} />
        </CardContent>
      </Card>
    </div>
  );
}
