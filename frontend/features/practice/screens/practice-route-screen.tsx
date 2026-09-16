"use client";

import {
  CheckCircleOutlined,
  LockOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { Button, Progress, Tag } from "antd";
import { useState } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SurfaceCard } from "@/components/ui/surface-card";
import { getDashboardSnapshot } from "@/lib/mock-data";

type PracticeRouteScreenProps = {
  activityId: string;
};

export function PracticeRouteScreen({ activityId }: PracticeRouteScreenProps) {
  const snapshot = getDashboardSnapshot();
  const questions = snapshot.exercisePreview;
  const [activeIndex, setActiveIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [locked, setLocked] = useState(false);
  const activeQuestion = questions[activeIndex];

  const answeredCount = questions.filter((question) => answers[question.id]).length;
  const canSubmit = answeredCount === questions.length && !locked;

  return (
    <div className="space-y-ae-section">
      <PageHeader
        eyebrow="Practice"
        title="Past perfect - targeted practice"
        description={`Activity ${activityId} - local answer state, route-owned identity.`}
        actions={
          <Tag color={locked ? "green" : "blue"} className="m-0">
            {locked ? "Submitted" : "Answering"}
          </Tag>
        }
      />

      <section className="grid gap-ae-lg xl:grid-cols-[minmax(0,1fr)_320px]">
        <SurfaceCard className="p-ae-xl">
          <div className="mb-ae-lg flex flex-col gap-ae-md md:flex-row md:items-center md:justify-between">
            <div>
              <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
                Question {activeIndex + 1} of {questions.length}
              </p>
              <h2 className="mb-0 text-[24px] font-bold tracking-normal">
                {activeQuestion.question}
              </h2>
            </div>
            <div className="w-full md:w-48">
              <Progress
                percent={Math.round((answeredCount / questions.length) * 100)}
                showInfo={false}
                strokeColor="#2454a6"
                trailColor="#e8efff"
              />
              <p className="mb-0 mt-ae-xs text-right text-[12px] text-ae-muted">
                {answeredCount}/{questions.length} answered
              </p>
            </div>
          </div>

          <div className="grid gap-ae-sm">
            {activeQuestion.options.map((option) => {
              const selected = answers[activeQuestion.id] === option.label;
              return (
                <button
                  className={`flex min-h-14 items-center gap-ae-sm rounded-ae-control border p-ae-card text-left transition ${
                    selected
                      ? "border-ae-primary bg-ae-primary-soft text-ae-primary"
                      : "border-ae-line bg-ae-surface hover:border-ae-primary-mid"
                  } ${locked ? "cursor-not-allowed opacity-80" : ""}`}
                  disabled={locked}
                  key={option.label}
                  type="button"
                  onClick={() =>
                    setAnswers((current) => ({
                      ...current,
                      [activeQuestion.id]: option.label,
                    }))
                  }
                >
                  <span className="grid size-8 shrink-0 place-items-center rounded-ae-pill border border-current text-[13px] font-bold">
                    {option.label}
                  </span>
                  <span className="text-[14px] leading-5">{option.text}</span>
                </button>
              );
            })}
          </div>

          <div className="mt-ae-lg flex flex-col gap-ae-sm sm:flex-row sm:justify-between">
            <Button
              disabled={activeIndex === 0}
              onClick={() => setActiveIndex((current) => Math.max(current - 1, 0))}
            >
              Previous
            </Button>
            <div className="flex flex-col gap-ae-sm sm:flex-row">
              <Button
                icon={<RightOutlined />}
                disabled={activeIndex === questions.length - 1}
                onClick={() =>
                  setActiveIndex((current) =>
                    Math.min(current + 1, questions.length - 1),
                  )
                }
              >
                Next
              </Button>
              <Button
                type="primary"
                icon={locked ? <LockOutlined /> : <CheckCircleOutlined />}
                disabled={!canSubmit}
                onClick={() => setLocked(true)}
              >
                {locked ? "Answers locked" : "Submit answers"}
              </Button>
            </div>
          </div>
        </SurfaceCard>

        <SurfaceCard className="p-ae-xl">
          <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
            Session navigator
          </p>
          <div className="grid grid-cols-5 gap-ae-xs">
            {questions.map((question, index) => {
              const selected = index === activeIndex;
              const answered = Boolean(answers[question.id]);
              return (
                <button
                  className={`grid aspect-square place-items-center rounded-ae-control border text-[13px] font-bold ${
                    selected
                      ? "border-ae-primary bg-ae-primary text-white"
                      : answered
                        ? "border-ae-success bg-ae-success-soft text-ae-success"
                        : "border-ae-line bg-ae-surface text-ae-muted"
                  }`}
                  key={question.id}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                >
                  {index + 1}
                </button>
              );
            })}
          </div>
          <p className="mb-0 mt-ae-md text-[13px] leading-5 text-ae-muted">
            Correctness appears only after the backend grading result is
            returned.
          </p>
        </SurfaceCard>
      </section>
    </div>
  );
}
