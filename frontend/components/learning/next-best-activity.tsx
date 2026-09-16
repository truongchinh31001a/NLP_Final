"use client";

import { ArrowRightOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Button, Tag } from "antd";
import Link from "next/link";

import { SurfaceCard } from "@/components/ui/surface-card";
import type { PracticePlanPreview } from "@/lib/types";

type NextBestActivityProps = {
  plan: PracticePlanPreview;
};

export function NextBestActivity({ plan }: NextBestActivityProps) {
  return (
    <SurfaceCard className="overflow-hidden">
      <div className="grid gap-ae-lg p-ae-xl lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="min-w-0">
          <div className="mb-ae-sm flex flex-wrap items-center gap-ae-xs">
            <Tag color="blue" className="m-0">
              Adaptive recommendation
            </Tag>
            <Tag color="cyan" className="m-0">
              {plan.difficulty}
            </Tag>
          </div>
          <h2 className="mb-ae-sm text-[26px] font-bold leading-tight tracking-normal">
            Master {formatTopic(plan.topic)} in context
          </h2>
          <p className="mb-ae-lg max-w-2xl text-[15px] leading-6 text-ae-muted">
            {plan.focusReason}
          </p>
          <div className="flex flex-wrap gap-ae-sm">
            <Button type="primary" icon={<ThunderboltOutlined />}>
              Start next activity
            </Button>
            <Link href="/tutor">
              <Button icon={<ArrowRightOutlined />}>Ask Tutor first</Button>
            </Link>
          </div>
        </div>
        <div className="rounded-ae-card bg-ae-info-soft p-ae-card">
          <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
            Activity spec
          </p>
          <dl className="mb-0 grid gap-ae-sm text-[13px]">
            <div className="flex justify-between gap-ae-md">
              <dt className="text-ae-muted">Questions</dt>
              <dd className="font-semibold">{plan.numQuestions}</dd>
            </div>
            <div className="flex justify-between gap-ae-md">
              <dt className="text-ae-muted">Type</dt>
              <dd className="font-semibold">{formatTopic(plan.exerciseType)}</dd>
            </div>
            <div className="flex justify-between gap-ae-md">
              <dt className="text-ae-muted">Skill</dt>
              <dd className="text-right font-semibold">
                {formatTopic(plan.targetSkillId ?? plan.topic)}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </SurfaceCard>
  );
}

function formatTopic(value: string) {
  return value.replaceAll("_", " ").replaceAll(".", " ");
}
