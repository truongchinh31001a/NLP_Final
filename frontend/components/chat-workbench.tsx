"use client";

import { useState, useTransition } from "react";

import { generatePractice } from "@/lib/api";
import type {
  DashboardSnapshot,
  ExercisePreview,
} from "@/lib/types";

type ChatWorkbenchProps = {
  snapshot: DashboardSnapshot;
};

export function ChatWorkbench({ snapshot }: ChatWorkbenchProps) {
  const [prompt, setPrompt] = useState(snapshot.currentPrompt);
  const [preview, setPreview] = useState<ExercisePreview[]>(
    snapshot.exercisePreview,
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState(
    "Connected UI preview. Try generating through the backend when it is available.",
  );
  const [, startTransition] = useTransition();

  const handleGeneratePreview = async () => {
    setIsGenerating(true);
    setStatus("Contacting backend...");

    try {
      const response = await generatePractice({
        userId: "demo-user",
        message: prompt,
      });

      startTransition(() => {
        setPreview(response.exercises);
      });
      setStatus(
        response.recommendation
          ? `Backend response ready. ${response.recommendation}`
          : `Backend response ready via ${response.generatorBackend ?? "configured generator"}.`,
      );
    } catch {
      const generated = buildPreviewFromPrompt(prompt);
      startTransition(() => {
        setPreview(generated);
      });
      setStatus(
        "Backend is unavailable right now, so the UI is showing a local preview fallback.",
      );
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <main className="shell">
      <div className="shell__frame">
        <header className="hero">
          <div>
            <div className="hero__eyebrow">
              <span>Next.js App Router</span>
              <span>Frontend baseline</span>
            </div>
            <h1 className="hero__title">
              A study dashboard that feels <span>personal</span>, not generic.
            </h1>
            <p className="hero__copy">
              This UI is designed for a Python + LangChain backend. The left
              column shows learner state, the center column handles natural
              language practice requests, and the right column keeps the
              feedback loop visible after each session.
            </p>
          </div>

          <aside className="hero__status">
            <p className="hero__status-label">Active focus</p>
            <p className="hero__status-value">{snapshot.activeFocus}</p>
            <p className="hero__status-note">
              {snapshot.recommendations[0]?.body}
            </p>
          </aside>
        </header>

        <section className="dashboard">
          <aside className="panel profile-card">
            <div>
              <span className="profile-card__badge">
                Learner profile
              </span>
              <h2 className="profile-card__name">{snapshot.profile.name}</h2>
              <p className="panel__subtitle">
                {snapshot.profile.goal}
              </p>
            </div>

            <div className="profile-card__meta">
              <StatChip label="Level" value={snapshot.profile.level} />
              <StatChip
                label="Preferred"
                value={snapshot.profile.preferredDifficulty}
              />
              <StatChip
                label="Accuracy"
                value={`${Math.round(snapshot.profile.accuracy * 100)}%`}
              />
              <StatChip
                label="Sessions"
                value={snapshot.profile.sessionCount.toString()}
              />
            </div>

            <div>
              <h3 className="panel__title">Weak topics</h3>
              <div className="weakness-list">
                {snapshot.weakTopics.map((topic) => (
                  <div className="weakness-row" key={topic.name}>
                    <div className="weakness-row__top">
                      <strong>{topic.name}</strong>
                      <span>{Math.round(topic.weight * 100)}%</span>
                    </div>
                    <div className="meter">
                      <span style={{ width: `${topic.weight * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </aside>

          <section className="workspace">
            <div className="prompt-card">
              <p className="prompt-card__label">Natural language request</p>
              <p className="prompt-card__value">{snapshot.currentPrompt}</p>
              <div className="prompt-card__chips">
                {snapshot.requestTags.map((tag) => (
                  <span className="chip" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            <div className="panel">
              <h2 className="panel__title">Exercise preview</h2>
              <p className="panel__subtitle">
                This panel prefers the Python API response and falls back to a
                local preview only when the backend is unavailable.
              </p>

              <div className="exercise-list" style={{ marginTop: 18 }}>
                {preview.map((exercise, index) => (
                  <article className="exercise-card" key={exercise.id}>
                    <div className="exercise-card__header">
                      <div style={{ display: "flex", gap: 14 }}>
                        <span className="exercise-card__index">
                          {index + 1}
                        </span>
                        <div>
                          <p className="exercise-card__question">
                            {exercise.question}
                          </p>
                        </div>
                      </div>
                      <span className="exercise-card__tag">
                        {exercise.type}
                      </span>
                    </div>

                    {exercise.options.length > 0 ? (
                      <div className="options">
                        {exercise.options.map((option) => (
                          <div
                            className={`option${option.isCorrect ? " option--correct" : ""}`}
                            key={option.label}
                          >
                            <span className="option__label">
                              {option.label}
                            </span>
                            <span>{option.text}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    <div className="exercise-card__explanation">
                      {exercise.explanation}
                    </div>
                  </article>
                ))}
              </div>
            </div>

            <div className="composer">
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Type a learner request, for example: I am weak at passive voice, generate 5 medium questions."
              />
              <div className="composer__footer">
                <span className="composer__hint">
                  {status}
                </span>
                <div className="composer__actions">
                  <button
                    className="button button--secondary"
                    type="button"
                    onClick={() => setPrompt(snapshot.currentPrompt)}
                  >
                    Reset prompt
                  </button>
                  <button
                    className="button button--primary"
                    type="button"
                    onClick={handleGeneratePreview}
                    disabled={isGenerating}
                  >
                    {isGenerating ? "Generating..." : "Generate practice"}
                  </button>
                </div>
              </div>
            </div>
          </section>

          <aside className="panel">
            <div>
              <h2 className="panel__title">Feedback loop</h2>
              <p className="panel__subtitle">
                Recommendation cards and session history make the
                personalization logic legible to the learner.
              </p>
            </div>

            <div className="recommendation-list" style={{ marginTop: 18 }}>
              {snapshot.recommendations.map((item) => (
                <article className="recommendation-card" key={item.title}>
                  <p className="recommendation-card__title">{item.title}</p>
                  <p className="recommendation-card__body">{item.body}</p>
                </article>
              ))}
            </div>

            <div style={{ marginTop: 22 }}>
              <h3 className="panel__title">Recent sessions</h3>
              <div className="history-list">
                {snapshot.history.map((item) => (
                  <article className="history-card" key={item.id}>
                    <p className="history-card__title">{item.topic}</p>
                    <p className="history-card__body">{item.note}</p>
                    <span className="history-card__score">
                      Score {Math.round(item.score * 100)}%
                    </span>
                  </article>
                ))}
              </div>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-chip">
      <p className="stat-chip__label">{label}</p>
      <p className="stat-chip__value">{value}</p>
    </div>
  );
}

function buildPreviewFromPrompt(prompt: string): ExercisePreview[] {
  const normalized = prompt.toLowerCase();
  const topic = normalized.includes("passive")
    ? "Passive voice"
    : normalized.includes("travel")
      ? "Travel vocabulary"
      : "Grammar review";
  const type = normalized.includes("fill") || normalized.includes("dien")
    ? "Fill blank"
    : "MCQ";

  if (type === "Fill blank") {
    return [
      {
        id: "preview-1",
        type,
        question: `Fill in the blank: This preview focuses on ${topic.toLowerCase()} with a learner-friendly warm-up item.`,
        options: [],
        explanation:
          "This is a UI-only preview. Replace this generator with a real API call to the Python backend.",
      },
      {
        id: "preview-2",
        type,
        question: `Fill in the blank: A second ${topic.toLowerCase()} item can appear here after the backend returns validated content.`,
        options: [],
        explanation:
          "Keep the frontend schema stable so later you can swap mock data for real LangChain output.",
      },
    ];
  }

  return [
    {
      id: "preview-1",
      type,
      question: `Which sentence best matches a ${topic.toLowerCase()} practice request?`,
      options: [
        { label: "A", text: "A validated correct option", isCorrect: true },
        { label: "B", text: "A plausible distractor", isCorrect: false },
        { label: "C", text: "An off-topic distractor", isCorrect: false },
        { label: "D", text: "A grammatically broken distractor", isCorrect: false },
      ],
      explanation:
        "This preview mirrors the structure expected from the backend: question, options, correct answer, and explanation.",
    },
    {
      id: "preview-2",
      type,
      question: `How should the learner continue after a weaker ${topic.toLowerCase()} score?`,
      options: [
        { label: "A", text: "Stay on the same topic with easier difficulty", isCorrect: true },
        { label: "B", text: "Jump to an unrelated hard topic", isCorrect: false },
        { label: "C", text: "Ignore the learner profile entirely", isCorrect: false },
        { label: "D", text: "Remove retrieval context from generation", isCorrect: false },
      ],
      explanation:
        "The UI should make recommendation logic visible so the personalization loop feels intentional.",
    },
  ];
}
