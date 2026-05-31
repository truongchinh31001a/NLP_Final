export type LearnerProfile = {
  name: string;
  goal: string;
  level: string;
  preferredDifficulty: string;
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
};

export type ScoreResult = {
  topic: string;
  score: number;
  correctCount: number;
  totalQuestions: number;
  weakTopicsDetected: string[];
  recommendation: string;
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
