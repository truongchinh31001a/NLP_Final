import Link from "next/link";

import { PageHeader } from "@/components/layout/page-header";
import { SurfaceCard } from "@/components/ui/surface-card";

type TopicPageProps = {
  params: Promise<{
    topicId: string;
  }>;
};

export default async function TopicPage({ params }: TopicPageProps) {
  const { topicId } = await params;
  const title = topicId.replaceAll("-", " ");

  return (
    <div className="space-y-ae-section">
      <PageHeader
        eyebrow="Grounded detail"
        title={title}
        description="Core rule, examples, linked skills and handoff actions stay together."
        actions={
          <Link
            className="inline-flex h-10 items-center rounded-ae-control bg-ae-primary px-ae-md text-[14px] font-semibold text-white"
            href="/tutor"
          >
            Ask Tutor
          </Link>
        }
      />
      <section className="grid gap-ae-lg xl:grid-cols-[minmax(0,1fr)_360px]">
        <SurfaceCard className="p-ae-xl">
          <span className="mb-ae-sm inline-flex rounded-ae-pill bg-ae-primary-soft px-ae-sm py-ae-xs text-[12px] font-semibold text-ae-primary">
            Knowledge
          </span>
          <h2 className="mb-ae-sm text-[24px] font-bold">
            Past perfect = had + past participle
          </h2>
          <p className="mb-ae-lg text-[15px] leading-7 text-ae-muted">
            Use it when one past event happened before another past reference
            point.
          </p>
          <div className="grid gap-ae-sm">
            {[
              "When I arrived, the meeting had already started.",
              "She had left before I called.",
              "By 8 PM, they had finished.",
            ].map((example) => (
              <p
                className="mb-0 rounded-ae-compact border border-ae-line bg-ae-page p-ae-card text-[14px]"
                key={example}
              >
                {example}
              </p>
            ))}
          </div>
        </SurfaceCard>
        <SurfaceCard className="p-ae-xl">
          <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
            Handoff
          </p>
          <div className="grid gap-ae-sm">
            <Link
              className="inline-flex h-10 items-center justify-center rounded-ae-control border border-ae-line bg-ae-surface px-ae-md text-[14px] font-semibold text-ae-ink"
              href="/tutor"
            >
              Ask a follow-up
            </Link>
            <Link
              className="inline-flex h-10 items-center justify-center rounded-ae-control bg-ae-primary px-ae-md text-[14px] font-semibold text-white"
              href="/practice/demo-activity"
            >
              Practice this topic
            </Link>
          </div>
        </SurfaceCard>
      </section>
    </div>
  );
}
