"use client";

import { ArrowRightOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { Button, Radio, Steps } from "antd";
import Link from "next/link";
import { useMemo, useState } from "react";

import { SurfaceCard } from "@/components/ui/surface-card";

const levels = [
  "A2 - Elementary",
  "B1 - Intermediate",
  "B2 - Upper intermediate",
  "Not sure yet",
];
const goals = [
  "Reach B2 for work or study",
  "Improve grammar accuracy",
  "Speak more confidently",
  "Prepare for classroom quizzes",
];

export function OnboardingScreen() {
  const [step, setStep] = useState(0);
  const [level, setLevel] = useState(levels[1]);
  const [goal, setGoal] = useState(goals[0]);
  const [calibration, setCalibration] = useState("skip");

  const steps = useMemo(
    () => [
      { title: "Setup" },
      { title: "Calibration" },
      { title: "Ready" },
    ],
    [],
  );

  return (
    <main className="min-h-screen bg-ae-page px-ae-md py-ae-lg text-ae-ink md:px-ae-xl md:py-ae-xl">
      <div className="grid min-h-[calc(100vh-48px)] w-full items-stretch gap-ae-xl lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[380px_minmax(0,1fr)]">
        <aside className="rounded-ae-hero bg-ae-sidebar p-ae-xl text-white">
          <div className="mb-ae-2xl flex items-center gap-ae-sm">
            <span className="grid size-11 place-items-center rounded-ae-compact bg-white text-ae-primary">
              LF
            </span>
            <div>
              <p className="mb-0 text-[11px] font-semibold uppercase text-white/55">
                Adaptive English
              </p>
              <strong className="text-[20px]">LingoFlow</strong>
            </div>
          </div>
          <Steps
            current={step}
            direction="vertical"
            items={steps}
            className="lingoflow-onboarding-steps"
          />
        </aside>

        <SurfaceCard className="flex min-h-[560px] flex-col justify-center p-ae-xl md:p-ae-2xl">
          {step === 0 ? (
            <section>
              <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
                Step 1 of 3
              </p>
              <h1 className="mb-ae-sm text-[32px] font-bold tracking-normal">
                Tell us where you want to begin
              </h1>
              <p className="mb-ae-xl max-w-2xl text-[15px] leading-6 text-ae-muted">
                Only the essentials now. Preferences can be refined later as
                learning evidence grows.
              </p>

              <div className="grid gap-ae-xl">
                <div>
                  <h2 className="mb-ae-sm text-[16px] font-bold">
                    How would you describe your English level?
                  </h2>
                  <Radio.Group
                    className="grid w-full gap-ae-sm md:grid-cols-2"
                    value={level}
                    onChange={(event) => setLevel(event.target.value)}
                    options={levels.map((item) => ({ label: item, value: item }))}
                    optionType="button"
                    buttonStyle="solid"
                  />
                </div>

                <div>
                  <h2 className="mb-ae-sm text-[16px] font-bold">
                    What is your main learning goal?
                  </h2>
                  <Radio.Group
                    className="grid w-full gap-ae-sm md:grid-cols-2"
                    value={goal}
                    onChange={(event) => setGoal(event.target.value)}
                    options={goals.map((item) => ({ label: item, value: item }))}
                    optionType="button"
                    buttonStyle="solid"
                  />
                </div>
              </div>
            </section>
          ) : null}

          {step === 1 ? (
            <section>
              <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
                Optional baseline
              </p>
              <h1 className="mb-ae-sm text-[32px] font-bold tracking-normal">
                Want a quick calibration first?
              </h1>
              <p className="mb-ae-xl max-w-2xl text-[15px] leading-6 text-ae-muted">
                Calibration can create a starting estimate. Skipping keeps the
                learner model in a need-more-evidence state.
              </p>
              <Radio.Group
                className="grid w-full gap-ae-sm md:grid-cols-2"
                value={calibration}
                onChange={(event) => setCalibration(event.target.value)}
                options={[
                  { label: "Start quick calibration", value: "start" },
                  { label: "Skip for now", value: "skip" },
                ]}
                optionType="button"
                buttonStyle="solid"
              />
            </section>
          ) : null}

          {step === 2 ? (
            <section>
              <span className="mb-ae-md grid size-12 place-items-center rounded-ae-pill bg-ae-success-soft text-ae-success">
                <CheckCircleOutlined />
              </span>
              <p className="mb-ae-xs text-[11px] font-bold uppercase tracking-[0.08em] text-ae-primary">
                Learner bootstrap
              </p>
              <h1 className="mb-ae-sm text-[32px] font-bold tracking-normal">
                Your starting context is ready
              </h1>
              <div className="mt-ae-xl grid gap-ae-sm md:grid-cols-3">
                <SummaryTile label="Declared level" value={level} />
                <SummaryTile label="Goal" value={goal} />
                <SummaryTile
                  label="Estimated level"
                  value={calibration === "start" ? "B1 starting estimate" : "Need more evidence"}
                />
              </div>
            </section>
          ) : null}

          <div className="mt-ae-2xl flex flex-col gap-ae-sm sm:flex-row sm:justify-between">
            <Button disabled={step === 0} onClick={() => setStep((value) => value - 1)}>
              Back
            </Button>
            {step < 2 ? (
              <Button
                type="primary"
                icon={<ArrowRightOutlined />}
                onClick={() => setStep((value) => value + 1)}
              >
                Continue
              </Button>
            ) : (
              <Link href="/home">
                <Button type="primary" icon={<ArrowRightOutlined />}>
                  Enter Home
                </Button>
              </Link>
            )}
          </div>
        </SurfaceCard>
      </div>
    </main>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-ae-compact border border-ae-line bg-ae-page p-ae-card">
      <p className="mb-ae-xs text-[12px] font-semibold text-ae-muted">{label}</p>
      <strong className="text-[14px] leading-5">{value}</strong>
    </div>
  );
}
