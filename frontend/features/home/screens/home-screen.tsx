"use client";

import {
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  HistoryOutlined,
} from "@ant-design/icons";
import { Button, Progress, Tag } from "antd";
import Link from "next/link";

import { PageHeader } from "@/components/layout/page-header";
import { NextBestActivity } from "@/components/learning/next-best-activity";
import { SkillMetricCard } from "@/components/learning/skill-metric-card";
import { SurfaceCard } from "@/components/ui/surface-card";
import type { DashboardSnapshot } from "@/lib/types";

type HomeScreenProps = {
  snapshot: DashboardSnapshot;
};

export function HomeScreen({ snapshot }: HomeScreenProps) {
  const accuracy = Math.round(snapshot.profile.accuracy * 100);
  const firstName = snapshot.profile.name.split(" ")[0] || "there";

  return (
    <div className="space-y-ae-section">
      <PageHeader
        eyebrow="Home"
        title={`Welcome, ${firstName}`}
        description="Your plan, review queue and next action stay in one calm learning loop."
        actions={
          <Tag color="blue" className="m-0 rounded-ae-pill px-ae-sm py-ae-xs">
            {snapshot.profile.level} learner
          </Tag>
        }
      />

      <section className="grid gap-ae-lg xl:grid-cols-[minmax(0,1fr)_360px]">
        <NextBestActivity plan={snapshot.planPreview} />

        <SurfaceCard className="p-ae-xl">
          <div className="mb-ae-md flex items-center justify-between gap-ae-md">
            <div>
              <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
                Today&apos;s plan
              </p>
              <h2 className="mb-0 text-[20px] font-bold">20 min focus</h2>
            </div>
            <ClockCircleOutlined className="text-[22px] text-ae-primary" />
          </div>
          <Progress
            percent={42}
            strokeColor="#147447"
            trailColor="#e8efff"
            showInfo={false}
          />
          <div className="mt-ae-md grid gap-ae-sm">
            <ActivityLine label="Warm-up" done text="Review weak pattern" />
            <ActivityLine label="Core" text="Targeted grammar practice" />
            <ActivityLine label="Close" text="Check mastery update" />
          </div>
        </SurfaceCard>
      </section>

      <section className="grid gap-ae-lg lg:grid-cols-3">
        <SkillMetricCard
          label="Overall accuracy"
          value={snapshot.profile.accuracy}
          detail={`${accuracy}% across ${snapshot.profile.sessionCount} completed sessions.`}
          tone="success"
        />
        <SkillMetricCard
          label="Top weak area"
          value={snapshot.weakTopics[0]?.weight ?? 0}
          detail={snapshot.weakTopics[0]?.name ?? "Need more evidence"}
          tone="warning"
        />
        <SkillMetricCard
          label="Evidence volume"
          value={Math.min(snapshot.profile.sessionCount / 25, 1)}
          detail="Recent answers are enough to guide the next activity."
        />
      </section>

      <section className="grid gap-ae-lg xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <SurfaceCard className="p-ae-xl">
          <div className="mb-ae-md flex items-center justify-between">
            <h2 className="mb-0 text-[20px] font-bold">Learning insight</h2>
            <BarChartOutlined className="text-[20px] text-ae-primary" />
          </div>
          <div className="grid gap-ae-sm">
            {snapshot.recommendations.map((item) => (
              <article
                className="rounded-ae-compact border border-ae-line bg-ae-page p-ae-card"
                key={item.title}
              >
                <h3 className="mb-ae-xs text-[15px] font-bold">{item.title}</h3>
                <p className="mb-0 text-[13px] leading-5 text-ae-muted">
                  {item.body}
                </p>
              </article>
            ))}
          </div>
        </SurfaceCard>

        <SurfaceCard className="p-ae-xl">
          <div className="mb-ae-md flex items-center justify-between">
            <h2 className="mb-0 text-[20px] font-bold">Recent evidence</h2>
            <Link href="/progress">
              <Button type="link" icon={<HistoryOutlined />}>
                View progress
              </Button>
            </Link>
          </div>
          <div className="grid gap-ae-sm">
            {snapshot.history.map((item) => (
              <article
                className="grid gap-ae-sm rounded-ae-compact border border-ae-line p-ae-card md:grid-cols-[160px_minmax(0,1fr)_80px]"
                key={item.id}
              >
                <strong>{item.topic}</strong>
                <p className="mb-0 text-[13px] leading-5 text-ae-muted">
                  {item.note}
                </p>
                <span className="font-semibold text-ae-primary">
                  {Math.round(item.score * 100)}%
                </span>
              </article>
            ))}
          </div>
        </SurfaceCard>
      </section>
    </div>
  );
}

function ActivityLine({
  done = false,
  label,
  text,
}: {
  done?: boolean;
  label: string;
  text: string;
}) {
  return (
    <div className="flex items-center gap-ae-sm rounded-ae-compact border border-ae-line bg-ae-surface p-ae-sm">
      <span
        className={`grid size-7 place-items-center rounded-ae-pill ${
          done ? "bg-ae-success-soft text-ae-success" : "bg-ae-primary-soft text-ae-primary"
        }`}
      >
        {done ? <CheckCircleOutlined /> : <ClockCircleOutlined />}
      </span>
      <span className="min-w-0">
        <strong className="block text-[13px]">{label}</strong>
        <span className="block truncate text-[12px] text-ae-muted">{text}</span>
      </span>
    </div>
  );
}
