import type {
  ChatMemoryResume,
  ChromaDebugSnapshot,
  ExercisePreview,
  PersonalizationSnapshot,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type GeneratePracticeRequest = {
  userId: string;
  message: string;
  intent?: PracticeIntentFields;
};

export type PracticeIntentFields = {
  topic?: string | null;
  difficulty?: string | null;
  exerciseType?: string | null;
  numQuestions?: number | null;
  targetSubtopic?: string | null;
  contentTheme?: string | null;
};

export type GeneratePracticeResponse = {
  generation_run_id: string;
  plan: {
    topic: string;
    difficulty: string;
    exercise_type: string;
    num_questions: number;
    focus_reason: string;
    content_theme?: string | null;
  };
  exercises: Array<{
    exercise_id: string;
    exercise_type: string;
    topic: string;
    difficulty: string;
    skill?: string;
    subtopic?: string | null;
    error_tag?: string | null;
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
  generationRunId: string;
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
  generation_run_id: string;
  session_code: string;
  practice_review?: {
    review_code: string;
    evaluator: string;
    summary: string;
    strengths: string[];
    weaknesses: string[];
    next_steps: string[];
    next_practice_prompt: string;
    raw_response?: string;
  } | null;
};

export type PersonalizationSnapshotResponse = {
  user_id: string;
  display_name: string;
  level: string;
  goals: string[];
  preferred_difficulty?: string | null;
  preferred_num_questions?: number | null;
  onboarding_completed: boolean;
  topic_stats: Array<{
    code: string;
    label: string;
    topic: string;
    attempts_count: number;
    correct_count: number;
    accuracy: number;
    weakness_score: number;
    status?: string | null;
    last_practiced_at?: string | null;
  }>;
  subtopic_stats: Array<{
    code: string;
    label: string;
    topic: string;
    attempts_count: number;
    correct_count: number;
    accuracy: number;
    mastery_score: number;
    weakness_score: number;
    status?: string | null;
    last_practiced_at?: string | null;
  }>;
  error_stats: Array<{
    code: string;
    label: string;
    topic: string;
    attempts_count: number;
    incorrect_count: number;
    error_rate: number;
    weakness_score: number;
    status?: string | null;
    last_seen_at?: string | null;
  }>;
  next_plan: {
    topic: string;
    difficulty: string;
    exercise_type: string;
    num_questions: number;
    focus_reason: string;
    content_theme?: string | null;
    target_subtopic?: string | null;
    target_error_tag?: string | null;
    learner_summary?: string;
  };
};

export type UpdateUserProfileRequest = {
  userId: string;
  displayName: string;
  level: string;
  goals: string[];
  preferredDifficulty: string;
  preferredNumQuestions: number;
  weakTopics: string[];
};

export type InterpretOnboardingRequest = {
  userId: string;
  message: string;
  currentAnswers: Record<string, unknown>;
  currentStepKey?: string | null;
};

export type InterpretOnboardingResponse = {
  answers: Record<string, unknown>;
  assistant_reply: string;
  next_question?: string | null;
  next_step_key?: string | null;
  is_complete: boolean;
  confidence: number;
  source: string;
  raw_llm_response?: string;
};

export type InterpretPracticeRequest = {
  userId: string;
  message: string;
};

export type InterpretPracticeResponse = {
  request: {
    topic?: string | null;
    difficulty?: string | null;
    exercise_type?: string | null;
    num_questions?: number | null;
    target_subtopic?: string | null;
    content_theme?: string | null;
  };
  assistant_reply: string;
  needs_clarification: boolean;
  clarification_question?: string | null;
  confidence: number;
  source: string;
  raw_llm_response?: string;
};

export type UserProfileResponse = {
  user_id: string;
  display_name: string;
  level: string;
  goals: string[];
  preferred_difficulty?: string | null;
  preferred_num_questions?: number | null;
  onboarding_completed: boolean;
};

export type ChatMemoryResumeResponse = {
  session_id: string;
  has_history: boolean;
  memory_summary: string;
  extracted_facts: Record<string, unknown>;
  suggested_next_question: string;
  messages: Array<{
    message_id: string;
    role: "user" | "assistant";
    content: string;
    created_at?: string | null;
  }>;
};

export type SaveChatMessageRequest = {
  userId: string;
  sessionId?: string | null;
  role: "user" | "assistant";
  content: string;
  metadata?: Record<string, unknown>;
  updateMemory?: boolean;
};

export type SaveChatMessageResponse = {
  session_id: string;
  message: {
    message_id: string;
    role: "user" | "assistant";
    content: string;
    created_at?: string | null;
  };
  memory_summary: string;
  extracted_facts: Record<string, unknown>;
  suggested_next_question: string;
};

export type ChromaDebugResponse = {
  configured_backend: string;
  using_chroma_backend: boolean;
  collection_name: string;
  persist_directory: string;
  is_available: boolean;
  status_message: string;
  total_chunks: number;
  topic_counts: Record<string, number>;
  level_counts: Record<string, number>;
  sample_chunks: Array<{
    chunk_id: string;
    topic: string;
    subtopic?: string | null;
    level: string;
    skill?: string | null;
    source?: string | null;
    content_preview: string;
  }>;
  raw_knowledge_path: string;
  raw_knowledge_count: number;
  ingest_command: string;
  error?: string | null;
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
    contentTheme?: string | null;
  };
  recommendation?: string;
  generatorBackend?: string;
  generationRunId: string;
}> {
  const response = await fetch(`${API_BASE_URL}/api/practice/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: payload.userId,
      message: payload.message,
      topic: payload.intent?.topic,
      difficulty: payload.intent?.difficulty,
      exercise_type: payload.intent?.exerciseType,
      num_questions: payload.intent?.numQuestions,
      target_subtopic: payload.intent?.targetSubtopic,
      content_theme: payload.intent?.contentTheme,
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
      contentTheme: data.plan.content_theme,
    },
    exercises: data.exercises.map((exercise) => ({
      id: exercise.exercise_id,
      type: exercise.exercise_type,
      topic: exercise.topic,
      difficulty: exercise.difficulty,
      skill: exercise.skill,
      subtopic: exercise.subtopic,
      errorTag: exercise.error_tag,
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
    generationRunId: data.generation_run_id,
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
  generationRunId: string;
  sessionCode: string;
  practiceReview?: {
    reviewCode: string;
    evaluator: string;
    summary: string;
    strengths: string[];
    weaknesses: string[];
    nextSteps: string[];
    nextPracticePrompt: string;
  } | null;
}> {
  const response = await fetch(`${API_BASE_URL}/api/practice/score`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: payload.userId,
      generation_run_id: payload.generationRunId,
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
    generationRunId: data.generation_run_id,
    sessionCode: data.session_code,
    practiceReview: data.practice_review
      ? {
          reviewCode: data.practice_review.review_code,
          evaluator: data.practice_review.evaluator,
          summary: data.practice_review.summary,
          strengths: data.practice_review.strengths,
          weaknesses: data.practice_review.weaknesses,
          nextSteps: data.practice_review.next_steps,
          nextPracticePrompt: data.practice_review.next_practice_prompt,
        }
      : null,
  };
}

export async function getPersonalizationSnapshot(
  userId: string,
): Promise<PersonalizationSnapshot> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(userId)}/personalization`,
  );

  if (!response.ok) {
    throw new Error("Failed to load personalization snapshot.");
  }

  const data = (await response.json()) as PersonalizationSnapshotResponse;

  return {
    userId: data.user_id,
    displayName: data.display_name,
    level: data.level,
    goals: data.goals,
    preferredDifficulty: data.preferred_difficulty,
    preferredNumQuestions: data.preferred_num_questions,
    onboardingCompleted: data.onboarding_completed,
    topicStats: data.topic_stats.map((item) => ({
      code: item.code,
      label: item.label,
      topic: item.topic,
      attemptsCount: item.attempts_count,
      correctCount: item.correct_count,
      accuracy: item.accuracy,
      weaknessScore: item.weakness_score,
      status: item.status,
      lastPracticedAt: item.last_practiced_at,
    })),
    subtopicStats: data.subtopic_stats.map((item) => ({
      code: item.code,
      label: item.label,
      topic: item.topic,
      attemptsCount: item.attempts_count,
      correctCount: item.correct_count,
      accuracy: item.accuracy,
      masteryScore: item.mastery_score,
      weaknessScore: item.weakness_score,
      status: item.status,
      lastPracticedAt: item.last_practiced_at,
    })),
    errorStats: data.error_stats.map((item) => ({
      code: item.code,
      label: item.label,
      topic: item.topic,
      attemptsCount: item.attempts_count,
      incorrectCount: item.incorrect_count,
      errorRate: item.error_rate,
      weaknessScore: item.weakness_score,
      status: item.status,
      lastSeenAt: item.last_seen_at,
    })),
    nextPlan: {
      topic: data.next_plan.topic,
      difficulty: data.next_plan.difficulty,
      exerciseType: data.next_plan.exercise_type,
      numQuestions: data.next_plan.num_questions,
      focusReason: data.next_plan.focus_reason,
      targetSubtopic: data.next_plan.target_subtopic,
      targetErrorTag: data.next_plan.target_error_tag,
      learnerSummary: data.next_plan.learner_summary,
      contentTheme: data.next_plan.content_theme,
    },
  };
}

export async function updateUserProfile(
  payload: UpdateUserProfileRequest,
): Promise<UserProfileResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(payload.userId)}/profile`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        display_name: payload.displayName,
        level: payload.level,
        goals: payload.goals,
        preferred_difficulty: payload.preferredDifficulty,
        preferred_num_questions: payload.preferredNumQuestions,
        weak_topics: payload.weakTopics,
        onboarding_completed: true,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to update learner profile.");
  }

  return (await response.json()) as UserProfileResponse;
}

export async function interpretOnboardingAnswer(
  payload: InterpretOnboardingRequest,
): Promise<InterpretOnboardingResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(payload.userId)}/onboarding/interpret`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: payload.message,
        current_answers: payload.currentAnswers,
        current_step_key: payload.currentStepKey,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to interpret onboarding answer.");
  }

  return (await response.json()) as InterpretOnboardingResponse;
}

export async function interpretPracticeRequest(
  payload: InterpretPracticeRequest,
): Promise<{
  request: PracticeIntentFields;
  assistantReply: string;
  needsClarification: boolean;
  clarificationQuestion?: string | null;
  confidence: number;
  source: string;
}> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(payload.userId)}/practice/interpret`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: payload.message,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to interpret practice request.");
  }

  const data = (await response.json()) as InterpretPracticeResponse;

  return {
    request: {
      topic: data.request.topic,
      difficulty: data.request.difficulty,
      exerciseType: data.request.exercise_type,
      numQuestions: data.request.num_questions,
      targetSubtopic: data.request.target_subtopic,
      contentTheme: data.request.content_theme,
    },
    assistantReply: data.assistant_reply,
    needsClarification: data.needs_clarification,
    clarificationQuestion: data.clarification_question,
    confidence: data.confidence,
    source: data.source,
  };
}

export async function getChatResume(userId: string): Promise<ChatMemoryResume> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(userId)}/chat/resume`,
  );

  if (!response.ok) {
    throw new Error("Failed to load chat memory.");
  }

  const data = (await response.json()) as ChatMemoryResumeResponse;
  return mapChatResume(data);
}

export async function saveChatMessage(
  payload: SaveChatMessageRequest,
): Promise<ChatMemoryResume> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(payload.userId)}/chat/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: payload.sessionId,
        role: payload.role,
        content: payload.content,
        metadata: payload.metadata ?? {},
        update_memory: payload.updateMemory ?? true,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to save chat message.");
  }

  const data = (await response.json()) as SaveChatMessageResponse;
  return mapChatResume({
    session_id: data.session_id,
    has_history: true,
    memory_summary: data.memory_summary,
    extracted_facts: data.extracted_facts,
    suggested_next_question: data.suggested_next_question,
    messages: [data.message],
  });
}

export async function getChromaDebugSnapshot(): Promise<ChromaDebugSnapshot> {
  const response = await fetch(`${API_BASE_URL}/api/debug/chroma`);

  if (!response.ok) {
    throw new Error("Failed to load Chroma debug snapshot.");
  }

  const data = (await response.json()) as ChromaDebugResponse;
  return {
    configuredBackend: data.configured_backend,
    usingChromaBackend: data.using_chroma_backend,
    collectionName: data.collection_name,
    persistDirectory: data.persist_directory,
    isAvailable: data.is_available,
    statusMessage: data.status_message,
    totalChunks: data.total_chunks,
    topicCounts: data.topic_counts,
    levelCounts: data.level_counts,
    sampleChunks: data.sample_chunks.map((chunk) => ({
      chunkId: chunk.chunk_id,
      topic: chunk.topic,
      subtopic: chunk.subtopic,
      level: chunk.level,
      skill: chunk.skill,
      source: chunk.source,
      contentPreview: chunk.content_preview,
    })),
    rawKnowledgePath: data.raw_knowledge_path,
    rawKnowledgeCount: data.raw_knowledge_count,
    ingestCommand: data.ingest_command,
    error: data.error,
  };
}

function mapChatResume(data: ChatMemoryResumeResponse): ChatMemoryResume {
  return {
    sessionId: data.session_id,
    hasHistory: data.has_history,
    memorySummary: data.memory_summary,
    extractedFacts: data.extracted_facts,
    suggestedNextQuestion: data.suggested_next_question,
    messages: data.messages.map((message) => ({
      messageId: message.message_id,
      role: message.role,
      content: message.content,
      createdAt: message.created_at,
    })),
  };
}
