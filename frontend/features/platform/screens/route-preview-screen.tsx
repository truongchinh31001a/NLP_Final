"use client";

import { ArrowRightOutlined } from "@ant-design/icons";
import { Button, Progress, Tag } from "antd";
import Link from "next/link";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SurfaceCard } from "@/components/ui/surface-card";

type PreviewPanel = {
  title: string;
  body: string;
  meta?: string;
};

type RoutePreviewScreenProps = {
  eyebrow: string;
  title: string;
  description: string;
  metricLabel: string;
  metricValue: number;
  metricDetail: string;
  primaryHref?: string;
  primaryLabel?: string;
  panels: PreviewPanel[];
  aside?: ReactNode;
};

export function RoutePreviewScreen({
  aside,
  description,
  eyebrow,
  metricDetail,
  metricLabel,
  metricValue,
  panels,
  primaryHref,
  primaryLabel,
  title,
}: RoutePreviewScreenProps) {
  return (
    <div className="space-y-ae-section">
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        description={description}
        actions={
          primaryHref && primaryLabel ? (
            <Link href={primaryHref}>
              <Button type="primary" icon={<ArrowRightOutlined />}>
                {primaryLabel}
              </Button>
            </Link>
          ) : null
        }
      />

      <section className="grid gap-ae-lg xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid gap-ae-lg md:grid-cols-2">
          {panels.map((panel) => (
            <SurfaceCard className="p-ae-xl" key={panel.title}>
              {panel.meta ? (
                <Tag color="blue" className="m-0 mb-ae-sm">
                  {panel.meta}
                </Tag>
              ) : null}
              <h2 className="mb-ae-sm text-[20px] font-bold tracking-normal">
                {panel.title}
              </h2>
              <p className="mb-0 text-[14px] leading-6 text-ae-muted">
                {panel.body}
              </p>
            </SurfaceCard>
          ))}
        </div>

        <SurfaceCard className="p-ae-xl">
          <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
            {metricLabel}
          </p>
          <div className="mb-ae-md flex items-end gap-ae-sm">
            <strong className="text-[42px] leading-none">
              {Math.round(metricValue)}%
            </strong>
            <span className="pb-1 text-[13px] text-ae-muted">current</span>
          </div>
          <Progress
            percent={Math.round(metricValue)}
            strokeColor="#2454a6"
            trailColor="#e8efff"
            showInfo={false}
          />
          <p className="mb-0 mt-ae-md text-[14px] leading-6 text-ae-muted">
            {metricDetail}
          </p>
          {aside ? <div className="mt-ae-lg">{aside}</div> : null}
        </SurfaceCard>
      </section>
    </div>
  );
}
