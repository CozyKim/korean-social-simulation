import Link from "next/link";
import { Button } from "@/components/ui/button";
import { LiveFeed } from "@/components/live-feed/live-feed";
import { FEATURED_RUN_ID } from "@/lib/featured";

export const dynamic = "force-static";

export default function HomePage() {
  return (
    <main>
      <section className="relative isolate overflow-hidden border-b border-zinc-800 px-6 py-16">
        <img
          src="/illustrations/hero.webp"
          alt=""
          className="absolute inset-0 -z-10 h-full w-full object-cover opacity-30"
        />
        <div className="mx-auto max-w-3xl">
          <h1 className="text-balance text-5xl font-bold tracking-tight">
            한국인 100만 페르소나에게 묻습니다.
          </h1>
          <p className="mt-4 text-lg text-zinc-300">
            인구비례 stratified 샘플 + LLM 구조화 응답 + 통계·인사이트 리포트.
          </p>
          <div className="mt-6 flex gap-3">
            <Link href="/scenarios"><Button variant="primary">시나리오 둘러보기</Button></Link>
            <Link href="/try"><Button variant="outline">체험해 보기</Button></Link>
          </div>
        </div>
      </section>
      {FEATURED_RUN_ID && (
        <section className="mx-auto max-w-5xl px-6 py-10">
          <h2 className="mb-4 text-xl font-semibold">대표 run 라이브 리플레이</h2>
          <LiveFeed runId={FEATURED_RUN_ID} maxCards={20} />
        </section>
      )}
    </main>
  );
}
