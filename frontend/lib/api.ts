import type { ExercisePreview } from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type GeneratePracticeRequest = {
  userId: string;
  message: string;
};

export type GeneratePracticeResponse = {
  exercises: Array<{
    exercise_id: string;
    exercise_type: string;
    question_text: string;
    options: Array<{
      label: string;
      text: string;
      is_correct: boolean;
    }>;
    explanation: string;
  }>;
  recommendation?: string;
  generator_backend?: string;
};

export async function generatePractice(
  payload: GeneratePracticeRequest,
): Promise<{
  exercises: ExercisePreview[];
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
    exercises: data.exercises.map((exercise) => ({
      id: exercise.exercise_id,
      type: exercise.exercise_type,
      question: exercise.question_text,
      options: exercise.options.map((option) => ({
        label: option.label,
        text: option.text,
        isCorrect: option.is_correct,
      })),
      explanation: exercise.explanation,
    })),
    recommendation: data.recommendation,
    generatorBackend: data.generator_backend,
  };
}
