import { notFound } from "next/navigation";
import { connection } from "next/server";
import { Suspense } from "react";

import { updatePostAction } from "@/lib/actions";
import { getPost } from "@/lib/db";
import { PostForm } from "@/components/post-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function EditPostPage({ params }: PageProps<"/posts/[id]/edit">) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">글 수정</CardTitle>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
          <EditForm params={params} />
        </Suspense>
      </CardContent>
    </Card>
  );
}

async function EditForm({ params }: Pick<PageProps<"/posts/[id]/edit">, "params">) {
  await connection();
  const id = Number((await params).id);
  const post = Number.isInteger(id) ? await getPost(id) : null;
  if (!post) notFound();

  return (
    <PostForm
      action={updatePostAction.bind(null, post.id)}
      defaultValues={{ title: post.title, content: post.content, author: post.author }}
      submitLabel="수정 완료"
      cancelHref={`/posts/${post.id}`}
    />
  );
}
