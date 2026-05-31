"use client";

import { useMemo, useState, useTransition } from "react";

import { generatePractice, scorePractice } from "@/lib/api";
import type {
  DashboardSnapshot,
  ExercisePreview,
  PracticePlanPreview,
  ScoreResult,
} from "@/lib/types";

type ChatWorkbenchProps = {
  snapshot: DashboardSnapshot;
};

type Screen = "chat" | "generating" | "practice" | "result";

const USER_ID = "demo-user";

const generationSteps = [
  "Phan tich yeu cau",
  "Doc ho so nguoi hoc",
  "Tim ngu canh kien thuc",
  "Sinh cau hoi",
  "Kiem tra dap an",
];

export function ChatWorkbench({ snapshot }: ChatWorkbenchProps) {
  const [screen, setScreen] = useState<Screen>("chat");
  const [prompt, setPrompt] = useState(snapshot.currentPrompt);
  const [preview, setPreview] = useState<ExercisePreview[]>(
    snapshot.exercisePreview,
  );
  const [plan, setPlan] = useState<PracticePlanPreview>(snapshot.planPreview);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [scoreResult, setScoreResult] = useState<ScoreResult | null>(null);
  const [status, setStatus] = useState("San sang tao bai luyen tap.");
  const [isScoring, setIsScoring] = useState(false);
  const [, startTransition] = useTransition();

  const answeredCount = useMemo(
    () => preview.filter((exercise) => answers[exercise.id]).length,
    [answers, preview],
  );
  const canSubmit = preview.length > 0 && answeredCount === preview.length;

  const handleGenerate = async () => {
    setScreen("generating");
    setScoreResult(null);
    setAnswers({});
    setStatus("Dang goi pipeline sinh bai tap...");

    try {
      const response = await generatePractice({
        userId: USER_ID,
        message: prompt,
      });

      startTransition(() => {
        setPreview(response.exercises);
        setPlan(response.plan);
      });
      setStatus(
        response.recommendation ??
          `Da sinh bai tap bang ${response.generatorBackend ?? "backend"}.`,
      );
    } catch {
      const generated = buildPreviewFromPrompt(prompt);
      startTransition(() => {
        setPreview(generated.exercises);
        setPlan(generated.plan);
      });
      setStatus("Backend chua san sang, dang dung bo cau hoi fallback.");
    } finally {
      window.setTimeout(() => setScreen("practice"), 650);
    }
  };

  const handleScorePractice = async () => {
    setIsScoring(true);
    setStatus("Dang cham bai...");

    try {
      const response = await scorePractice({
        userId: USER_ID,
        topic: plan.topic,
        answers: preview.map((exercise) => ({
          exerciseId: exercise.id,
          selectedAnswer: answers[exercise.id],
        })),
      });

      setScoreResult(response);
      setStatus("Da cham bai va cap nhat khuyen nghi.");
    } catch {
      const correctCount = preview.filter(
        (exercise) => answers[exercise.id] === exercise.correctAnswer,
      ).length;
      const score = correctCount / Math.max(preview.length, 1);
      setScoreResult({
        topic: plan.topic,
        score,
        correctCount,
        totalQuestions: preview.length,
        weakTopicsDetected: score < 0.8 ? [plan.topic] : [],
        recommendation:
          score < 0.8
            ? "Nen luyen lai chu de nay voi do kho thap hon mot muc."
            : "Co the tang do kho hoac chuyen sang bien the gan voi chu de nay.",
      });
      setStatus("Da cham bang fallback frontend.");
    } finally {
      setIsScoring(false);
      setScreen("result");
    }
  };

  return (
    <main className="flow-shell">
      <header className="flow-topbar">
        <div>
          <p className="eyebrow">Personalized English Practice</p>
          <h1>Chatbot sinh bai tap tieng Anh</h1>
        </div>
        <div className="learner-pill">
          <span>{snapshot.profile.name}</span>
          <strong>{snapshot.profile.level}</strong>
        </div>
      </header>

      {screen === "chat" ? (
        <section className="chat-screen">
          <div className="chat-thread">
            <article className="message message--bot">
              <span>AI</span>
              <p>
                Ban muon luyen chu de nao? Hay noi bang ngon ngu tu nhien,
                minh se tao bai kiem tra phu hop voi ho so hoc tap.
              </p>
            </article>
            <article className="message message--user">
              <span>Ban</span>
              <p>{prompt}</p>
            </article>
          </div>

          <div className="chat-composer">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Vi du: I am weak at passive voice. Generate 5 medium multiple-choice questions."
            />
            <button
              className="button button--primary"
              type="button"
              onClick={handleGenerate}
              disabled={prompt.trim().length === 0}
            >
              Gui yeu cau
            </button>
          </div>
        </section>
      ) : null}

      {screen === "generating" ? (
        <section className="generation-screen">
          <div className="generation-card">
            <p className="eyebrow">Dang generate</p>
            <h2>Pipeline dang tao bai kiem tra</h2>
            <p className="muted">{status}</p>
            <div className="generation-steps">
              {generationSteps.map((step, index) => (
                <div className="generation-step" key={step}>
                  <span>{index + 1}</span>
                  <strong>{step}</strong>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {screen === "practice" ? (
        <section className="test-screen">
          <div className="test-header">
            <div>
              <p className="eyebrow">Bai kiem tra</p>
              <h2>{formatTopic(plan.topic)}</h2>
              <p className="muted">
                {plan.difficulty} - {plan.exerciseType} - {status}
              </p>
            </div>
            <div className="progress-pill">
              {answeredCount}/{preview.length} cau
            </div>
          </div>

          <div className="question-list">
            {preview.map((exercise, index) => (
              <QuestionCard
                exercise={exercise}
                index={index}
                key={exercise.id}
                selectedAnswer={answers[exercise.id]}
                onSelect={(value) =>
                  setAnswers((current) => ({
                    ...current,
                    [exercise.id]: value,
                  }))
                }
              />
            ))}
          </div>

          <div className="test-actions">
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setScreen("chat")}
            >
              Sua yeu cau
            </button>
            <button
              className="button button--primary"
              type="button"
              onClick={handleScorePractice}
              disabled={!canSubmit || isScoring}
            >
              {isScoring ? "Dang cham..." : "Nop bai"}
            </button>
          </div>
        </section>
      ) : null}

      {screen === "result" && scoreResult ? (
        <section className="result-screen">
          <div className="score-summary">
            <p className="eyebrow">Ket qua</p>
            <strong>{Math.round(scoreResult.score * 100)}%</strong>
            <span>
              {scoreResult.correctCount}/{scoreResult.totalQuestions} cau dung
            </span>
            <p>{scoreResult.recommendation}</p>
          </div>

          <div className="answer-review">
            {preview.map((exercise, index) => {
              const selected = answers[exercise.id];
              const isCorrect = selected === exercise.correctAnswer;
              return (
                <article className="review-card" key={exercise.id}>
                  <div className="review-card__top">
                    <span>{index + 1}</span>
                    <div>
                      <strong>{exercise.question}</strong>
                      <p className={isCorrect ? "answer-ok" : "answer-bad"}>
                        Ban chon {selected}; dap an dung la{" "}
                        {exercise.correctAnswer}
                      </p>
                    </div>
                  </div>
                  <p>{exercise.explanation}</p>
                </article>
              );
            })}
          </div>

          <div className="test-actions">
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setScreen("practice")}
            >
              Xem lai bai
            </button>
            <button
              className="button button--primary"
              type="button"
              onClick={() => {
                setScreen("chat");
                setScoreResult(null);
                setAnswers({});
              }}
            >
              Tao bai moi
            </button>
          </div>
        </section>
      ) : null}
    </main>
  );
}

function QuestionCard({
  exercise,
  index,
  selectedAnswer,
  onSelect,
}: {
  exercise: ExercisePreview;
  index: number;
  selectedAnswer?: string;
  onSelect: (value: string) => void;
}) {
  return (
    <article className="question-card">
      <div className="question-card__top">
        <span>{index + 1}</span>
        <strong>{exercise.question}</strong>
      </div>

      {exercise.options.length > 0 ? (
        <div className="option-grid">
          {exercise.options.map((option) => (
            <button
              className={`answer-option${selectedAnswer === option.label ? " answer-option--selected" : ""}`}
              key={option.label}
              type="button"
              onClick={() => onSelect(option.label)}
            >
              <span>{option.label}</span>
              <strong>{option.text}</strong>
            </button>
          ))}
        </div>
      ) : (
        <input
          className="text-answer"
          value={selectedAnswer ?? ""}
          onChange={(event) => onSelect(event.target.value)}
          placeholder="Nhap cau tra loi"
        />
      )}
    </article>
  );
}

function formatTopic(topic: string) {
  return topic.replaceAll("_", " ");
}

function buildPreviewFromPrompt(prompt: string): {
  exercises: ExercisePreview[];
  plan: PracticePlanPreview;
} {
  const normalized = prompt.toLowerCase();
  const topic = normalized.includes("passive")
    ? "passive_voice"
    : normalized.includes("travel")
      ? "travel_vocabulary"
      : "grammar_review";
  const difficulty = normalized.includes("hard")
    ? "hard"
    : normalized.includes("easy")
      ? "easy"
      : "medium";

  return {
    plan: {
      topic,
      difficulty,
      exerciseType: "grammar_mcq",
      numQuestions: 2,
      focusReason: "Fallback plan from frontend.",
    },
    exercises: [
      {
        id: "preview-1",
        type: "grammar_mcq",
        topic,
        difficulty,
        question: `Which option best matches a ${topic} practice request?`,
        options: [
          { label: "A", text: "A focused exercise for the learner weakness", isCorrect: true },
          { label: "B", text: "A random unrelated exercise", isCorrect: false },
          { label: "C", text: "A prompt without explanation", isCorrect: false },
          { label: "D", text: "A question without a topic", isCorrect: false },
        ],
        correctAnswer: "A",
        explanation:
          "The correct option stays aligned with topic, difficulty, and learner profile.",
        sourceChunkIds: [],
      },
      {
        id: "preview-2",
        type: "grammar_mcq",
        topic,
        difficulty,
        question: "What should happen after the learner submits answers?",
        options: [
          { label: "A", text: "Score the session and recommend the next step", isCorrect: true },
          { label: "B", text: "Discard the answers", isCorrect: false },
          { label: "C", text: "Hide the explanation", isCorrect: false },
          { label: "D", text: "Ignore weak topics", isCorrect: false },
        ],
        correctAnswer: "A",
        explanation:
          "The project workflow ends with scoring, profile update, and recommendation.",
        sourceChunkIds: [],
      },
    ],
  };
}
