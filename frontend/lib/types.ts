export type LearnerProfile = {
  name: string;
  goal: string;
  level: string;
  preferredDifficulty: string;
  preferredNumQuestions?: number | null;
  accuracy: number;
  sessionCount: number;
};

export type WeakTopic = {
  name: string;
  weight: number;
};

export type Recommendation = {
  title: string;
  body: string;
};

export type SessionHistoryItem = {
  id: string;
  topic: string;
  note: string;
  score: number;
};

export type ExerciseOptionPreview = {
  label: string;
  text: string;
  isCorrect: boolean;
};

export type ExercisePreview = {
  id: string;
  type: string;
  topic: string;
  difficulty: string;
  skill?: string;
  subtopic?: string | null;
  errorTag?: string | null;
  question: string;
  options: ExerciseOptionPreview[];
  correctAnswer: string;
  explanation: string;
  sourceChunkIds: string[];
};

export type PracticePlanPreview = {
  topic: string;
  difficulty: string;
  exerciseType: string;
  numQuestions: number;
  focusReason: string;
  contentTheme?: string | null;
  targetSkillId?: string | null;
};

export type ScoreResult = {
  topic: string;
  score: number;
  correctCount: number;
  totalQuestions: number;
  weakTopicsDetected: string[];
  recommendation: string;
  generationRunId?: string;
  sessionCode?: string;
  answerDiagnoses?: AnswerDiagnosis[];
  practiceReview?: PracticeReview | null;
};

export type AnswerDiagnosis = {
  exerciseId: string;
  isCorrect: boolean;
  errorType: string;
  skillId: string;
  topic: string;
  subtopic?: string | null;
  subtype?: string | null;
  severity: number;
  masteryImpact: number;
  explanation: string;
  evidence: Record<string, unknown>;
};

export type PracticeReview = {
  reviewCode: string;
  evaluator: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  nextSteps: string[];
  nextPracticePrompt: string;
};

export type PersistedChatMessage = {
  messageId: string;
  role: "user" | "assistant";
  content: string;
  createdAt?: string | null;
};

export type ChatMemoryResume = {
  sessionId: string;
  hasHistory: boolean;
  memorySummary: string;
  extractedFacts: Record<string, unknown>;
  suggestedNextQuestion: string;
  messages: PersistedChatMessage[];
};

export type ChatSessionSummary = {
  sessionId: string;
  title: string;
  preview: string;
  messageCount: number;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type PersonalizationTopicStat = {
  code: string;
  label: string;
  topic: string;
  attemptsCount: number;
  correctCount: number;
  accuracy: number;
  weaknessScore: number;
  status?: string | null;
  lastPracticedAt?: string | null;
};

export type PersonalizationSubtopicStat = {
  code: string;
  label: string;
  topic: string;
  attemptsCount: number;
  correctCount: number;
  accuracy: number;
  masteryScore: number;
  weaknessScore: number;
  status?: string | null;
  lastPracticedAt?: string | null;
};

export type PersonalizationErrorStat = {
  code: string;
  label: string;
  topic: string;
  attemptsCount: number;
  incorrectCount: number;
  errorRate: number;
  weaknessScore: number;
  status?: string | null;
  lastSeenAt?: string | null;
};

export type PersonalizationSkillMastery = {
  code: string;
  label: string;
  topic: string;
  skillType: string;
  cefr?: string | null;
  masteryProbability: number;
  confidence: number;
  attemptsCount: number;
  correctCount: number;
  incorrectCount: number;
  weaknessScore: number;
  status?: string | null;
  lastPracticedAt?: string | null;
  nextReviewAt?: string | null;
  prerequisites: string[];
};

export type PersonalizationSnapshot = {
  userId: string;
  displayName: string;
  level: string;
  goals: string[];
  preferredDifficulty?: string | null;
  preferredNumQuestions?: number | null;
  onboardingCompleted: boolean;
  topicStats: PersonalizationTopicStat[];
  subtopicStats: PersonalizationSubtopicStat[];
  errorStats: PersonalizationErrorStat[];
  skillMastery: PersonalizationSkillMastery[];
  nextPlan: PracticePlanPreview & {
    targetSubtopic?: string | null;
    targetErrorTag?: string | null;
    targetSkillId?: string | null;
    learnerSummary?: string;
  };
};

export type ChromaDebugChunk = {
  chunkId: string;
  topic: string;
  subtopic?: string | null;
  level: string;
  skill?: string | null;
  source?: string | null;
  contentPreview: string;
};

export type ChromaDebugSnapshot = {
  configuredBackend: string;
  retrievalMode: string;
  embeddingBackend: string;
  rerankerEnabled: boolean;
  usingChromaBackend: boolean;
  collectionName: string;
  persistDirectory: string;
  isAvailable: boolean;
  statusMessage: string;
  totalChunks: number;
  topicCounts: Record<string, number>;
  levelCounts: Record<string, number>;
  sampleChunks: ChromaDebugChunk[];
  rawKnowledgePath: string;
  rawKnowledgeCount: number;
  ingestCommand: string;
  error?: string | null;
};

export type DashboardSnapshot = {
  profile: LearnerProfile;
  weakTopics: WeakTopic[];
  currentPrompt: string;
  requestTags: string[];
  activeFocus: string;
  exercisePreview: ExercisePreview[];
  planPreview: PracticePlanPreview;
  recommendations: Recommendation[];
  history: SessionHistoryItem[];
};
