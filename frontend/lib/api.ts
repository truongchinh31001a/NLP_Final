import type { ExercisePreview } from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type GeneratePracticeRequest = {
  userId: string;
  message: string;
};

export type GeneratePracticeResponse = {
  plan: {
    topic: string;
    difficulty: string;
    exercise_type: string;
    num_questions: number;
    focus_reason: string;
  };
  exercises: Array<{
    exercise_id: string;
    exercise_type: string;
    topic: string;
    difficulty: string;
    question_text: string;
    options: Array<{
      label: string;
      text: string;
      is_correct: boolean;
    }>;
    correct_answer: string;
    explanation: string;
    source_chunk_ids: string[];
  }>;
  recommendation?: string;
  generator_backend?: string;
  agent_trace?: Array<{
    tool: string;
    status: string;
    detail: string;
    metadata: Record<string, unknown>;
  }>;
};

export type ScorePracticeRequest = {
  userId: string;
  topic: string;
  answers: Array<{
    exerciseId: string;
    selectedAnswer: string;
  }>;
};

export type ScorePracticeResponse = {
  topic: string;
  score: number;
  correct_count: number;
  total_questions: number;
  weak_topics_detected: string[];
  recommendation: string;
};

export async function generatePractice(
  payload: GeneratePracticeRequest,
): Promise<{
  exercises: ExercisePreview[];
  plan: {
    topic: string;
    difficulty: string;
    exerciseType: string;
    numQuestions: number;
    focusReason: string;
  };
  recommendation?: string;
  generatorBackend?: string;
}> {
  const response = await fetch(`${API_BASE_URL}/api/practice/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: payload.userId,
      message: payload.message,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to generate practice exercises.");
  }

  const data = (await response.json()) as GeneratePracticeResponse;

  return {
    plan: {
      topic: data.plan.topic,
      difficulty: data.plan.difficulty,
      exerciseType: data.plan.exercise_type,
      numQuestions: data.plan.num_questions,
      focusReason: data.plan.focus_reason,
    },
    exercises: data.exercises.map((exercise) => ({
      id: exercise.exercise_id,
      type: exercise.exercise_type,
      topic: exercise.topic,
      difficulty: exercise.difficulty,
      question: exercise.question_text,
      options: exercise.options.map((option) => ({
        label: option.label,
        text: option.text,
        isCorrect: option.is_correct,
      })),
      correctAnswer: exercise.correct_answer,
      explanation: exercise.explanation,
      sourceChunkIds: exercise.source_chunk_ids,
    })),
    recommendation: data.recommendation,
    generatorBackend: data.generator_backend,
  };
}

export async function scorePractice(
  payload: ScorePracticeRequest,
): Promise<{
  topic: string;
  score: number;
  correctCount: number;
  totalQuestions: number;
  weakTopicsDetected: string[];
  recommendation: string;
}> {
  const response = await fetch(`${API_BASE_URL}/api/practice/score`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: payload.userId,
      topic: payload.topic,
      answers: payload.answers.map((answer) => ({
        exercise_id: answer.exerciseId,
        selected_answer: answer.selectedAnswer,
      })),
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to score practice exercises.");
  }

  const data = (await response.json()) as ScorePracticeResponse;

  return {
    topic: data.topic,
    score: data.score,
    correctCount: data.correct_count,
    totalQuestions: data.total_questions,
    weakTopicsDetected: data.weak_topics_detected,
    recommendation: data.recommendation,
  };
}
