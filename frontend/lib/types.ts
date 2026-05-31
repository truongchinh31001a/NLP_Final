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
  question: string;
  options: ExerciseOptionPreview[];
  explanation: string;
};

export type DashboardSnapshot = {
  profile: LearnerProfile;
  weakTopics: WeakTopic[];
  currentPrompt: string;
  requestTags: string[];
  activeFocus: string;
  exercisePreview: ExercisePreview[];
  recommendations: Recommendation[];
  history: SessionHistoryItem[];
};
