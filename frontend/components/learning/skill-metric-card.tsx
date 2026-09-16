"use client";

import { Progress } from "antd";

import { SurfaceCard } from "@/components/ui/surface-card";

type SkillMetricCardProps = {
  label: string;
  value: number;
  detail: string;
  tone?: "primary" | "success" | "warning";
};

const strokeByTone = {
  primary: "#2454a6",
  success: "#147447",
  warning: "#c7730d",
};

export function SkillMetricCard({
  detail,
  label,
  tone = "primary",
  value,
}: SkillMetricCardProps) {
  return (
    <SurfaceCard className="p-ae-card">
      <div className="flex items-start justify-between gap-ae-md">
        <div className="min-w-0">
          <p className="mb-ae-xs text-[12px] font-semibold text-ae-muted">
            {label}
          </p>
          <strong className="block text-[26px] leading-none">
            {Math.round(value * 100)}%
          </strong>
        </div>
        <Progress
          percent={Math.round(value * 100)}
          size={46}
          strokeColor={strokeByTone[tone]}
          type="circle"
        />
      </div>
      <p className="mb-0 mt-ae-sm text-[13px] leading-5 text-ae-muted">
        {detail}
      </p>
    </SurfaceCard>
  );
}
