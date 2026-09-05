import type {
  ChatMemoryResume,
  ChatSessionSummary,
  ChromaDebugSnapshot,
  ConversationRoute,
  ConversationTurn,
  ExercisePreview,
  LearningActivityPreview,
  NextActivitySuggestion,
  PendingClarification,
  PersonalizationSnapshot,
  PracticePlanPreview,
  ScoreResult,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const AUTH_TOKEN = process.env.NEXT_PUBLIC_AUTH_TOKEN;

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return AUTH_TOKEN
    ? {
        ...extra,
        Authorization: `Bearer ${AUTH_TOKEN}`,
      }
    : extra;
}

export type GeneratePracticeRequest = {
  userId: string;
  message: string;
  conversationId?: string | null;
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
  activity_id?: string | null;
  generation_run_id: string;
  request?: Record<string, unknown>;
  plan: {
    topic: string;
    difficulty: string;
    exercise_type: string;
    num_questions: number;
    focus_reason: string;
    content_theme?: string | null;
    target_skill_id?: string | null;
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
  activity_id?: string | null;
  generation_run_id: string;
  session_code: string;
  answer_diagnoses?: Array<{
    exercise_id: string;
    is_correct: boolean;
    error_type: string;
    skill_id: string;
    topic: string;
    subtopic?: string | null;
    subtype?: string | null;
    severity: number;
    mastery_impact: number;
    explanation: string;
    evidence: Record<string, unknown>;
  }>;
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

export type NextActivitySuggestionResponse = {
  recommendation_id?: string | null;
  user_id?: string | null;
  source_activity_id?: string | null;
  conversation_id?: string | null;
  skill?: string | null;
  topic?: string | null;
  subtopic?: string | null;
  difficulty?: string | null;
  exercise_type?: string | null;
  num_questions?: number | null;
  reason?: string | null;
  prompt?: string | null;
  evidence?: Record<string, unknown> | null;
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
  skill_mastery?: Array<{
    code: string;
    label: string;
    topic: string;
    skill_type: string;
    cefr?: string | null;
    mastery_probability: number;
    confidence: number;
    attempts_count: number;
    correct_count: number;
    incorrect_count: number;
    weakness_score: number;
    status?: string | null;
    last_practiced_at?: string | null;
    next_review_at?: string | null;
    prerequisites: string[];
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
    target_skill_id?: string | null;
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
  messages: ChatMessageResponse[];
  pending_clarification?: PendingClarificationResponse | null;
  active_activity?: LearningActivityResponse | null;
};

export type ChatSessionSummaryResponse = {
  session_id: string;
  title: string;
  preview: string;
  message_count: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ChatSessionListResponse = {
  sessions: ChatSessionSummaryResponse[];
};

export type ConversationSummaryResponse = {
  conversation_id: string;
  title: string;
  preview: string;
  message_count: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ConversationListResponse = {
  conversations: ConversationSummaryResponse[];
};

export type ConversationDetailResponse = {
  conversation_id: string;
  has_history: boolean;
  memory_summary: string;
  extracted_facts: Record<string, unknown>;
  suggested_next_question: string;
  messages: ChatMessageResponse[];
  pending_clarification?: PendingClarificationResponse | null;
  active_activity?: LearningActivityResponse | null;
};

export type ChatMessageResponse = {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
};

export type PendingClarificationResponse = {
  pending_intent: string;
  missing_fields: string[];
  collected_slots: Record<string, unknown>;
  question: string;
};

export type ConversationRouteResponse = {
  intent: string;
  confidence: number;
  source: string;
  reason: string;
  slots: Record<string, unknown>;
  missing_slots?: string[];
  referenced_activity_id?: string | null;
  needs_clarification: boolean;
  clarification_question?: string | null;
};

export type LearningActivityResponse = {
  activity_id: string;
  conversation_id: string;
  learner_id: string;
  type: string;
  status: string;
  target_skills?: string[];
  difficulty?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  submitted_at?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
  generation_run_id?: string | null;
  session_code?: string | null;
  metadata?: Record<string, unknown>;
  request?: Record<string, unknown> | null;
  plan?: GeneratePracticeResponse["plan"] | null;
  exercises?: GeneratePracticeResponse["exercises"];
  result?: ScorePracticeResponse | null;
  recommendation?: string;
  next_activity_suggestion?: NextActivitySuggestionResponse | null;
  ui_action?: string;
};

export type ActivityReviewResponse = {
  learner_id: string;
  activity_id: string;
  conversation_id: string;
  assistant_reply: string;
  activity?: LearningActivityResponse | null;
  metadata?: Record<string, unknown>;
  ui_action: string;
};

export type ConversationMessageTurnResponse = {
  conversation_id: string;
  message: ChatMessageResponse;
  intent: string;
  assistant_reply: string;
  pending_clarification?: PendingClarificationResponse | null;
  activity?: LearningActivityResponse | null;
  ui_action: string;
  assistant_message?: ChatMessageResponse | null;
  route?: ConversationRouteResponse | null;
};

export type SubmitActivityRequest = {
  userId: string;
  activityId: string;
  answers?: Array<{
    exerciseId: string;
    selectedAnswer: string;
  }>;
  writingText?: string;
};

export type ActivitySubmitResponse = {
  activity: LearningActivityResponse;
  result: ScorePracticeResponse;
  exercises: GeneratePracticeResponse["exercises"];
  answers: Array<{
    exercise_id: string;
    selected_answer: string;
  }>;
  next_activity_suggestion?: NextActivitySuggestionResponse | null;
  ui_action: string;
};

export type ActivitySubmitResult = {
  activity: LearningActivityPreview;
  result: ScoreResult;
  exercises: ExercisePreview[];
  answers: Array<{
    exerciseId: string;
    selectedAnswer: string;
  }>;
  nextActivitySuggestion?: NextActivitySuggestion | null;
  uiAction: string;
};

export type ActivityReviewResult = {
  learnerId: string;
  activityId: string;
  conversationId: string;
  assistantReply: string;
  activity: LearningActivityPreview | null;
  metadata: Record<string, unknown>;
  uiAction: string;
};

export type RecommendationListResponse = {
  recommendations: NextActivitySuggestionResponse[];
};

export type RecommendationAcceptResponse = {
  recommendation: NextActivitySuggestionResponse;
  activity: LearningActivityResponse;
  ui_action: string;
};

export type RecommendationAcceptResult = {
  recommendation: NextActivitySuggestion;
  activity: LearningActivityPreview;
  uiAction: string;
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
  retrieval_mode: string;
  embedding_backend: string;
  reranker_enabled: boolean;
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

// Legacy compatibility client. The main UI uses conversation/activity endpoints.
export async function generatePractice(
  payload: GeneratePracticeRequest,
): Promise<{
  exercises: ExercisePreview[];
  plan: PracticePlanPreview;
  recommendation?: string;
  generatorBackend?: string;
  activityId?: string | null;
  generationRunId: string;
}> {
  const response = await fetch(`${API_BASE_URL}/api/practice/generate`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      user_id: payload.userId,
      message: payload.message,
      conversation_id: payload.conversationId,
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
    plan: mapPracticePlan(data.plan),
    exercises: data.exercises.map(mapExercisePreview),
    recommendation: data.recommendation,
    generatorBackend: data.generator_backend,
    activityId: data.activity_id,
    generationRunId: data.generation_run_id,
  };
}

// Legacy compatibility client. The main UI submits practice by activity id.
export async function scorePractice(
  payload: ScorePracticeRequest,
): Promise<ScoreResult> {
  const response = await fetch(`${API_BASE_URL}/api/practice/score`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
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
  return mapScoreResult(data);
}

export async function createConversation(
  userId: string,
): Promise<ChatMemoryResume> {
  const response = await fetch(`${API_BASE_URL}/api/conversations`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      user_id: userId,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to create conversation.");
  }

  const data = (await response.json()) as ConversationDetailResponse;
  return mapConversationDetail(data);
}

export async function listConversations(
  userId: string,
): Promise<ChatSessionSummary[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations?user_id=${encodeURIComponent(userId)}`,
    {
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to load conversations.");
  }

  const data = (await response.json()) as ConversationListResponse;
  return data.conversations.map(mapConversationSummary);
}

export async function getConversation(
  userId: string,
  conversationId: string,
): Promise<ChatMemoryResume> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(
      conversationId,
    )}?user_id=${encodeURIComponent(userId)}`,
    {
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to load conversation.");
  }

  const data = (await response.json()) as ConversationDetailResponse;
  return mapConversationDetail(data);
}

export async function sendConversationMessage(payload: {
  userId: string;
  conversationId: string;
  message: string;
  metadata?: Record<string, unknown>;
}): Promise<ConversationTurn> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(
      payload.conversationId,
    )}/messages`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        user_id: payload.userId,
        message: payload.message,
        metadata: payload.metadata ?? {},
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to send conversation message.");
  }

  const data = (await response.json()) as ConversationMessageTurnResponse;
  return mapConversationTurn(data);
}

export async function getActivity(
  userId: string,
  activityId: string,
): Promise<LearningActivityPreview> {
  const params = new URLSearchParams({ user_id: userId });
  const response = await fetch(
    `${API_BASE_URL}/api/activities/${encodeURIComponent(activityId)}?${params}`,
    {
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to load activity.");
  }

  const activity = mapLearningActivity(
    (await response.json()) as LearningActivityResponse,
  );
  if (!activity) {
    throw new Error("Backend returned an invalid activity.");
  }
  return activity;
}

export async function getActivityReview(payload: {
  userId: string;
  activityId: string;
  questionNumber?: number | null;
}): Promise<ActivityReviewResult> {
  const params = new URLSearchParams({ user_id: payload.userId });
  if (payload.questionNumber) {
    params.set("question_number", String(payload.questionNumber));
  }
  const response = await fetch(
    `${API_BASE_URL}/api/activities/${encodeURIComponent(
      payload.activityId,
    )}/review?${params}`,
    {
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to load activity review.");
  }

  const data = (await response.json()) as ActivityReviewResponse;
  return {
    learnerId: data.learner_id,
    activityId: data.activity_id,
    conversationId: data.conversation_id,
    assistantReply: data.assistant_reply,
    activity: mapLearningActivity(data.activity),
    metadata: data.metadata ?? {},
    uiAction: data.ui_action,
  };
}

export async function submitActivity(
  payload: SubmitActivityRequest,
): Promise<ActivitySubmitResult> {
  const response = await fetch(
    `${API_BASE_URL}/api/activities/${encodeURIComponent(
      payload.activityId,
    )}/submit`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        user_id: payload.userId,
        answers: (payload.answers ?? []).map((answer) => ({
          exercise_id: answer.exerciseId,
          selected_answer: answer.selectedAnswer,
        })),
        writing_text: payload.writingText,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to submit activity.");
  }

  const data = (await response.json()) as ActivitySubmitResponse;
  const nextActivitySuggestion = mapNextActivitySuggestion(
    data.next_activity_suggestion ?? data.activity.next_activity_suggestion,
  );
  const result = mapScoreResult(data.result, nextActivitySuggestion);
  const activity = mapLearningActivity({
    ...data.activity,
    exercises: data.exercises.length ? data.exercises : data.activity.exercises,
    result: data.result,
    next_activity_suggestion: data.next_activity_suggestion,
  });

  if (!activity) {
    throw new Error("Backend returned an invalid activity.");
  }

  return {
    activity,
    result,
    exercises: data.exercises.map(mapExercisePreview),
    answers: data.answers.map((answer) => ({
      exerciseId: answer.exercise_id,
      selectedAnswer: answer.selected_answer,
    })),
    nextActivitySuggestion,
    uiAction: data.ui_action,
  };
}

export async function listRecommendations(
  userId: string,
  limit = 5,
): Promise<NextActivitySuggestion[]> {
  const params = new URLSearchParams({
    limit: String(limit),
  });
  const response = await fetch(
    `${API_BASE_URL}/api/learners/${encodeURIComponent(
      userId,
    )}/recommendations?${params}`,
    {
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to load recommendations.");
  }

  const data = (await response.json()) as RecommendationListResponse;
  return data.recommendations
    .map(mapNextActivitySuggestion)
    .filter(
      (recommendation): recommendation is NextActivitySuggestion =>
        recommendation !== null,
    );
}

export async function acceptRecommendation(payload: {
  userId: string;
  recommendationId: string;
  conversationId?: string | null;
}): Promise<RecommendationAcceptResult> {
  const response = await fetch(
    `${API_BASE_URL}/api/recommendations/${encodeURIComponent(
      payload.recommendationId,
    )}/accept`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        user_id: payload.userId,
        conversation_id: payload.conversationId,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to accept recommendation.");
  }

  const data = (await response.json()) as RecommendationAcceptResponse;
  const recommendation = mapNextActivitySuggestion(data.recommendation);
  const activity = mapLearningActivity(data.activity);
  if (!recommendation || !activity) {
    throw new Error("Backend returned an invalid recommendation activity.");
  }

  return {
    recommendation,
    activity,
    uiAction: data.ui_action,
  };
}

export async function getPersonalizationSnapshot(
  userId: string,
): Promise<PersonalizationSnapshot> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(userId)}/personalization`,
    {
      headers: authHeaders(),
    },
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
    skillMastery: (data.skill_mastery ?? []).map((item) => ({
      code: item.code,
      label: item.label,
      topic: item.topic,
      skillType: item.skill_type,
      cefr: item.cefr,
      masteryProbability: item.mastery_probability,
      confidence: item.confidence,
      attemptsCount: item.attempts_count,
      correctCount: item.correct_count,
      incorrectCount: item.incorrect_count,
      weaknessScore: item.weakness_score,
      status: item.status,
      lastPracticedAt: item.last_practiced_at,
      nextReviewAt: item.next_review_at,
      prerequisites: item.prerequisites,
    })),
    nextPlan: {
      topic: data.next_plan.topic,
      difficulty: data.next_plan.difficulty,
      exerciseType: data.next_plan.exercise_type,
      numQuestions: data.next_plan.num_questions,
      focusReason: data.next_plan.focus_reason,
      targetSubtopic: data.next_plan.target_subtopic,
      targetErrorTag: data.next_plan.target_error_tag,
      targetSkillId: data.next_plan.target_skill_id,
      learnerSummary: data.next_plan.learner_summary,
      contentTheme: data.next_plan.content_theme,
    },
  };
}

export async function updateUserProfile(
  payload: UpdateUserProfileRequest,
): Promise<UserProfileResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/learners/${encodeURIComponent(payload.userId)}/profile`,
    {
      method: "PATCH",
      headers: authHeaders({ "Content-Type": "application/json" }),
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
      headers: authHeaders({ "Content-Type": "application/json" }),
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
      headers: authHeaders({ "Content-Type": "application/json" }),
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
    {
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to load chat memory.");
  }

  const data = (await response.json()) as ChatMemoryResumeResponse;
  return mapChatResume(data);
}

export async function listChatSessions(
  userId: string,
): Promise<ChatSessionSummary[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(userId)}/chat/sessions`,
    {
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to load chat sessions.");
  }

  const data = (await response.json()) as ChatSessionListResponse;
  return data.sessions.map(mapChatSessionSummary);
}

export async function createChatSession(
  userId: string,
): Promise<ChatMemoryResume> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(userId)}/chat/sessions`,
    {
      method: "POST",
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to create chat session.");
  }

  const data = (await response.json()) as ChatMemoryResumeResponse;
  return mapChatResume(data);
}

export async function getChatSession(
  userId: string,
  sessionId: string,
): Promise<ChatMemoryResume> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/${encodeURIComponent(
      userId,
    )}/chat/sessions/${encodeURIComponent(sessionId)}`,
    {
      headers: authHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to load chat session.");
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
      headers: authHeaders({ "Content-Type": "application/json" }),
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
    retrievalMode: data.retrieval_mode,
    embeddingBackend: data.embedding_backend,
    rerankerEnabled: data.reranker_enabled,
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
    messages: data.messages.map(mapChatMessage),
    pendingClarification: mapPendingClarification(data.pending_clarification),
    activeActivity: mapLearningActivity(data.active_activity),
  };
}

function mapConversationDetail(data: ConversationDetailResponse): ChatMemoryResume {
  return {
    sessionId: data.conversation_id,
    hasHistory: data.has_history,
    memorySummary: data.memory_summary,
    extractedFacts: data.extracted_facts,
    suggestedNextQuestion: data.suggested_next_question,
    messages: data.messages.map(mapChatMessage),
    pendingClarification: mapPendingClarification(data.pending_clarification),
    activeActivity: mapLearningActivity(data.active_activity),
  };
}

function mapChatSessionSummary(
  data: ChatSessionSummaryResponse,
): ChatSessionSummary {
  return {
    sessionId: data.session_id,
    title: data.title,
    preview: data.preview,
    messageCount: data.message_count,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  };
}

function mapConversationSummary(
  data: ConversationSummaryResponse,
): ChatSessionSummary {
  return {
    sessionId: data.conversation_id,
    title: data.title,
    preview: data.preview,
    messageCount: data.message_count,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  };
}

function mapConversationTurn(data: ConversationMessageTurnResponse): ConversationTurn {
  return {
    conversationId: data.conversation_id,
    message: mapChatMessage(data.message),
    intent: data.intent,
    assistantReply: data.assistant_reply,
    pendingClarification: mapPendingClarification(data.pending_clarification),
    activity: mapLearningActivity(data.activity),
    uiAction: data.ui_action,
    assistantMessage: data.assistant_message
      ? mapChatMessage(data.assistant_message)
      : null,
    route: mapConversationRoute(data.route),
  };
}

function mapChatMessage(data: ChatMessageResponse) {
  const metadata = isRecord(data.metadata) ? data.metadata : {};
  const activity = mapLearningActivity(metadata.activity);
  const uiAction =
    typeof metadata.ui_action === "string" ? metadata.ui_action : null;

  return {
    messageId: data.message_id,
    role: data.role,
    content: data.content,
    metadata,
    activity,
    uiAction,
    createdAt: data.created_at,
  };
}

function mapPendingClarification(
  data?: PendingClarificationResponse | null,
): PendingClarification | null {
  if (!data) {
    return null;
  }
  return {
    pendingIntent: data.pending_intent,
    missingFields: data.missing_fields,
    collectedSlots: data.collected_slots,
    question: data.question,
  };
}

function mapConversationRoute(
  data?: ConversationRouteResponse | null,
): ConversationRoute | null {
  if (!data) {
    return null;
  }
  return {
    intent: data.intent,
    confidence: data.confidence,
    source: data.source,
    reason: data.reason,
    slots: data.slots,
    missingSlots: data.missing_slots ?? [],
    referencedActivityId: data.referenced_activity_id,
    needsClarification: data.needs_clarification,
    clarificationQuestion: data.clarification_question,
  };
}

function mapLearningActivity(
  rawActivity?: unknown,
): LearningActivityPreview | null {
  if (!isRecord(rawActivity)) {
    return null;
  }
  const activityId = getString(rawActivity.activity_id);
  const conversationId = getString(rawActivity.conversation_id);
  const learnerId = getString(rawActivity.learner_id);
  const type = getString(rawActivity.type);
  const status = getString(rawActivity.status);
  if (!activityId || !conversationId || !learnerId || !type || !status) {
    return null;
  }

  const rawPlan = isRecord(rawActivity.plan) ? rawActivity.plan : null;
  const rawExercises = Array.isArray(rawActivity.exercises)
    ? rawActivity.exercises
    : [];
  const nextActivitySuggestion = mapNextActivitySuggestion(
    rawActivity.next_activity_suggestion,
  );
  const rawResult = isRecord(rawActivity.result)
    ? (rawActivity.result as ScorePracticeResponse)
    : null;

  return {
    activityId,
    conversationId,
    learnerId,
    type,
    status,
    targetSkills: Array.isArray(rawActivity.target_skills)
      ? rawActivity.target_skills.map(String).filter(Boolean)
      : [],
    difficulty: getString(rawActivity.difficulty),
    createdAt: getString(rawActivity.created_at),
    startedAt: getString(rawActivity.started_at),
    submittedAt: getString(rawActivity.submitted_at),
    completedAt: getString(rawActivity.completed_at),
    updatedAt: getString(rawActivity.updated_at),
    generationRunId: getString(rawActivity.generation_run_id),
    sessionCode: getString(rawActivity.session_code),
    metadata: isRecord(rawActivity.metadata) ? rawActivity.metadata : {},
    request: isRecord(rawActivity.request) ? rawActivity.request : null,
    plan: rawPlan ? mapPracticePlan(rawPlan) : null,
    exercises: rawExercises
      .filter(isRecord)
      .map((exercise) => mapExercisePreview(exercise)),
    result: rawResult ? mapScoreResult(rawResult, nextActivitySuggestion) : null,
    recommendation: getString(rawActivity.recommendation) ?? "",
    nextActivitySuggestion,
    uiAction: getString(rawActivity.ui_action),
  };
}

function mapPracticePlan(rawPlan: Record<string, unknown>): PracticePlanPreview {
  return {
    topic: getString(rawPlan.topic) ?? "grammar",
    difficulty: getString(rawPlan.difficulty) ?? "medium",
    exerciseType: getString(rawPlan.exercise_type) ?? "grammar_mcq",
    numQuestions: getNumber(rawPlan.num_questions) ?? 5,
    focusReason: getString(rawPlan.focus_reason) ?? "",
    contentTheme: getString(rawPlan.content_theme),
    targetSkillId: getString(rawPlan.target_skill_id),
  };
}

function mapExercisePreview(rawExercise: Record<string, unknown>): ExercisePreview {
  const rawOptions = Array.isArray(rawExercise.options)
    ? rawExercise.options
    : [];
  const sourceChunkIds = Array.isArray(rawExercise.source_chunk_ids)
    ? rawExercise.source_chunk_ids.map(String).filter(Boolean)
    : [];

  return {
    id: getString(rawExercise.exercise_id) ?? "",
    type: getString(rawExercise.exercise_type) ?? "grammar_mcq",
    topic: getString(rawExercise.topic) ?? "grammar",
    difficulty: getString(rawExercise.difficulty) ?? "medium",
    skill: getString(rawExercise.skill) ?? undefined,
    subtopic: getString(rawExercise.subtopic),
    errorTag: getString(rawExercise.error_tag),
    question: getString(rawExercise.question_text) ?? "",
    options: rawOptions.filter(isRecord).map((option) => ({
      label: getString(option.label) ?? "",
      text: getString(option.text) ?? "",
      isCorrect: Boolean(option.is_correct),
    })),
    correctAnswer: getString(rawExercise.correct_answer) ?? "",
    explanation: getString(rawExercise.explanation) ?? "",
    sourceChunkIds,
  };
}

function mapScoreResult(
  data: ScorePracticeResponse,
  nextActivitySuggestion?: NextActivitySuggestion | null,
): ScoreResult {
  return {
    topic: data.topic,
    score: data.score,
    correctCount: data.correct_count,
    totalQuestions: data.total_questions,
    weakTopicsDetected: data.weak_topics_detected,
    recommendation: data.recommendation,
    activityId: data.activity_id,
    generationRunId: data.generation_run_id,
    sessionCode: data.session_code,
    answerDiagnoses: (data.answer_diagnoses ?? []).map((diagnosis) => ({
      exerciseId: diagnosis.exercise_id,
      isCorrect: diagnosis.is_correct,
      errorType: diagnosis.error_type,
      skillId: diagnosis.skill_id,
      topic: diagnosis.topic,
      subtopic: diagnosis.subtopic,
      subtype: diagnosis.subtype,
      severity: diagnosis.severity,
      masteryImpact: diagnosis.mastery_impact,
      explanation: diagnosis.explanation,
      evidence: diagnosis.evidence,
    })),
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
    nextActivitySuggestion,
  };
}

function mapNextActivitySuggestion(
  rawSuggestion?: unknown,
): NextActivitySuggestion | null {
  if (!isRecord(rawSuggestion)) {
    return null;
  }
  const topic = getString(rawSuggestion.topic);
  if (!topic) {
    return null;
  }
  return {
    recommendationId: getString(rawSuggestion.recommendation_id) ?? undefined,
    userId: getString(rawSuggestion.user_id) ?? undefined,
    sourceActivityId: getString(rawSuggestion.source_activity_id),
    conversationId: getString(rawSuggestion.conversation_id),
    skill: getString(rawSuggestion.skill),
    topic,
    subtopic: getString(rawSuggestion.subtopic),
    difficulty: getString(rawSuggestion.difficulty),
    exerciseType: getString(rawSuggestion.exercise_type),
    numQuestions: getNumber(rawSuggestion.num_questions),
    reason: getString(rawSuggestion.reason) ?? undefined,
    prompt: getString(rawSuggestion.prompt) ?? undefined,
    evidence: isRecord(rawSuggestion.evidence) ? rawSuggestion.evidence : undefined,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function getNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}
