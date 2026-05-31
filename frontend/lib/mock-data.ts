import type { DashboardSnapshot } from "@/lib/types";

export function getDashboardSnapshot(): DashboardSnapshot {
  return {
    profile: {
      name: "An Nguyen",
      goal: "Improve grammar accuracy for classroom quizzes and weekly self-study.",
      level: "Intermediate",
      preferredDifficulty: "Medium",
      accuracy: 0.72,
      sessionCount: 18,
    },
    weakTopics: [
      { name: "Passive voice", weight: 0.86 },
      { name: "Relative clauses", weight: 0.63 },
      { name: "Conditional sentences", weight: 0.48 },
    ],
    currentPrompt:
      "I am weak at passive voice. Generate 5 medium multiple-choice questions and explain each answer.",
    requestTags: ["passive voice", "medium", "mcq", "5 questions"],
    activeFocus: "Past simple passive",
    exercisePreview: [
      {
        id: "exercise-1",
        type: "MCQ",
        topic: "passive_voice",
        difficulty: "medium",
        question:
          "Which sentence is correctly written in the passive voice for a past event?",
        options: [
          {
            label: "A",
            text: "The report was finished before noon.",
            isCorrect: true,
          },
          {
            label: "B",
            text: "The report has finish before noon.",
            isCorrect: false,
          },
          {
            label: "C",
            text: "The report finishing before noon.",
            isCorrect: false,
          },
          {
            label: "D",
            text: "The report was finish before noon.",
            isCorrect: false,
          },
        ],
        correctAnswer: "A",
        explanation:
          "A uses the correct past simple passive structure: was + past participle.",
        sourceChunkIds: ["grammar-passive-01"],
      },
      {
        id: "exercise-2",
        type: "MCQ",
        topic: "passive_voice",
        difficulty: "medium",
        question:
          "Why should the learner stay on passive voice for the next session?",
        options: [
          {
            label: "A",
            text: "Because recent answers show repeated tense-form mistakes.",
            isCorrect: true,
          },
          {
            label: "B",
            text: "Because random topic switching improves personalization.",
            isCorrect: false,
          },
          {
            label: "C",
            text: "Because retrieval is not needed for grammar topics.",
            isCorrect: false,
          },
          {
            label: "D",
            text: "Because explanations should be hidden after scoring.",
            isCorrect: false,
          },
        ],
        correctAnswer: "A",
        explanation:
          "The recommendation engine should keep the learner near the weakness until accuracy becomes stable.",
        sourceChunkIds: ["profile-session-18"],
      },
    ],
    planPreview: {
      topic: "passive_voice",
      difficulty: "medium",
      exerciseType: "grammar_mcq",
      numQuestions: 5,
      focusReason:
        "Focused on the strongest weak topic and kept the difficulty near the learner preference.",
    },
    recommendations: [
      {
        title: "Next practice recommendation",
        body:
          "Stay with passive voice, but narrow to past simple passive and keep difficulty at easy-medium for one more session.",
      },
      {
        title: "Feedback strategy",
        body:
          "Show why the distractors are wrong, not only why the correct answer is right. This makes the weakness pattern easier to understand.",
      },
    ],
    history: [
      {
        id: "session-18",
        topic: "Passive voice",
        note: "Weakness concentrated in tense agreement.",
        score: 0.6,
      },
      {
        id: "session-17",
        topic: "Travel vocabulary",
        note: "Learner handled context words well with strong distractor rejection.",
        score: 0.88,
      },
      {
        id: "session-16",
        topic: "Relative clauses",
        note: "Confusion remains between who, which, and that.",
        score: 0.67,
      },
    ],
  };
}
