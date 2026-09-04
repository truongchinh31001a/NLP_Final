"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { Steps } from "antd";
import {
  BarChartOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  EditOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  LoadingOutlined,
  PlusOutlined,
  RobotOutlined,
  SearchOutlined,
  SendOutlined,
  TranslationOutlined,
  UserOutlined,
} from "@ant-design/icons";

import {
  createChatSession,
  generatePractice,
  getChatResume,
  getChatSession,
  getPersonalizationSnapshot,
  interpretOnboardingAnswer,
  interpretPracticeRequest,
  listChatSessions,
  saveChatMessage,
  scorePractice,
  type PracticeIntentFields,
  updateUserProfile,
} from "@/lib/api";
import type {
  ChatMemoryResume,
  ChatSessionSummary,
  DashboardSnapshot,
  ExercisePreview,
  PersonalizationSnapshot,
  PracticePlanPreview,
  ScoreResult,
} from "@/lib/types";

type ChatWorkbenchProps = {
  snapshot: DashboardSnapshot;
};

type Screen = "chat" | "generating" | "practice" | "result";

type OnboardingValues = {
  displayName: string;
  level: string;
  goals: string[];
  preferredDifficulty: string;
  preferredNumQuestions: number;
  weakTopics: string[];
};

type OnboardingStepKey = keyof OnboardingValues;

type ChatMessage = {
  id: string;
  role: "bot" | "user";
  content: string;
  createdAt?: string | null;
};

type ChatSessionHistoryItem = {
  id: string;
  backendSessionId?: string | null;
  title: string;
  preview: string;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
};

type OnboardingStep = {
  key: OnboardingStepKey;
  question: string;
  quickReplies?: Array<{
    label: string;
    value: string;
  }>;
};

type OnboardingInterpretationResult = {
  answers: Partial<OnboardingValues>;
  assistantReply: string;
  nextQuestion?: string | null;
  nextStepKey?: OnboardingStepKey | null;
  source: string;
};

type PracticeInterpretationResult = {
  request: PracticeIntentFields;
  assistantReply: string;
  needsClarification: boolean;
  clarificationQuestion?: string | null;
  source: string;
};

const USER_ID = "demo-user";
const CHAT_SESSION_HISTORY_LIMIT = 12;
const CHAT_SESSION_STORAGE_KEY = `english-tutor-chat-sessions:${USER_ID}`;

const weakTopicOptions = [
  { label: "Passive voice", value: "passive_voice" },
  { label: "Relative clause", value: "relative_clause" },
  { label: "Conditional sentence", value: "conditional_sentence" },
  { label: "Reported speech", value: "reported_speech" },
  { label: "Tenses", value: "tenses" },
  { label: "Prepositions", value: "prepositions" },
  { label: "Vocabulary", value: "vocabulary" },
  { label: "Travel vocabulary", value: "travel_vocabulary" },
];

const onboardingSteps: OnboardingStep[] = [
  {
    key: "displayName",
    question: "Mình gọi bạn là gì cho thân thiện nhỉ? Tên thật hay nickname đều được.",
  },
  {
    key: "level",
    question: "Bạn đang ở mức nào? Nếu chưa chắc, cứ chọn mức gần nhất, mình sẽ tự điều chỉnh sau vài bài.",
    quickReplies: [
      { label: "Beginner", value: "beginner" },
      { label: "Intermediate", value: "intermediate" },
      { label: "Advanced", value: "advanced" },
    ],
  },
  {
    key: "goals",
    question:
      "Bạn học tiếng Anh để làm gì nhiều nhất lúc này? Ví dụ: giao tiếp, TOEIC, ngữ pháp, từ vựng, đi du lịch.",
    quickReplies: [
      { label: "Giao tiếp", value: "giao tiep hang ngay" },
      { label: "TOEIC", value: "thi TOEIC va on ngu phap" },
      { label: "Du lịch", value: "tieng Anh du lich va giao tiep san bay" },
    ],
  },
  {
    key: "weakTopics",
    question:
      "Phần nào làm bạn hay khựng nhất? Bạn có thể nói nhiều ý, ví dụ: thì, bị động, giới từ, mệnh đề quan hệ.",
    quickReplies: weakTopicOptions.slice(0, 4).map((option) => ({
      label: option.label,
      value: option.value,
    })),
  },
  {
    key: "preferredDifficulty",
    question: "Mình nên bắt đầu nhẹ nhàng hay thử thách một chút?",
    quickReplies: [
      { label: "Easy", value: "easy" },
      { label: "Medium", value: "medium" },
      { label: "Hard", value: "hard" },
    ],
  },
  {
    key: "preferredNumQuestions",
    question: "Mỗi lần luyện bạn muốn khoảng bao nhiêu câu để vừa sức?",
    quickReplies: [
      { label: "5 câu", value: "5" },
      { label: "7 câu", value: "7" },
      { label: "10 câu", value: "10" },
    ],
  },
];

const generationSteps = [
  {
    title: "Hiểu yêu cầu",
    description: "Đọc tiếng Việt/tiếng Anh và chuẩn hóa ý bạn muốn luyện.",
    icon: <TranslationOutlined />,
  },
  {
    title: "Chọn dạng bài",
    description: "Xác định chủ đề, độ khó, số câu và kiểu câu hỏi.",
    icon: <ExperimentOutlined />,
  },
  {
    title: "Đọc hồ sơ học",
    description: "Xem lại mục tiêu, điểm yếu và kết quả gần đây.",
    icon: <SearchOutlined />,
  },
  {
    title: "Tìm kiến thức liên quan",
    description: "Lấy mảnh kiến thức phù hợp để câu hỏi không bị lan man.",
    icon: <DatabaseOutlined />,
  },
  {
    title: "Tạo câu hỏi",
    description: "Sinh bài luyện theo đúng hồ sơ và yêu cầu hiện tại.",
    icon: <RobotOutlined />,
  },
  {
    title: "Kiểm tra lại",
    description: "Rà đáp án, lựa chọn và giải thích trước khi đưa cho bạn.",
    icon: <CheckCircleOutlined />,
  },
];

const promptSuggestions = [
  {
    label: "Ngữ pháp cơ bản",
    value:
      "Mình mới học lại tiếng Anh. Tạo cho mình 5 câu ngữ pháp cơ bản mức dễ, có giải thích ngắn sau mỗi câu.",
  },
  {
    label: "Luyện lỗi hay sai",
    value:
      "Mình hay quên động từ be trong câu bị động. Cho mình 7 câu luyện đúng lỗi đó, mức vừa.",
  },
  {
    label: "Từ vựng du lịch",
    value:
      "Mình muốn học từ vựng du lịch để nói ở sân bay và khách sạn. Tạo 6 câu trắc nghiệm mức dễ.",
  },
];

export function ChatWorkbench({ snapshot }: ChatWorkbenchProps) {
  const [screen, setScreen] = useState<Screen>("chat");
  const [prompt, setPrompt] = useState("");
  const [submittedPrompt, setSubmittedPrompt] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSessionHistoryItem[]>(
    [],
  );
  const [activeLocalSessionId, setActiveLocalSessionId] = useState<
    string | null
  >(null);
  const chatThreadRef = useRef<HTMLDivElement | null>(null);
  const chatMessagesRef = useRef<ChatMessage[]>([]);
  const chatSessionIdRef = useRef<string | null>(null);
  const activeLocalSessionIdRef = useRef<string | null>(null);
  const [preview, setPreview] = useState<ExercisePreview[]>(
    snapshot.exercisePreview,
  );
  const [plan, setPlan] = useState<PracticePlanPreview>(snapshot.planPreview);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [scoreResult, setScoreResult] = useState<ScoreResult | null>(null);
  const [status, setStatus] = useState("Sẵn sàng tạo bài luyện tập.");
  const [isScoring, setIsScoring] = useState(false);
  const [generationRunId, setGenerationRunId] = useState<string | null>(null);
  const [learnerDisplayName, setLearnerDisplayName] = useState(
    snapshot.profile.name,
  );
  const [learnerLevel, setLearnerLevel] = useState(snapshot.profile.level);
  const [isGuidedOnboarding, setIsGuidedOnboarding] = useState(false);
  const [onboardingStepIndex, setOnboardingStepIndex] = useState(0);
  const [onboardingAnswers, setOnboardingAnswers] = useState<
    Partial<OnboardingValues>
  >({});
  const [isOnboardingSaving, setIsOnboardingSaving] = useState(false);
  const [isCoachThinking, setIsCoachThinking] = useState(false);
  const [, startTransition] = useTransition();

  const answeredCount = useMemo(
    () => preview.filter((exercise) => answers[exercise.id]).length,
    [answers, preview],
  );
  const canSubmit = preview.length > 0 && answeredCount === preview.length;
  const showOnboardingShortcuts = true;
  const isComposerLocked = isOnboardingSaving || isCoachThinking;

  useEffect(() => {
    const storedSessions = loadStoredChatSessions();
    setChatSessions(storedSessions);
    const latestSession = storedSessions[0];
    if (latestSession) {
      activeLocalSessionIdRef.current = latestSession.id;
      chatMessagesRef.current = latestSession.messages;
      setActiveLocalSessionId(latestSession.id);
      setChatMessages(latestSession.messages);
    }
  }, []);

  useEffect(() => {
    const thread = chatThreadRef.current;
    if (!thread) {
      return;
    }
    thread.scrollTo({
      behavior: "smooth",
      top: thread.scrollHeight,
    });
  }, [chatMessages.length, prompt]);

  useEffect(() => {
    let isMounted = true;

    async function loadProfileAndChat() {
      try {
        const [personalization, chatResume, backendSessions] = await Promise.all([
          getPersonalizationSnapshot(USER_ID),
          getChatResume(USER_ID),
          listChatSessions(USER_ID).catch(() => []),
        ]);
        if (!isMounted) {
          return;
        }

        const displayName = normalizeDisplayNameForUi(
          personalization.displayName,
          USER_ID,
        );
        setLearnerDisplayName(displayName);
        setLearnerLevel(personalization.level);
        chatSessionIdRef.current = chatResume.sessionId;
        const history = mapPersistedChatMessages(chatResume);
        const storedSessions = loadStoredChatSessions();
        setChatSessions(
          saveStoredChatSessions(
            mergeBackendChatSessions(backendSessions, storedSessions),
          ),
        );
        const resumedLocalSessionId = chatResume.sessionId;

        if (!personalization.onboardingCompleted) {
          const rememberedAnswers = buildOnboardingAnswersFromMemory(
            personalization,
            chatResume,
          );
          const nextStepIndex = getNextOnboardingStepIndex(rememberedAnswers);
          if (nextStepIndex >= onboardingSteps.length) {
            const memoryIntro = chatResume.hasHistory
              ? `Mình đã mở lại cuộc trò chuyện trước đó. ${chatResume.suggestedNextQuestion}`
              : `Mình đã đọc hồ sơ của ${displayName}: level ${personalization.level}. Hôm nay bạn muốn luyện chủ đề nào?`;

            setIsGuidedOnboarding(false);
            setOnboardingStepIndex(0);
            setOnboardingAnswers({});
            setPrompt("");
            setSubmittedPrompt(null);
            activateChatSession(appendDistinctBotMessages(history, [memoryIntro]), {
              backendSessionId: chatResume.sessionId,
              localSessionId: resumedLocalSessionId,
            });
            return;
          }

          setIsGuidedOnboarding(true);
          setOnboardingStepIndex(nextStepIndex);
          setOnboardingAnswers(rememberedAnswers);
          setPrompt("");
          setSubmittedPrompt(null);
          activateChatSession(
            appendDistinctBotMessages(history, [
              buildConversationalOnboardingOpening(
                nextStepIndex,
                chatResume.hasHistory,
              ),
            ]),
            {
              backendSessionId: chatResume.sessionId,
              localSessionId: resumedLocalSessionId,
            },
          );
        } else {
          const memoryIntro = chatResume.hasHistory
            ? `Mình đã mở lại cuộc trò chuyện gần đây. ${chatResume.suggestedNextQuestion}`
            : `Mình đã đọc hồ sơ của ${displayName}: level ${personalization.level}. Bạn muốn luyện gì hôm nay?`;

          setIsGuidedOnboarding(false);
          setOnboardingStepIndex(0);
          setOnboardingAnswers({});
          setPrompt("");
          setSubmittedPrompt(null);
          activateChatSession(appendDistinctBotMessages(history, [memoryIntro]), {
            backendSessionId: chatResume.sessionId,
            localSessionId: resumedLocalSessionId,
          });
        }
      } catch {
        if (!isMounted) {
          return;
        }
        setIsGuidedOnboarding(true);
        setOnboardingStepIndex(0);
        setOnboardingAnswers({});
        setPrompt("");
        setSubmittedPrompt(null);
        activateChatSession(
          [
            buildConversationalOnboardingOpening(0, false),
          ].map((content) => makeMessage("bot", content)),
          {
            backendSessionId: null,
            localSessionId:
              activeLocalSessionIdRef.current || createLocalChatSessionId(),
          },
        );
      }
    }

    loadProfileAndChat();

    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function activateChatSession(
    messages: ChatMessage[],
    options: {
      backendSessionId?: string | null;
      localSessionId?: string | null;
    } = {},
  ) {
    const backendSessionId =
      options.backendSessionId === undefined
        ? chatSessionIdRef.current
        : options.backendSessionId;
    const nextLocalSessionId =
      options.localSessionId ||
      activeLocalSessionIdRef.current ||
      backendSessionId ||
      createLocalChatSessionId();

    activeLocalSessionIdRef.current = nextLocalSessionId;
    setActiveLocalSessionId(nextLocalSessionId);
    chatMessagesRef.current = messages;
    setChatMessages(messages);
    syncActiveChatSession(messages, {
      backendSessionId,
      localSessionId: nextLocalSessionId,
    });
  }

  function syncActiveChatSession(
    messages: ChatMessage[],
    options: {
      backendSessionId?: string | null;
      localSessionId?: string | null;
    } = {},
  ) {
    const localSessionId =
      options.localSessionId ||
      activeLocalSessionIdRef.current ||
      options.backendSessionId ||
      createLocalChatSessionId();

    if (!activeLocalSessionIdRef.current) {
      activeLocalSessionIdRef.current = localSessionId;
      setActiveLocalSessionId(localSessionId);
    }

    setChatSessions((currentSessions) =>
      saveStoredChatSessions(
        upsertChatSession(currentSessions, {
          id: localSessionId,
          backendSessionId:
            options.backendSessionId === undefined
              ? chatSessionIdRef.current
              : options.backendSessionId,
          messages,
        }),
      ),
    );
  }

  function attachBackendSessionIdToActiveSession(backendSessionId: string) {
    const localSessionId = activeLocalSessionIdRef.current;
    if (!localSessionId) {
      return;
    }

    setChatSessions((currentSessions) =>
      saveStoredChatSessions(
        currentSessions.map((session) =>
          session.id === localSessionId
            ? { ...session, backendSessionId }
            : session,
        ),
      ),
    );
  }

  async function handleSelectChatSession(sessionId: string) {
    const session = chatSessions.find((item) => item.id === sessionId);
    if (!session) {
      return;
    }

    activeLocalSessionIdRef.current = session.id;
    chatSessionIdRef.current = session.backendSessionId ?? null;
    chatMessagesRef.current = session.messages;
    setActiveLocalSessionId(session.id);
    setChatMessages(session.messages);
    setPrompt("");
    setSubmittedPrompt(null);
    setIsCoachThinking(false);
    setIsGuidedOnboarding(false);
    setScreen("chat");

    if (!session.backendSessionId) {
      return;
    }

    try {
      const chatResume = await getChatSession(USER_ID, session.backendSessionId);
      chatSessionIdRef.current = chatResume.sessionId;
      activateChatSession(mapPersistedChatMessages(chatResume), {
        backendSessionId: chatResume.sessionId,
        localSessionId: session.id,
      });
    } catch {
      // Cached chat history remains usable when the backend is unavailable.
    }
  }

  async function handleStartNewChatSession() {
    let backendSessionId: string | null = null;
    try {
      const chatResume = await createChatSession(USER_ID);
      backendSessionId = chatResume.sessionId;
    } catch {
      backendSessionId = null;
    }

    const openingMessage = makeMessage(
      "bot",
      "Mình mở một phiên mới rồi. Bạn muốn luyện gì ở phiên này?",
    );

    chatSessionIdRef.current = backendSessionId;
    setPrompt("");
    setSubmittedPrompt(null);
    setIsCoachThinking(false);
    setIsGuidedOnboarding(false);
    setOnboardingStepIndex(0);
    setOnboardingAnswers({});
    setScreen("chat");
    activateChatSession([openingMessage], {
      backendSessionId,
      localSessionId: backendSessionId ?? createLocalChatSessionId(),
    });
  }

  function startGuidedOnboarding(
    intro?: string,
    initialAnswers: Partial<OnboardingValues> = {},
    initialStepIndex = 0,
    shouldPersist = true,
  ) {
    setIsGuidedOnboarding(true);
    setOnboardingStepIndex(initialStepIndex);
    setOnboardingAnswers(initialAnswers);
    setPrompt("");
    setSubmittedPrompt(null);
    const opening = buildConversationalOnboardingOpening(
      initialStepIndex,
      false,
    );
    const botMessages = [
      intro ? `${intro} ${opening}` : opening,
    ];
    activateChatSession(botMessages.map((content) => makeMessage("bot", content)), {
      backendSessionId: chatSessionIdRef.current,
      localSessionId: createLocalChatSessionId(),
    });
    if (shouldPersist) {
      botMessages.forEach((content) => {
        void persistChatMessage(
          "bot",
          content,
          {
            phase: "onboarding",
            source: "guided_restart",
          },
          false,
        );
      });
    }
  }

  function appendChatMessage(
    role: ChatMessage["role"],
    content: string,
    metadata: Record<string, unknown> = {},
    updateMemory = role === "user",
  ) {
    const nextMessage = makeMessage(role, content);
    const nextMessages = [...chatMessagesRef.current, nextMessage];
    chatMessagesRef.current = nextMessages;
    setChatMessages(nextMessages);
    syncActiveChatSession(nextMessages);
    void persistChatMessage(role, content, metadata, updateMemory);
  }

  async function persistChatMessage(
    role: ChatMessage["role"],
    content: string,
    metadata: Record<string, unknown> = {},
    updateMemory = role === "user",
  ) {
    try {
      const saved = await saveChatMessage({
        userId: USER_ID,
        sessionId: chatSessionIdRef.current,
        role: role === "bot" ? "assistant" : "user",
        content,
        metadata,
        updateMemory,
      });
      chatSessionIdRef.current = saved.sessionId;
      attachBackendSessionIdToActiveSession(saved.sessionId);
    } catch {
      // Chat memory is helpful, but the practice flow should still work offline.
    }
  }

  async function handleGuidedOnboardingAnswer(message: string) {
    const step = onboardingSteps[onboardingStepIndex];
    setPrompt("");
    setIsOnboardingSaving(true);
    setIsCoachThinking(true);
    appendChatMessage("user", message, {
      phase: "onboarding",
      field: step.key,
    });

    const interpretation = await interpretOnboardingAnswerWithFallback(
      message,
      onboardingAnswers,
      step.key,
    );
    const nextAnswers = interpretation.answers;
    const nextStepIndex = getOnboardingStepIndexFromKey(
      interpretation.nextStepKey,
      nextAnswers,
    );

    setOnboardingAnswers(nextAnswers);

    if (nextStepIndex < onboardingSteps.length) {
      setOnboardingStepIndex(nextStepIndex);
      appendChatMessage(
        "bot",
        buildOnboardingCoachMessage(
          interpretation.assistantReply,
          interpretation.nextQuestion ||
            buildConversationalOnboardingQuestion(nextStepIndex, nextAnswers),
        ),
        {
          phase: "onboarding",
          field: step.key,
          nextField: onboardingSteps[nextStepIndex].key,
          action: "coach_followup",
          interpreter: interpretation.source,
        },
        false,
      );
      setIsOnboardingSaving(false);
      setIsCoachThinking(false);
      return;
    }

    appendChatMessage(
      "bot",
      interpretation.assistantReply,
      {
        phase: "onboarding",
        field: step.key,
        action: "acknowledge",
        interpreter: interpretation.source,
      },
      false,
    );
    appendChatMessage(
      "bot",
      "Ổn rồi, mình lưu lại các ý chính để lần sau không phải hỏi lại.",
      { phase: "onboarding", action: "save_profile" },
      false,
    );

    try {
      const values = completeOnboardingAnswers(nextAnswers);
      const savedProfile = await updateUserProfile({
        userId: USER_ID,
        displayName: values.displayName,
        level: values.level,
        goals: values.goals,
        weakTopics: values.weakTopics,
        preferredDifficulty: values.preferredDifficulty,
        preferredNumQuestions: values.preferredNumQuestions,
      });
      const savedDisplayName = normalizeDisplayNameForUi(
        savedProfile.display_name,
        USER_ID,
      );
      setLearnerDisplayName(savedDisplayName);
      setLearnerLevel(savedProfile.level);
      setStatus(
        "Đã lưu hồ sơ ban đầu. Bài tập tiếp theo sẽ được tinh chỉnh theo profile này.",
      );
      setIsGuidedOnboarding(false);
      appendChatMessage(
        "bot",
        `Xong rồi ${savedDisplayName || "bạn"}. Mình tạo luôn bài đầu tiên nhé: ${values.preferredNumQuestions} câu, mức ${formatDifficulty(values.preferredDifficulty)}, tập trung vào ${formatTopic(values.weakTopics[0] ?? "grammar")}.`,
        { phase: "onboarding", action: "completed" },
        false,
      );
      await wait(320);
      await handleGenerate(
        buildInitialPracticePrompt(values),
        {
          persistUserMessage: false,
          skipPracticeInterpretation: true,
          requestMetadata: {
            phase: "practice_request",
            source: "auto_after_onboarding",
          },
        },
      );
    } catch {
      appendChatMessage(
        "bot",
        "Mình chưa lưu được hồ sơ, có vẻ backend đang hơi khựng. Bạn thử gửi lại câu cuối giúp mình nhé.",
        { phase: "onboarding", action: "save_failed" },
        false,
      );
    } finally {
      setIsOnboardingSaving(false);
      setIsCoachThinking(false);
    }
  }

  const handleSubmitMessage = async (overrideMessage?: string) => {
    if (isComposerLocked) {
      return;
    }

    const message = (overrideMessage ?? prompt).trim();
    if (!message) {
      return;
    }

    if (isGuidedOnboarding) {
      await handleGuidedOnboardingAnswer(message);
      return;
    }

    await handleGenerate(message);
  };

  const handleGenerate = async (
    message: string,
    options: {
      persistUserMessage?: boolean;
      skipPracticeInterpretation?: boolean;
      requestMetadata?: Record<string, unknown>;
    } = {},
  ) => {
    if (options.persistUserMessage ?? true) {
      appendChatMessage("user", message, {
        phase: "practice_request",
        ...options.requestMetadata,
      });
    }

    setSubmittedPrompt(message);
    setPrompt("");
    setIsCoachThinking(true);

    let interpretedIntent: PracticeIntentFields | undefined;
    if (!options.skipPracticeInterpretation) {
      const interpretation = await interpretPracticeRequestWithFallback(message);
      if (interpretation.needsClarification) {
        appendChatMessage(
          "bot",
          interpretation.clarificationQuestion ||
            defaultPracticeClarificationQuestion(),
          {
            phase: "practice_clarification",
            interpreter: interpretation.source,
          },
          false,
        );
        setSubmittedPrompt(null);
        setScreen("chat");
        setIsCoachThinking(false);
        return;
      }
      interpretedIntent = interpretation.request;
    }

    await wait(260);

    setIsCoachThinking(false);
    setScreen("generating");
    setScoreResult(null);
    setAnswers({});
    setGenerationRunId(null);
    setStatus("Mình đang ghép bài theo đúng yêu cầu của bạn...");

    try {
      const response = await generatePractice({
        userId: USER_ID,
        message,
        intent: interpretedIntent,
      });

      startTransition(() => {
        setPreview(response.exercises);
        setPlan(response.plan);
      });
      setGenerationRunId(response.generationRunId);
      setStatus(
        `Đã sẵn sàng. ${
          response.recommendation ?? ""
        }`.trim(),
      );
      appendChatMessage(
        "bot",
        `Mình đã chuẩn bị ${response.exercises.length} câu về ${formatTopic(response.plan.topic)}${formatContentThemeSuffix(response.plan.contentTheme)}, mức ${formatDifficulty(response.plan.difficulty)}. Bạn làm thong thả, nộp xong mình sẽ chỉ ra phần nên luyện tiếp.`,
        {
          phase: "practice_generated",
          generationRunId: response.generationRunId,
          topic: response.plan.topic,
        },
        false,
      );
    } catch {
      const generated = buildPreviewFromPrompt(message);
      startTransition(() => {
        setPreview(generated.exercises);
        setPlan(generated.plan);
      });
      setGenerationRunId(null);
      setStatus("Backend chưa sẵn sàng, mình dùng bộ câu dự phòng trước.");
      appendChatMessage(
        "bot",
        "Backend đang chưa phản hồi ổn, nên mình dùng bộ câu dự phòng để bạn vẫn luyện được ngay. Khi backend chạy lại, bài sẽ được cá nhân hóa sâu hơn.",
        { phase: "practice_generated", fallback: true },
        false,
      );
    } finally {
      setIsCoachThinking(false);
      window.setTimeout(() => setScreen("practice"), 650);
    }
  };

  const handleScorePractice = async () => {
    setIsScoring(true);
    setStatus("Mình đang chấm và nhìn xem bạn hay vướng chỗ nào...");

    try {
      if (!generationRunId) {
        throw new Error("Missing persisted generation run.");
      }

      const response = await scorePractice({
        userId: USER_ID,
        generationRunId,
        answers: preview.map((exercise) => ({
          exerciseId: exercise.id,
          selectedAnswer: answers[exercise.id],
        })),
      });

      setScoreResult(response);
      setStatus("Chấm xong rồi. Mình đã cập nhật gợi ý luyện tiếp.");
      appendChatMessage(
        "bot",
        buildResultCoachMessage({
          correctCount: response.correctCount,
          recommendation:
            response.practiceReview?.summary ?? response.recommendation,
          score: response.score,
          totalQuestions: response.totalQuestions,
        }),
        {
          phase: "practice_result",
          generationRunId,
          sessionCode: response.sessionCode,
          topic: response.topic,
          score: response.score,
        },
        false,
      );
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
            ? "Nên luyện lại chủ đề này với độ khó thấp hơn một mức."
            : "Có thể tăng độ khó hoặc chuyển sang biến thể gần với chủ đề này.",
      });
      setStatus("Chấm xong bằng bộ dự phòng.");
      appendChatMessage(
        "bot",
        buildResultCoachMessage({
          correctCount,
          recommendation:
            score < 0.8
              ? "Mình nghĩ nên luyện lại chủ đề này với mức dễ hơn một chút."
              : "Bạn có thể tăng độ khó hoặc chuyển sang một biến thể gần với chủ đề này.",
          score,
          totalQuestions: preview.length,
        }),
        {
          phase: "practice_result",
          fallback: true,
          topic: plan.topic,
          score,
        },
        false,
      );
    } finally {
      setIsScoring(false);
      setScreen("result");
    }
  };

  const currentQuickReplies =
    onboardingSteps[onboardingStepIndex]?.quickReplies ?? [];

  return (
    <main className="flow-shell">
      <header className="flow-topbar">
        <div className="flow-heading">
          <p className="eyebrow">Adaptive English Tutor</p>
          <h1>Coach luyện tiếng Anh cá nhân</h1>
        </div>
        <div className="learner-pill">
          <span>{learnerDisplayName}</span>
          <strong>{learnerLevel}</strong>
          <button
            className="learner-pill__button"
            type="button"
            onClick={() =>
              startGuidedOnboarding(
                "Mình sẽ cập nhật hồ sơ theo kiểu trò chuyện nhẹ thôi. Bạn cứ kể tự nhiên, mình sẽ tự rút ra điều cần thiết để tạo bài phù hợp hơn.",
              )
            }
          >
            <EditOutlined />
            <span>Cập nhật hồ sơ</span>
          </button>
          <Link className="learner-pill__link" href="/personalization">
            <BarChartOutlined />
            <span>Cá nhân hóa</span>
          </Link>
          <Link className="learner-pill__link" href="/debug/chroma">
            <DatabaseOutlined />
            <span>RAG debug</span>
          </Link>
        </div>
      </header>

      {screen === "chat" ? (
        <div className="chat-workspace">
          <ChatSessionSidebar
            activeSessionId={activeLocalSessionId}
            sessions={chatSessions}
            onNewSession={handleStartNewChatSession}
            onSelectSession={handleSelectChatSession}
          />

          <section className="chat-screen">
            <div className="chat-panel-top">
              <div className="coach-presence">
                <span className="coach-presence__avatar" aria-hidden="true">
                  <RobotOutlined />
                </span>
                <div>
                  <strong>AI Coach</strong>
                  <span>
                    {isGuidedOnboarding
                      ? "Đang làm quen với bạn"
                      : "Sẵn sàng tạo bài luyện"}
                  </span>
                </div>
              </div>
              <span className="chat-session-pill">
                {chatMessages.length > 1 ? "Đã nối lại hội thoại" : "Phiên mới"}
              </span>
            </div>

            <div className="chat-thread" ref={chatThreadRef}>
              {chatMessages.map((message) => (
                <ChatMessageBubble key={message.id} message={message} />
              ))}
              {showOnboardingShortcuts &&
              isGuidedOnboarding &&
              currentQuickReplies.length > 0 ? (
                <div className="quick-replies" aria-label="Câu trả lời nhanh">
                  {currentQuickReplies.map((reply) => (
                    <button
                      disabled={isComposerLocked}
                      key={reply.label}
                      type="button"
                      onClick={() => {
                        void handleSubmitMessage(reply.value);
                      }}
                    >
                      {reply.label}
                    </button>
                  ))}
                </div>
              ) : null}
              {isCoachThinking ? <CoachTypingMessage /> : null}
            </div>

            <div className="chat-composer">
              {!submittedPrompt && !isGuidedOnboarding ? (
                <div className="composer-suggestions" aria-label="Gợi ý nhanh">
                  {promptSuggestions.map((suggestion) => (
                    <button
                      className="suggestion-chip"
                      key={suggestion.label}
                      type="button"
                      onClick={() => setPrompt(suggestion.value)}
                    >
                      {suggestion.label}
                    </button>
                  ))}
                </div>
              ) : null}

              <div className="composer-input-row">
                <textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void handleSubmitMessage();
                    }
                  }}
                  placeholder={
                    isGuidedOnboarding
                      ? "Trả lời tự nhiên thôi, không cần viết đúng format..."
                      : "Ví dụ: Tạo 10 câu ngữ pháp cơ bản mức dễ, giải thích ngắn."
                  }
                  rows={2}
                  disabled={isComposerLocked}
                />
                <button
                  className="button button--primary composer-send-button"
                  type="button"
                  onClick={() => {
                    void handleSubmitMessage();
                  }}
                  disabled={prompt.trim().length === 0 || isComposerLocked}
                >
                  <SendOutlined />
                  <span>{isGuidedOnboarding ? "Trả lời" : "Gửi"}</span>
                </button>
              </div>
            </div>
          </section>
        </div>
      ) : null}

      {screen === "generating" ? (
        <section className="generation-screen">
          <div className="generation-card">
            <p className="eyebrow">Đang chuẩn bị</p>
            <h2>Mình đang dựng bài luyện cho bạn</h2>
            <p className="muted">{status}</p>
            <Steps
              className="generation-steps generation-steps--antd"
              current={generationSteps.length - 1}
              direction="vertical"
              items={generationSteps.map((step, index) => ({
                title: step.title,
                description: step.description,
                icon:
                  index === generationSteps.length - 1 ? (
                    <LoadingOutlined />
                  ) : (
                    step.icon
                  ),
                status:
                  index === generationSteps.length - 1 ? "process" : "finish",
              }))}
            />
          </div>
        </section>
      ) : null}

      {screen === "practice" ? (
        <section className="test-screen">
          <div className="test-header">
            <div>
              <p className="eyebrow">Bài luyện</p>
              <h2>{formatTopic(plan.topic)}</h2>
              <p className="muted">
                {plan.difficulty} - {plan.exerciseType} - {status}
              </p>
            </div>
            <div className="progress-pill">
              {answeredCount}/{preview.length} câu
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
              onClick={() => {
                setPrompt(submittedPrompt ?? "");
                setSubmittedPrompt(null);
                setScreen("chat");
              }}
            >
              Sửa yêu cầu
            </button>
            <button
              className="button button--primary"
              type="button"
              onClick={handleScorePractice}
              disabled={!canSubmit || isScoring}
            >
              {isScoring ? "Đang chấm..." : "Nộp bài"}
            </button>
          </div>
        </section>
      ) : null}

      {screen === "result" && scoreResult ? (
        <section className="result-screen">
          <div className="score-summary">
            <p className="eyebrow">Kết quả</p>
            <strong>{Math.round(scoreResult.score * 100)}%</strong>
            <span>
              {scoreResult.correctCount}/{scoreResult.totalQuestions} câu đúng
            </span>
            <p>{scoreResult.recommendation}</p>
          </div>

          {scoreResult.answerDiagnoses?.some((item) => !item.isCorrect) ? (
            <section className="coach-review-card">
              <div className="coach-review-card__top">
                <div>
                  <p className="eyebrow">Error diagnosis</p>
                  <h3>Skill-level mistakes</h3>
                </div>
                <span>BKT input</span>
              </div>
              <div className="error-diagnosis-list">
                {scoreResult.answerDiagnoses
                  .filter((item) => !item.isCorrect)
                  .slice(0, 4)
                  .map((diagnosis) => (
                    <p key={diagnosis.exerciseId}>
                      <strong>{formatDiagnosisLabel(diagnosis.errorType)}</strong>
                      {" - "}
                      {formatDiagnosisLabel(
                        diagnosis.subtype ?? diagnosis.subtopic ?? diagnosis.skillId,
                      )}
                      {` (${Math.round(diagnosis.severity * 100)}%)`}
                    </p>
                  ))}
              </div>
            </section>
          ) : null}

          {scoreResult.practiceReview ? (
            <section className="coach-review-card">
              <div className="coach-review-card__top">
                <div>
                  <p className="eyebrow">Coach review</p>
                  <h3>Nhận xét sau bài làm</h3>
                </div>
                <span>{scoreResult.practiceReview.evaluator}</span>
              </div>
              <p>{scoreResult.practiceReview.summary}</p>
              <div className="coach-review-grid">
                <ReviewList
                  items={scoreResult.practiceReview.strengths}
                  title="Điểm đang ổn"
                />
                <ReviewList
                  items={scoreResult.practiceReview.weaknesses}
                  title="Điểm cần luyện"
                />
                <ReviewList
                  items={scoreResult.practiceReview.nextSteps}
                  title="Bước tiếp theo"
                />
              </div>
              {scoreResult.practiceReview.nextPracticePrompt ? (
                <button
                  className="coach-review-prompt"
                  type="button"
                  onClick={() => {
                    setPrompt(scoreResult.practiceReview?.nextPracticePrompt ?? "");
                    setScreen("chat");
                    setScoreResult(null);
                    setSubmittedPrompt(null);
                  }}
                >
                  Dùng gợi ý luyện tiếp:{" "}
                  {scoreResult.practiceReview.nextPracticePrompt}
                </button>
              ) : null}
            </section>
          ) : null}

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
                        Bạn chọn {selected}; đáp án đúng là{" "}
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
              Xem lại bài
            </button>
            <button
              className="button button--primary"
              type="button"
              onClick={() => {
                setScreen("chat");
                setScoreResult(null);
                setAnswers({});
                setSubmittedPrompt(null);
                setPrompt("");
                appendChatMessage(
                  "bot",
                  "Bạn muốn luyện tiếp theo hướng nào? Nếu nói “luyện tiếp”, mình sẽ dựa vào kết quả vừa rồi để chọn bài kế tiếp.",
                  { phase: "practice_prompt", source: "after_result" },
                  false,
                );
              }}
            >
              Tạo bài mới
            </button>
          </div>
        </section>
      ) : null}
    </main>
  );
}

function ChatSessionSidebar({
  activeSessionId,
  onNewSession,
  onSelectSession,
  sessions,
}: {
  activeSessionId: string | null;
  onNewSession: () => void | Promise<void>;
  onSelectSession: (sessionId: string) => void | Promise<void>;
  sessions: ChatSessionHistoryItem[];
}) {
  return (
    <aside className="chat-history-panel" aria-label="Lịch sử phiên chat">
      <div className="chat-history-panel__top">
        <div>
          <span>
            <HistoryOutlined />
          </span>
          <strong>Lịch sử chat</strong>
        </div>
        <p>{sessions.length} phiên đã lưu</p>
      </div>

      <button
        className="chat-history-new-button"
        type="button"
        onClick={() => {
          void onNewSession();
        }}
      >
        <PlusOutlined />
        <span>Phiên mới</span>
      </button>

      <div className="chat-session-list">
        {sessions.length > 0 ? (
          sessions.map((session) => (
            <button
              className={`chat-session-card${
                session.id === activeSessionId ? " chat-session-card--active" : ""
              }`}
              key={session.id}
              type="button"
              onClick={() => {
                void onSelectSession(session.id);
              }}
            >
              <span>{session.title}</span>
              <p>{session.preview}</p>
              <time dateTime={session.updatedAt}>
                {formatSessionTimestamp(session.updatedAt)}
              </time>
            </button>
          ))
        ) : (
          <p className="chat-history-empty">
            Chưa có phiên nào. Khi bạn bắt đầu chat, phiên sẽ hiện ở đây.
          </p>
        )}
      </div>
    </aside>
  );
}

function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const isBot = message.role === "bot";
  const displayTime = formatMessageTime(message.createdAt);

  return (
    <article className={`message-row message-row--${message.role}`}>
      <span className="message-avatar" aria-hidden="true">
        {isBot ? <RobotOutlined /> : <UserOutlined />}
      </span>
      <div className={`message message--${message.role}`}>
        <div className="message-meta">
          <span>{isBot ? "Coach" : "Bạn"}</span>
          {displayTime ? (
            <time dateTime={message.createdAt ?? undefined}>
              {displayTime}
            </time>
          ) : null}
        </div>
        <div className="message-content">
          {renderMessageContent(message.content)}
        </div>
      </div>
    </article>
  );
}

function CoachTypingMessage() {
  return (
    <article
      className="message-row message-row--bot message-row--thinking"
      aria-live="polite"
    >
      <span className="message-avatar" aria-hidden="true">
        <RobotOutlined />
      </span>
      <div className="message message--bot message--typing">
        <div className="message-meta">
          <span>Coach</span>
        </div>
        <div className="typing-dots" aria-label="Coach đang trả lời">
          <span />
          <span />
          <span />
        </div>
      </div>
    </article>
  );
}

function renderMessageContent(content: string) {
  const paragraphs = content
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  return paragraphs.map((paragraph, index) => (
    <p key={`${index}-${paragraph.slice(0, 12)}`}>{paragraph}</p>
  ));
}

function formatMessageTime(createdAt?: string | null) {
  if (!createdAt) {
    return "";
  }

  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function mergeBackendChatSessions(
  backendSessions: ChatSessionSummary[],
  storedSessions: ChatSessionHistoryItem[],
) {
  const usedStoredSessionIds = new Set<string>();
  const storedByBackendSessionId = new Map<string, ChatSessionHistoryItem>();
  const storedByLocalSessionId = new Map<string, ChatSessionHistoryItem>();

  storedSessions.forEach((session) => {
    storedByLocalSessionId.set(session.id, session);
    if (session.backendSessionId) {
      storedByBackendSessionId.set(session.backendSessionId, session);
    }
  });

  const backendItems = backendSessions.map((session) => {
    const storedSession =
      storedByBackendSessionId.get(session.sessionId) ||
      storedByLocalSessionId.get(session.sessionId);
    if (storedSession) {
      usedStoredSessionIds.add(storedSession.id);
    }

    const createdAt =
      session.createdAt || storedSession?.createdAt || new Date().toISOString();
    const updatedAt = session.updatedAt || storedSession?.updatedAt || createdAt;

    return {
      id: session.sessionId,
      backendSessionId: session.sessionId,
      title: session.title || storedSession?.title || "Phiên chat mới",
      preview:
        session.preview ||
        storedSession?.preview ||
        buildChatSessionPreview(storedSession?.messages ?? []),
      messageCount: session.messageCount || storedSession?.messageCount || 0,
      createdAt,
      updatedAt,
      messages: cloneChatMessages(storedSession?.messages ?? []),
    };
  });

  const localOnlyItems = storedSessions.filter(
    (session) =>
      !usedStoredSessionIds.has(session.id) &&
      !backendSessions.some(
        (backendSession) => backendSession.sessionId === session.backendSessionId,
      ),
  );

  return [...backendItems, ...localOnlyItems];
}

function loadStoredChatSessions(): ChatSessionHistoryItem[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const rawValue = window.localStorage.getItem(CHAT_SESSION_STORAGE_KEY);
    if (!rawValue) {
      return [];
    }

    const parsed = JSON.parse(rawValue) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .map(normalizeStoredChatSession)
      .filter((session): session is ChatSessionHistoryItem => Boolean(session))
      .sort((first, second) => sortSessionsByUpdatedAt(first, second))
      .slice(0, CHAT_SESSION_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

function saveStoredChatSessions(
  sessions: ChatSessionHistoryItem[],
): ChatSessionHistoryItem[] {
  const nextSessions = dedupeChatSessions(sessions)
    .sort((first, second) => sortSessionsByUpdatedAt(first, second))
    .slice(0, CHAT_SESSION_HISTORY_LIMIT);

  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(
        CHAT_SESSION_STORAGE_KEY,
        JSON.stringify(nextSessions),
      );
    } catch {
      // The chat still works if the browser refuses local storage.
    }
  }

  return nextSessions;
}

function upsertChatSession(
  currentSessions: ChatSessionHistoryItem[],
  session: {
    id: string;
    backendSessionId?: string | null;
    messages: ChatMessage[];
  },
) {
  const baseSessions = dedupeChatSessions([
    ...currentSessions,
    ...loadStoredChatSessions(),
  ]);
  const existingSession = baseSessions.find((item) => item.id === session.id);
  const messages = cloneChatMessages(session.messages);
  const now = new Date().toISOString();
  const createdAt =
    existingSession?.createdAt || getFirstMessageTimestamp(messages) || now;
  const updatedAt = getLastMessageTimestamp(messages) || now;
  const nextSession: ChatSessionHistoryItem = {
    id: session.id,
    backendSessionId:
      session.backendSessionId === undefined
        ? existingSession?.backendSessionId ?? null
        : session.backendSessionId,
    title: buildChatSessionTitle(messages),
    preview: buildChatSessionPreview(messages),
    messageCount: messages.length || existingSession?.messageCount || 0,
    createdAt,
    updatedAt,
    messages,
  };

  return [
    nextSession,
    ...baseSessions.filter(
      (item) =>
        item.id !== session.id &&
        (!session.backendSessionId ||
          item.backendSessionId !== session.backendSessionId),
    ),
  ];
}

function dedupeChatSessions(sessions: ChatSessionHistoryItem[]) {
  const seenIds = new Set<string>();
  const seenBackendSessionIds = new Set<string>();
  const result: ChatSessionHistoryItem[] = [];

  sessions.forEach((session) => {
    if (seenIds.has(session.id)) {
      return;
    }
    if (
      session.backendSessionId &&
      seenBackendSessionIds.has(session.backendSessionId)
    ) {
      return;
    }

    seenIds.add(session.id);
    if (session.backendSessionId) {
      seenBackendSessionIds.add(session.backendSessionId);
    }
    result.push(session);
  });

  return result;
}

function normalizeStoredChatSession(
  value: unknown,
): ChatSessionHistoryItem | null {
  if (!isRecord(value) || typeof value.id !== "string") {
    return null;
  }

  const rawMessages = Array.isArray(value.messages) ? value.messages : [];
  const messages = rawMessages
    .map(normalizeStoredChatMessage)
    .filter((message): message is ChatMessage => Boolean(message));

  const now = new Date().toISOString();
  const createdAt =
    typeof value.createdAt === "string"
      ? value.createdAt
      : getFirstMessageTimestamp(messages) || now;
  const updatedAt =
    typeof value.updatedAt === "string"
      ? value.updatedAt
      : getLastMessageTimestamp(messages) || createdAt;

  return {
    id: value.id,
    backendSessionId:
      typeof value.backendSessionId === "string"
        ? value.backendSessionId
        : null,
    title:
      typeof value.title === "string"
        ? value.title
        : buildChatSessionTitle(messages),
    preview:
      typeof value.preview === "string"
        ? value.preview
        : buildChatSessionPreview(messages),
    messageCount:
      typeof value.messageCount === "number" ? value.messageCount : messages.length,
    createdAt,
    updatedAt,
    messages,
  };
}

function normalizeStoredChatMessage(value: unknown): ChatMessage | null {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.content !== "string" ||
    (value.role !== "bot" && value.role !== "user")
  ) {
    return null;
  }

  return {
    id: value.id,
    role: value.role,
    content: value.content,
    createdAt: typeof value.createdAt === "string" ? value.createdAt : null,
  };
}

function buildChatSessionTitle(messages: ChatMessage[]) {
  const firstUserMessage = messages.find(
    (message) => message.role === "user" && message.content.trim(),
  );
  const firstMessage =
    firstUserMessage ?? messages.find((message) => message.content.trim());

  if (!firstMessage) {
    return "Phiên chat mới";
  }

  return truncateSessionText(firstMessage.content, 52);
}

function buildChatSessionPreview(messages: ChatMessage[]) {
  const lastMessage = getLastMeaningfulMessage(messages);
  if (!lastMessage) {
    return "Chưa có tin nhắn";
  }

  const speaker = lastMessage.role === "user" ? "Bạn: " : "Coach: ";
  return truncateSessionText(`${speaker}${lastMessage.content}`, 84);
}

function getLastMeaningfulMessage(messages: ChatMessage[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].content.trim()) {
      return messages[index];
    }
  }

  return null;
}

function truncateSessionText(value: string, maxLength: number) {
  const compactValue = value.replace(/\s+/g, " ").trim();
  if (compactValue.length <= maxLength) {
    return compactValue;
  }

  return `${compactValue.slice(0, Math.max(maxLength - 3, 1)).trim()}...`;
}

function formatSessionTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(date);
}

function getFirstMessageTimestamp(messages: ChatMessage[]) {
  return messages.find((message) => message.createdAt)?.createdAt ?? null;
}

function getLastMessageTimestamp(messages: ChatMessage[]) {
  return (
    [...messages].reverse().find((message) => message.createdAt)?.createdAt ??
    null
  );
}

function sortSessionsByUpdatedAt(
  first: ChatSessionHistoryItem,
  second: ChatSessionHistoryItem,
) {
  return getTimestampValue(second.updatedAt) - getTimestampValue(first.updatedAt);
}

function getTimestampValue(value: string) {
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function cloneChatMessages(messages: ChatMessage[]) {
  return messages.map((message) => ({ ...message }));
}

function createLocalChatSessionId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `local-chat-${crypto.randomUUID()}`;
  }

  return `local-chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function wait(milliseconds: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function makeMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    content,
    createdAt: new Date().toISOString(),
  };
}

function buildOnboardingAcknowledgement(
  key: OnboardingStepKey,
  answer: string,
) {
  if (key === "displayName") {
    return `Rất vui được đồng hành cùng ${parseDisplayName(answer) || "bạn"}.`;
  }
  if (key === "level") {
    return "Ổn, mình sẽ giữ nhịp vừa đủ để bạn không bị ngợp.";
  }
  if (key === "goals") {
    return "Mục tiêu rõ hơn rồi. Mình sẽ ưu tiên bài tập có ích cho hướng đó.";
  }
  if (key === "weakTopics") {
    return "Hay, biết điểm vướng là mình cá nhân hóa bài tốt hơn nhiều.";
  }
  if (key === "preferredDifficulty") {
    return "Được, mình sẽ bắt đầu ở mức đó và tăng/giảm theo kết quả của bạn.";
  }
  return "Mình ghi nhận số câu này để mỗi lượt luyện vừa sức hơn.";
}

function buildResultCoachMessage({
  correctCount,
  recommendation,
  score,
  totalQuestions,
}: {
  correctCount: number;
  recommendation: string;
  score: number;
  totalQuestions: number;
}) {
  const percent = Math.round(score * 100);
  const tone =
    score >= 0.8
      ? "Bài này ổn áp đấy."
      : score >= 0.5
        ? "Có nền rồi, nhưng vẫn còn vài chỗ đáng luyện thêm."
        : "Không sao, bài này đang chỉ ra đúng phần mình cần xử lý.";
  return `${tone} Bạn đúng ${correctCount}/${totalQuestions} câu (${percent}%). ${recommendation}`;
}

function mapPersistedChatMessages(resume: ChatMemoryResume): ChatMessage[] {
  return resume.messages.map((message) => ({
    id: message.messageId,
    role: message.role === "assistant" ? "bot" : "user",
    content: normalizePersistedChatContent(message.content),
    createdAt: message.createdAt,
  }));
}

function normalizePersistedChatContent(content: string) {
  const displayNamePrefix = "Rất vui được đồng hành cùng ";
  if (!content.startsWith(displayNamePrefix)) {
    return content;
  }

  const rawDisplayName = content
    .slice(displayNamePrefix.length)
    .replace(/[.!?。]+$/u, "")
    .trim();
  const displayName = parseDisplayName(rawDisplayName);
  return displayName ? `${displayNamePrefix}${displayName}.` : content;
}

function appendDistinctBotMessages(
  history: ChatMessage[],
  contents: Array<string | undefined>,
): ChatMessage[] {
  const nextMessages = [...history];
  contents
    .filter((content): content is string => Boolean(content))
    .forEach((content) => {
      const lastMessage = nextMessages.at(-1);
      if (lastMessage?.role === "bot" && lastMessage.content === content) {
        return;
      }
      nextMessages.push(makeMessage("bot", content));
    });
  return nextMessages;
}

function buildOnboardingAnswersFromMemory(
  personalization: PersonalizationSnapshot,
  resume: ChatMemoryResume,
): Partial<OnboardingValues> {
  const facts = resume.extractedFacts;
  const displayNameFact = getStringFact(facts, "display_name");
  const displayName = displayNameFact
    ? parseDisplayName(displayNameFact)
    : undefined;
  const level = getStringFact(facts, "level");
  const preferredDifficulty = getStringFact(facts, "preferred_difficulty");
  const preferredNumQuestions = getNumberFact(facts, "preferred_num_questions");
  const goals = getStringListFact(facts, "goals");
  const weakTopics = getStringListFact(facts, "weak_topics");
  const profileWeakTopics = personalization.topicStats
    .filter((item) => item.weaknessScore >= 0.7)
    .map((item) => item.topic);

  return {
    displayName:
      displayName ||
      (personalization.displayName !== USER_ID
        ? parseDisplayName(personalization.displayName)
        : undefined),
    level,
    goals: goals.length ? goals : personalization.goals,
    preferredDifficulty:
      preferredDifficulty || personalization.preferredDifficulty || undefined,
    preferredNumQuestions:
      preferredNumQuestions || personalization.preferredNumQuestions || undefined,
    weakTopics: weakTopics.length ? weakTopics : profileWeakTopics,
  };
}

function getNextOnboardingStepIndex(answers: Partial<OnboardingValues>) {
  const missingKey = onboardingSteps.findIndex((step) => {
    const value = answers[step.key];
    if (Array.isArray(value)) {
      return value.length === 0;
    }
    return value === undefined || value === "";
  });
  return missingKey === -1 ? onboardingSteps.length : missingKey;
}

function getStringFact(facts: Record<string, unknown>, key: string) {
  const value = facts[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function getNumberFact(facts: Record<string, unknown>, key: string) {
  const value = facts[key];
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function getStringListFact(facts: Record<string, unknown>, key: string) {
  const value = facts[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item).trim())
    .filter(Boolean);
}

async function interpretPracticeRequestWithFallback(
  message: string,
): Promise<PracticeInterpretationResult> {
  try {
    const response = await interpretPracticeRequest({
      userId: USER_ID,
      message,
    });
    return {
      request: response.request,
      assistantReply: response.assistantReply,
      needsClarification: response.needsClarification,
      clarificationQuestion: response.clarificationQuestion,
      source: response.source || "backend",
    };
  } catch {
    return buildPracticeIntentFallback(message);
  }
}

function buildPracticeIntentFallback(message: string): PracticeInterpretationResult {
  const normalized = normalizeText(message);
  const request: PracticeIntentFields = {};
  const topic = inferPracticeTopic(normalized);
  const targetSubtopic = inferPracticeSubtopic(normalized);
  const numQuestions = extractPracticeQuestionCount(normalized);
  const contentTheme = inferPracticeContentTheme(normalized);

  if (topic) {
    request.topic = topic;
    request.exerciseType = topic.includes("vocabulary")
      ? "vocabulary_mcq"
      : "grammar_mcq";
  }
  if (targetSubtopic) {
    request.targetSubtopic = targetSubtopic;
    request.topic = request.topic || "tenses";
    request.exerciseType = request.exerciseType || "grammar_mcq";
  }
  if (hasDifficultySignal(normalized)) {
    request.difficulty = parseDifficulty(message);
  }
  if (numQuestions) {
    request.numQuestions = numQuestions;
  }
  if (contentTheme) {
    request.contentTheme = contentTheme;
  }

  const hasFocus = Boolean(request.topic || request.targetSubtopic);
  const isContinueRequest = hasAnySignal(normalized, [
    "tiep tuc",
    "luyen tiep",
    "continue",
  ]);
  const shouldClarify = !hasFocus && !isContinueRequest;

  return {
    request,
    assistantReply: shouldClarify
      ? defaultPracticeClarificationQuestion()
      : "Mình sẽ dựa vào hồ sơ học của bạn để chọn bài phù hợp.",
    needsClarification: shouldClarify,
    clarificationQuestion: shouldClarify
      ? defaultPracticeClarificationQuestion()
      : null,
    source: "frontend-rule-fallback",
  };
}

function inferPracticeTopic(normalized: string) {
  if (hasAnySignal(normalized, ["travel", "du lich", "san bay", "khach san"])) {
    return "travel_vocabulary";
  }
  if (hasAnySignal(normalized, ["tu vung", "vocabulary", "vocab"])) {
    return "vocabulary";
  }
  if (hasAnySignal(normalized, ["passive", "bi dong"])) {
    return "passive_voice";
  }
  if (hasAnySignal(normalized, ["relative", "quan he"])) {
    return "relative_clause";
  }
  if (hasAnySignal(normalized, ["conditional", "dieu kien"])) {
    return "conditional_sentence";
  }
  if (hasAnySignal(normalized, ["reported", "gian tiep", "tuong thuat"])) {
    return "reported_speech";
  }
  if (hasAnySignal(normalized, ["preposition", "gioi tu"])) {
    return "prepositions";
  }
  if (
    hasAnySignal(normalized, [
      "grammar",
      "ngu phap",
      "tense",
      "thi",
      "qua khu",
      "hom qua",
      "yesterday",
      "last week",
      "tuan truoc",
      "last month",
      "thang truoc",
      "hien tai",
      "tuong lai",
    ])
  ) {
    return "tenses";
  }
  return undefined;
}

function inferPracticeContentTheme(normalized: string) {
  if (
    hasAnySignal(normalized, [
      "anime",
      "manga",
      "otaku",
      "anime character",
      "nhan vat anime",
      "chu de anime",
    ])
  ) {
    return "anime";
  }
  return undefined;
}

function inferPracticeSubtopic(normalized: string) {
  if (
    hasAnySignal(normalized, [
      "modal passive",
      "passive modal",
      "passive voice modal",
      "khuyet thieu bi dong",
      "dong tu khuyet thieu bi dong",
    ])
  ) {
    return "modal_passive";
  }
  if (hasAnySignal(normalized, ["past perfect"])) {
    return "past_perfect_sequence";
  }
  if (hasAnySignal(normalized, ["past continuous"])) {
    return "past_continuous_interrupted_action";
  }
  if (
    hasAnySignal(normalized, [
      "past tense",
      "past simple",
      "qua khu",
      "hom qua",
      "yesterday",
      "last week",
      "tuan truoc",
      "last month",
      "thang truoc",
    ])
  ) {
    return "past_simple_finished_time";
  }
  if (hasAnySignal(normalized, ["present perfect"])) {
    return "present_perfect_experience";
  }
  if (hasAnySignal(normalized, ["present continuous"])) {
    return "present_continuous_now";
  }
  if (hasAnySignal(normalized, ["present simple", "thi hien tai"])) {
    return "present_simple_habits";
  }
  if (hasAnySignal(normalized, ["future tense", "thi tuong lai", "tuong lai"])) {
    return "future_will_prediction";
  }
  return undefined;
}

function extractPracticeQuestionCount(normalized: string) {
  const match = normalized.match(/\b\d{1,2}\b/);
  if (!match) {
    return undefined;
  }
  return Math.max(1, Math.min(Number(match[0]), 20));
}

function defaultPracticeClarificationQuestion() {
  return "Mình chưa rõ bạn muốn luyện phần nào. Bạn nói rõ hơn một chút nhé: ngữ pháp, từ vựng, thì quá khứ, bị động hay giới từ?";
}

async function interpretOnboardingAnswerWithFallback(
  message: string,
  currentAnswers: Partial<OnboardingValues>,
  currentStepKey: OnboardingStepKey,
): Promise<OnboardingInterpretationResult> {
  try {
    const response = await interpretOnboardingAnswer({
      userId: USER_ID,
      message,
      currentAnswers: currentAnswers as Record<string, unknown>,
      currentStepKey,
    });
    const answers = normalizeOnboardingAnswersFromApi(response.answers);
    const nextStepKey = isOnboardingStepKey(response.next_step_key)
      ? response.next_step_key
      : onboardingSteps[getNextOnboardingStepIndex(answers)]?.key;
    return {
      answers,
      assistantReply:
        response.assistant_reply ||
        buildOnboardingAcknowledgement(currentStepKey, message),
      nextQuestion: response.next_question,
      nextStepKey,
      source: response.source || "backend",
    };
  } catch {
    if (currentStepKey === "level" && isUnclearLevelAnswer(message)) {
      return {
        answers: currentAnswers,
        assistantReply:
          "Không sao, bạn không cần tự dán nhãn trình độ ngay đâu.",
        nextQuestion: buildLevelDiagnosticQuestion(),
        nextStepKey: "level",
        source: "frontend-rule-clarify",
      };
    }

    const explicitAnswer = buildOnboardingAnswerPatch(
      currentStepKey,
      parseOnboardingAnswer(currentStepKey, message),
    );
    const inferredAnswers = extractOnboardingHints(message);
    const answers = mergeOnboardingAnswers(
      currentAnswers,
      inferredAnswers,
      explicitAnswer,
    );
    const nextStepIndex = getNextOnboardingStepIndex(answers);
    return {
      answers,
      assistantReply: buildOnboardingAcknowledgement(currentStepKey, message),
      nextQuestion: buildConversationalOnboardingQuestion(
        nextStepIndex,
        answers,
      ),
      nextStepKey: onboardingSteps[nextStepIndex]?.key,
      source: "frontend-rule-fallback",
    };
  }
}

function normalizeOnboardingAnswersFromApi(
  rawAnswers: Record<string, unknown>,
): Partial<OnboardingValues> {
  const normalized: Partial<OnboardingValues> = {};

  if (typeof rawAnswers.displayName === "string") {
    normalized.displayName = parseDisplayName(rawAnswers.displayName);
  }
  if (
    typeof rawAnswers.level === "string" &&
    ["beginner", "intermediate", "advanced"].includes(rawAnswers.level)
  ) {
    normalized.level = rawAnswers.level;
  }
  if (Array.isArray(rawAnswers.goals)) {
    normalized.goals = rawAnswers.goals
      .map((item) => String(item).trim())
      .filter(Boolean);
  }
  if (Array.isArray(rawAnswers.weakTopics)) {
    normalized.weakTopics = rawAnswers.weakTopics
      .map((item) => String(item).trim())
      .filter(Boolean);
  }
  if (
    typeof rawAnswers.preferredDifficulty === "string" &&
    ["easy", "medium", "hard"].includes(rawAnswers.preferredDifficulty)
  ) {
    normalized.preferredDifficulty = rawAnswers.preferredDifficulty;
  }
  const questionCount = Number(rawAnswers.preferredNumQuestions);
  if (Number.isFinite(questionCount)) {
    normalized.preferredNumQuestions = Math.max(
      1,
      Math.min(Math.round(questionCount), 20),
    );
  }

  return normalized;
}

function getOnboardingStepIndexFromKey(
  key: OnboardingStepKey | null | undefined,
  answers: Partial<OnboardingValues>,
) {
  const index = onboardingSteps.findIndex((step) => step.key === key);
  return index >= 0 ? index : getNextOnboardingStepIndex(answers);
}

function isOnboardingStepKey(value: unknown): value is OnboardingStepKey {
  return (
    typeof value === "string" &&
    onboardingSteps.some((step) => step.key === value)
  );
}

function isUnclearLevelAnswer(answer: string) {
  const normalized = normalizeText(answer);
  return hasAnySignal(normalized, [
    "khong ro",
    "ko ro",
    "k ro",
    "khong biet",
    "ko biet",
    "chua biet",
    "khong chac",
    "ko chac",
    "chua chac",
    "khao sat",
    "test thu",
    "kiem tra giup",
    "danh gia giup",
    "xem giup",
  ]);
}

function buildLevelDiagnosticQuestion() {
  return (
    "Bạn kể mình nghe theo cách đời thường là được: bạn đang học lại từ đầu, " +
    "đọc câu đơn giản tạm ổn nhưng hay sai, hay muốn luyện câu dài khó hơn? " +
    "Nếu vẫn chưa rõ, mình sẽ cho một bài khởi động ngắn để đo dần."
  );
}

function buildConversationalOnboardingOpening(
  nextStepIndex: number,
  hasHistory: boolean,
) {
  const prefix = hasHistory
    ? "Mình đã nhớ lại vài thông tin bạn từng chia sẻ, nên mình chỉ trò chuyện tiếp phần còn thiếu thôi."
    : "Mình sẽ không bắt bạn điền form đâu. Cứ trò chuyện tự nhiên, mình sẽ tự rút ra vài thông tin để tạo bài vừa sức hơn.";
  const question = buildConversationalOnboardingQuestion(nextStepIndex, {});
  return question ? `${prefix} ${question}` : prefix;
}

function buildOnboardingCoachMessage(
  assistantReply: string,
  nextQuestion?: string | null,
) {
  const reply = assistantReply.trim();
  const question = (nextQuestion || "").trim();
  if (!question) {
    return reply;
  }
  if (!reply) {
    return question;
  }
  if (reply.includes(question)) {
    return reply;
  }
  return `${reply} ${question}`;
}

function buildConversationalOnboardingQuestion(
  nextStepIndex: number,
  answers: Partial<OnboardingValues>,
) {
  const step = onboardingSteps[nextStepIndex];
  if (!step) {
    return undefined;
  }
  if (step.key === "displayName") {
    return "Trước hết mình làm quen nhẹ nha: mình nên gọi bạn là gì? Nickname cũng được.";
  }
  if (step.key === "level") {
    return "Về trình độ thì bạn không cần tự gắn nhãn. Bạn kể mình nghe hiện tại bạn đọc câu đơn giản có ổn không, hay đang học lại từ đầu?";
  }
  if (step.key === "goals") {
    const name = answers.displayName || "bạn";
    return `${name} muốn dùng tiếng Anh vào việc gì nhiều nhất lúc này: nói chuyện, đi học/đi thi, công việc, hay chỉ muốn lấy lại căn bản?`;
  }
  if (step.key === "weakTopics") {
    return "Khi học tiếng Anh, phần nào hay làm bạn đứng lại nhất? Nếu chưa biết, cứ nói “mình chưa rõ”, mình sẽ cho bài khởi động để đo dần.";
  }
  if (step.key === "preferredDifficulty") {
    return "Để bắt đầu cho đỡ ngợp, mình có thể tạo bài nhẹ trước rồi tăng dần. Bạn muốn đi chậm chắc hay thử thách hơn một chút?";
  }
  return "Mỗi lượt mình nên tạo khoảng bao nhiêu câu để bạn thấy vừa sức? Nếu chưa rõ, mình sẽ mặc định 5 câu trước.";
}

function buildOnboardingAnswerPatch(
  key: OnboardingStepKey,
  value: OnboardingValues[OnboardingStepKey],
): Partial<OnboardingValues> {
  if (key === "displayName") {
    return { displayName: String(value).trim() };
  }
  if (key === "level") {
    return { level: String(value) };
  }
  if (key === "goals") {
    return { goals: Array.isArray(value) ? value : [] };
  }
  if (key === "weakTopics") {
    return { weakTopics: Array.isArray(value) ? value : [] };
  }
  if (key === "preferredDifficulty") {
    return { preferredDifficulty: String(value) };
  }
  return {
    preferredNumQuestions:
      typeof value === "number" && Number.isFinite(value) ? value : 5,
  };
}

function mergeOnboardingAnswers(
  current: Partial<OnboardingValues>,
  ...patches: Partial<OnboardingValues>[]
): Partial<OnboardingValues> {
  const next: Partial<OnboardingValues> = { ...current };

  patches.forEach((patch) => {
    if (typeof patch.displayName === "string" && patch.displayName.trim()) {
      next.displayName = patch.displayName.trim();
    }
    if (typeof patch.level === "string" && patch.level.trim()) {
      next.level = patch.level;
    }
    if (Array.isArray(patch.goals) && patch.goals.length) {
      next.goals = mergeUniqueStrings(next.goals, patch.goals);
    }
    if (
      typeof patch.preferredDifficulty === "string" &&
      patch.preferredDifficulty.trim()
    ) {
      next.preferredDifficulty = patch.preferredDifficulty;
    }
    if (
      typeof patch.preferredNumQuestions === "number" &&
      Number.isFinite(patch.preferredNumQuestions)
    ) {
      next.preferredNumQuestions = patch.preferredNumQuestions;
    }
    if (Array.isArray(patch.weakTopics) && patch.weakTopics.length) {
      next.weakTopics = mergeUniqueStrings(next.weakTopics, patch.weakTopics);
    }
  });

  return next;
}

function mergeUniqueStrings(current: string[] | undefined, incoming: string[]) {
  return [...new Set([...(current ?? []), ...incoming])];
}

function extractOnboardingHints(answer: string): Partial<OnboardingValues> {
  const normalized = normalizeText(answer);
  const hints: Partial<OnboardingValues> = {};

  if (hasLevelSignal(normalized)) {
    hints.level = parseLevel(answer);
  }
  if (hasGoalSignal(normalized)) {
    hints.goals = parseGoals(answer);
  }
  if (hasWeakTopicSignal(normalized)) {
    hints.weakTopics = parseWeakTopics(answer);
  }
  if (hasDifficultySignal(normalized)) {
    hints.preferredDifficulty = parseDifficulty(answer);
  }
  if (hasQuestionCountSignal(normalized)) {
    hints.preferredNumQuestions = parseQuestionCount(answer);
  }

  return hints;
}

function hasLevelSignal(normalized: string) {
  return (
    hasAnySignal(normalized, [
      "beginner",
      "intermediate",
      "advanced",
      "moi hoc",
      "mat goc",
      "so cap",
    ]) || /\b[abc][12]\b/.test(normalized)
  );
}

function hasGoalSignal(normalized: string) {
  return hasAnySignal(normalized, [
    "giao tiep",
    "toeic",
    "ielts",
    "kiem tra",
    "on thi",
    "thi toeic",
    "thi ielts",
    "ngu phap",
    "grammar",
    "tu vung",
    "vocabulary",
    "du lich",
    "travel",
  ]);
}

function hasWeakTopicSignal(normalized: string) {
  return (
    hasAnySignal(normalized, [
      "passive",
      "bi dong",
      "relative",
      "quan he",
      "conditional",
      "dieu kien",
      "reported",
      "gian tiep",
      "preposition",
      "gioi tu",
      "du lich",
      "travel",
      "tu vung",
      "vocabulary",
      "ngu phap",
      "grammar",
    ]) || hasTenseSignal(normalized)
  );
}

function hasDifficultySignal(normalized: string) {
  return hasAnySignal(normalized, [
    "easy",
    "co ban",
    "nhe",
    "muc de",
    "cau de",
    "medium",
    "trung binh",
    "vua",
    "hard",
    "kho",
    "thu thach",
    "nang cao",
  ]);
}

function hasQuestionCountSignal(normalized: string) {
  return /\b\d{1,2}\b/.test(normalized);
}

function hasTenseSignal(normalized: string) {
  return (
    normalized === "thi" ||
    hasAnySignal(normalized, [
      "tense",
      "tenses",
      "cac thi",
      "chia thi",
      "thi dong tu",
    ])
  );
}

function hasAnySignal(normalized: string, signals: string[]) {
  return signals.some((signal) =>
    new RegExp(`(?<!\\w)${escapeRegExp(signal)}(?!\\w)`).test(normalized),
  );
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeDisplayNameForUi(value: string | undefined, fallback: string) {
  const displayName = value ? parseDisplayName(value) : "";
  return displayName || fallback;
}

function parseDisplayName(answer: string) {
  const trimmed = answer.trim();
  if (!trimmed) {
    return "";
  }

  const patterns = [
    /(?:^|[\s,.;!?])(?:cứ\s+)?(?:gọi|goi)\s+(?:(?:mình|minh|tôi|toi|em|anh|chị|chi|bạn|ban)\s+)?(?:là|la)\s+(.+)$/iu,
    /(?:^|[\s,.;!?])(?:tên|ten)\s+(?:(?:mình|minh|tôi|toi|em|anh|chị|chi|bạn|ban)\s+)?(?:là|la)?\s*(.+)$/iu,
    /(?:^|[\s,.;!?])(?:mình|minh|tôi|toi|em|anh|chị|chi)\s+(?:là|la)\s+(.+)$/iu,
    /(?:^|[\s,.;!?])(?:call me|my name is|i am|i'm)\s+(.+)$/iu,
  ];

  for (const pattern of patterns) {
    const match = trimmed.match(pattern);
    if (!match?.[1]) {
      continue;
    }
    const candidate = cleanupDisplayNameCandidate(match[1]);
    if (isUsableDisplayName(candidate)) {
      return toDisplayNameCase(candidate);
    }
  }

  const candidate = cleanupDisplayNameCandidate(trimmed);
  return isUsableDisplayName(candidate) ? toDisplayNameCase(candidate) : "";
}

function cleanupDisplayNameCandidate(value: string) {
  let candidate = value.split(/[,.;!?\n]/, 1)[0]?.trim() ?? "";
  candidate = candidate
    .replace(/^(?:là|la)\s+/iu, "")
    .replace(
      /\s+(?:cũng được|cung duoc|được|duoc|đi|di|nhé|nhe|nha|ạ|a|ha|với|voi|thôi|thoi)$/iu,
      "",
    )
    .trim();
  return candidate.replace(/\s+/g, " ").slice(0, 40);
}

function isUsableDisplayName(candidate: string) {
  const normalized = normalizeText(candidate);
  const wordCount = candidate.split(/\s+/).filter(Boolean).length;
  return (
    Boolean(candidate) &&
    wordCount <= 6 &&
    ![
      "beginner",
      "intermediate",
      "advanced",
      "easy",
      "medium",
      "hard",
      "co ban",
      "khong biet",
      "chua biet",
    ].includes(normalized)
  );
}

function toDisplayNameCase(value: string) {
  return value
    .split(" ")
    .map((part) =>
      part ? `${part.charAt(0).toLocaleUpperCase("vi-VN")}${part.slice(1)}` : part,
    )
    .join(" ");
}

function parseOnboardingAnswer(
  key: OnboardingStepKey,
  answer: string,
): OnboardingValues[OnboardingStepKey] {
  if (key === "displayName") {
    return parseDisplayName(answer);
  }
  if (key === "level") {
    return parseLevel(answer);
  }
  if (key === "goals") {
    return parseGoals(answer);
  }
  if (key === "weakTopics") {
    return parseWeakTopics(answer);
  }
  if (key === "preferredDifficulty") {
    return parseDifficulty(answer);
  }
  return parseQuestionCount(answer);
}

function completeOnboardingAnswers(
  answers: Partial<OnboardingValues>,
): OnboardingValues {
  return {
    displayName: answers.displayName || USER_ID,
    level: answers.level || "beginner",
    goals: answers.goals?.length ? answers.goals : ["grammar_foundation"],
    preferredDifficulty: answers.preferredDifficulty || "easy",
    preferredNumQuestions: answers.preferredNumQuestions || 5,
    weakTopics: answers.weakTopics?.length
      ? answers.weakTopics
      : ["passive_voice"],
  };
}

function buildInitialPracticePrompt(values: OnboardingValues) {
  const topic = values.weakTopics[0] ?? "grammar";
  const topicText = formatTopic(topic);
  const goalText = values.goals.length
    ? ` Mục tiêu của tôi: ${values.goals.join(", ")}.`
    : "";
  return `Luyện tiếp theo profile. Tạo ${values.preferredNumQuestions} câu trắc nghiệm về ${topicText} mức ${values.preferredDifficulty}. Tôi là ${values.level}.${goalText}`;
}

function parseLevel(answer: string) {
  const normalized = normalizeText(answer);
  if (
    /\bc[12]\b/.test(normalized) ||
    normalized.includes("advanced") ||
    normalized.includes("nang cao")
  ) {
    return "advanced";
  }
  if (
    /\bb[12]\b/.test(normalized) ||
    normalized.includes("intermediate") ||
    normalized.includes("trung binh") ||
    normalized.includes("vua")
  ) {
    return "intermediate";
  }
  return "beginner";
}

function parseDifficulty(answer: string) {
  const normalized = normalizeText(answer);
  if (
    hasAnySignal(normalized, ["hard", "kho", "thu thach", "nang cao"])
  ) {
    return "hard";
  }
  if (hasAnySignal(normalized, ["medium", "trung binh", "vua"])) {
    return "medium";
  }
  return "easy";
}

function parseQuestionCount(answer: string) {
  const match = normalizeText(answer).match(/\d{1,2}/);
  if (!match) {
    return 5;
  }
  return Math.max(1, Math.min(Number(match[0]), 20));
}

function parseGoals(answer: string) {
  const normalized = normalizeText(answer);
  const goals: string[] = [];
  if (normalized.includes("giao tiep")) {
    goals.push("daily_communication");
  }
  if (
    normalized.includes("toeic") ||
    normalized.includes("ielts") ||
    normalized.includes("on thi") ||
    normalized.includes("thi toeic") ||
    normalized.includes("thi ielts") ||
    normalized.includes("kiem tra")
  ) {
    goals.push("exam_preparation");
  }
  if (normalized.includes("ngu phap") || normalized.includes("grammar")) {
    goals.push("grammar_foundation");
  }
  if (normalized.includes("tu vung") || normalized.includes("vocabulary")) {
    goals.push("topic_vocabulary");
  }
  if (normalized.includes("du lich") || normalized.includes("travel")) {
    goals.push("travel_english");
  }
  return goals.length ? goals : splitFreeformList(answer);
}

function parseWeakTopics(answer: string) {
  const normalized = normalizeText(answer);
  const topics: string[] = [];
  if (normalized.includes("passive") || normalized.includes("bi dong")) {
    topics.push("passive_voice");
  }
  if (normalized.includes("relative") || normalized.includes("quan he")) {
    topics.push("relative_clause");
  }
  if (normalized.includes("conditional") || normalized.includes("dieu kien")) {
    topics.push("conditional_sentence");
  }
  if (normalized.includes("reported") || normalized.includes("gian tiep")) {
    topics.push("reported_speech");
  }
  if (
    hasTenseSignal(normalized) ||
    normalized.includes("ngu phap") ||
    normalized.includes("grammar")
  ) {
    topics.push("tenses");
  }
  if (normalized.includes("preposition") || normalized.includes("gioi tu")) {
    topics.push("prepositions");
  }
  if (normalized.includes("du lich") || normalized.includes("travel")) {
    topics.push("travel_vocabulary");
  } else if (
    normalized.includes("tu vung") ||
    normalized.includes("vocabulary")
  ) {
    topics.push("vocabulary");
  }
  return topics.length ? [...new Set(topics)] : splitFreeformList(answer);
}

function splitFreeformList(answer: string) {
  return answer
    .split(/[,;|]/)
    .map((item) => normalizeText(item).replaceAll(" ", "_"))
    .filter(Boolean);
}

function normalizeText(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll("\u0111", "d")
    .replaceAll("\u0110", "D")
    .toLowerCase()
    .trim();
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
          placeholder="Nhập câu trả lời"
        />
      )}
    </article>
  );
}

function ReviewList({
  items,
  title,
}: {
  items: string[];
  title: string;
}) {
  return (
    <div className="coach-review-list">
      <strong>{title}</strong>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function formatTopic(topic: string) {
  return topic.replaceAll("_", " ");
}

function formatDiagnosisLabel(value: string) {
  return value.replaceAll(".", " ").replaceAll("_", " ");
}

function formatDifficulty(difficulty: string) {
  const labels: Record<string, string> = {
    easy: "dễ",
    hard: "khó",
    medium: "vừa",
  };
  return labels[difficulty] ?? difficulty;
}

function formatContentThemeSuffix(contentTheme?: string | null) {
  if (!contentTheme) {
    return "";
  }
  const labels: Record<string, string> = {
    anime: " theo chủ đề anime",
  };
  return labels[contentTheme] ?? ` theo chủ đề ${contentTheme}`;
}

function buildPreviewFromPrompt(prompt: string): {
  exercises: ExercisePreview[];
  plan: PracticePlanPreview;
} {
  const normalized = normalizeText(prompt);
  const contentTheme = inferPracticeContentTheme(normalized);
  const topic = normalized.includes("passive") || normalized.includes("bi dong")
    ? "passive_voice"
    : normalized.includes("travel") || normalized.includes("du lich")
      ? "travel_vocabulary"
      : normalized.includes("vocabulary") || normalized.includes("tu vung")
        ? "vocabulary"
      : normalized.includes("preposition") || normalized.includes("gioi tu")
        ? "prepositions"
        : normalized.includes("relative") || normalized.includes("quan he")
          ? "relative_clause"
          : normalized.includes("conditional") || normalized.includes("dieu kien")
            ? "conditional_sentence"
            : "tenses";
  const difficulty = normalized.includes("hard")
    ? "hard"
    : normalized.includes("easy") ||
        normalized.includes("co ban") ||
        normalized.includes("de")
      ? "easy"
      : "medium";
  const numQuestions = parseFallbackQuestionCount(normalized);
  const exerciseType = topic.includes("vocabulary")
    ? "vocabulary_mcq"
    : "grammar_mcq";
  const exercises = Array.from({ length: numQuestions }, (_, index) =>
    buildFallbackExercise({
      difficulty,
      exerciseType,
      index: index + 1,
      topic,
      contentTheme,
    }),
  );

  return {
    plan: {
      topic,
      difficulty,
      exerciseType,
      numQuestions,
      focusReason: "Fallback plan from frontend.",
      contentTheme,
    },
    exercises,
  };
}

function parseFallbackQuestionCount(normalizedPrompt: string) {
  const match = normalizedPrompt.match(
    /\b(\d{1,2})\s*(?:cau|questions?|bai|exercises?)?\b/,
  );
  if (!match) {
    return 5;
  }
  return Math.max(1, Math.min(Number(match[1]), 20));
}

function buildFallbackExercise({
  difficulty,
  exerciseType,
  index,
  topic,
  contentTheme,
}: {
  difficulty: string;
  exerciseType: string;
  index: number;
  topic: string;
  contentTheme?: string;
}): ExercisePreview {
  const isVocabulary = exerciseType === "vocabulary_mcq";
  const templates = isVocabulary
    ? fallbackVocabularyTemplates
    : contentTheme === "anime"
      ? fallbackAnimeGrammarTemplates
      : fallbackGrammarTemplates;
  const template = templates[(index - 1) % templates.length];
  return {
    id: `fallback-${index}`,
    type: exerciseType,
    topic,
    difficulty,
    skill: isVocabulary ? "vocabulary" : "grammar",
    subtopic: template.subtopic,
    errorTag: template.errorTag,
    question: template.question,
    options: template.options.map((option) => ({
      ...option,
      isCorrect: option.label === template.correctAnswer,
    })),
    correctAnswer: template.correctAnswer,
    explanation: template.explanation,
    sourceChunkIds: [],
  };
}

const fallbackGrammarTemplates = [
  {
    question: "Choose the correct sentence.",
    options: [
      { label: "A", text: "She goes to school every day." },
      { label: "B", text: "She go to school every day." },
      { label: "C", text: "She going to school every day." },
      { label: "D", text: "She gone to school every day." },
    ],
    correctAnswer: "A",
    explanation: "With the subject `she`, present simple uses `goes`.",
    subtopic: "present_simple",
    errorTag: "subject_verb_agreement",
  },
  {
    question: "Complete the sentence: I ___ coffee in the morning.",
    options: [
      { label: "A", text: "drink" },
      { label: "B", text: "drinks" },
      { label: "C", text: "drinking" },
      { label: "D", text: "drank" },
    ],
    correctAnswer: "A",
    explanation: "With `I`, present simple uses the base verb `drink`.",
    subtopic: "present_simple",
    errorTag: "verb_form",
  },
  {
    question: "Choose the correct question.",
    options: [
      { label: "A", text: "Do you like English?" },
      { label: "B", text: "Does you like English?" },
      { label: "C", text: "Are you like English?" },
      { label: "D", text: "You like English?" },
    ],
    correctAnswer: "A",
    explanation: "Use `Do + subject + base verb` for present simple questions.",
    subtopic: "present_simple_questions",
    errorTag: "auxiliary_do",
  },
  {
    question: "Complete the sentence: They ___ at home yesterday.",
    options: [
      { label: "A", text: "were" },
      { label: "B", text: "was" },
      { label: "C", text: "are" },
      { label: "D", text: "is" },
    ],
    correctAnswer: "A",
    explanation: "`They` takes `were` in the past simple of `be`.",
    subtopic: "past_simple",
    errorTag: "be_verb_past",
  },
  {
    question: "Choose the correct article: I saw ___ apple on the table.",
    options: [
      { label: "A", text: "an" },
      { label: "B", text: "a" },
      { label: "C", text: "the a" },
      { label: "D", text: "no article" },
    ],
    correctAnswer: "A",
    explanation: "Use `an` before a vowel sound, as in `apple`.",
    subtopic: "articles",
    errorTag: "article_choice",
  },
  {
    question: "Complete the sentence: My book is ___ the bag.",
    options: [
      { label: "A", text: "in" },
      { label: "B", text: "on" },
      { label: "C", text: "at" },
      { label: "D", text: "to" },
    ],
    correctAnswer: "A",
    explanation: "`In` means inside something, so `in the bag` is correct.",
    subtopic: "prepositions",
    errorTag: "preposition_place",
  },
  {
    question: "Choose the correct form: This test is ___ than the last one.",
    options: [
      { label: "A", text: "easier" },
      { label: "B", text: "easy" },
      { label: "C", text: "easiest" },
      { label: "D", text: "more easy" },
    ],
    correctAnswer: "A",
    explanation: "Use the comparative form `easier` with `than`.",
    subtopic: "comparatives",
    errorTag: "comparative_form",
  },
  {
    question: "Complete the sentence: He can ___ very fast.",
    options: [
      { label: "A", text: "run" },
      { label: "B", text: "runs" },
      { label: "C", text: "running" },
      { label: "D", text: "ran" },
    ],
    correctAnswer: "A",
    explanation: "After modal verbs like `can`, use the base verb.",
    subtopic: "modals",
    errorTag: "modal_base_verb",
  },
  {
    question: "Choose the correct sentence.",
    options: [
      { label: "A", text: "There are two chairs in the room." },
      { label: "B", text: "There is two chairs in the room." },
      { label: "C", text: "There be two chairs in the room." },
      { label: "D", text: "There am two chairs in the room." },
    ],
    correctAnswer: "A",
    explanation: "Use `there are` with plural nouns like `two chairs`.",
    subtopic: "there_is_are",
    errorTag: "plural_agreement",
  },
  {
    question: "Complete the sentence: We ___ TV now.",
    options: [
      { label: "A", text: "are watching" },
      { label: "B", text: "watch" },
      { label: "C", text: "watches" },
      { label: "D", text: "watched" },
    ],
    correctAnswer: "A",
    explanation: "`Now` often signals present continuous: `are watching`.",
    subtopic: "present_continuous",
    errorTag: "continuous_form",
  },
];

const fallbackAnimeGrammarTemplates = [
  {
    question: "Complete the sentence: The next episode should ___ by new fans first.",
    options: [
      { label: "A", text: "be watched" },
      { label: "B", text: "watch" },
      { label: "C", text: "watched" },
      { label: "D", text: "be watch" },
    ],
    correctAnswer: "A",
    explanation: "Modal passive uses modal + be + past participle: should be watched.",
    subtopic: "modal_passive",
    errorTag: "missing_be",
  },
  {
    question: "Choose the correct passive sentence.",
    options: [
      { label: "A", text: "The opening song was performed by a new band." },
      { label: "B", text: "The opening song performed by a new band." },
      { label: "C", text: "The opening song was perform by a new band." },
      { label: "D", text: "The opening song is performing by a new band." },
    ],
    correctAnswer: "A",
    explanation: "Past passive uses was/were + past participle.",
    subtopic: "past_simple_passive",
    errorTag: "wrong_verb_form",
  },
  {
    question: "Complete the sentence: Spoilers must ___ before the review is posted.",
    options: [
      { label: "A", text: "be hidden" },
      { label: "B", text: "hide" },
      { label: "C", text: "hidden" },
      { label: "D", text: "be hide" },
    ],
    correctAnswer: "A",
    explanation: "`Must be hidden` is modal passive: must + be + past participle.",
    subtopic: "modal_passive",
    errorTag: "missing_be",
  },
  {
    question: "Choose the correct sentence.",
    options: [
      { label: "A", text: "The manga chapter has been translated into English." },
      { label: "B", text: "The manga chapter has translated into English." },
      { label: "C", text: "The manga chapter is translated yesterday." },
      { label: "D", text: "The manga chapter have been translate into English." },
    ],
    correctAnswer: "A",
    explanation: "Present perfect passive uses has/have been + past participle.",
    subtopic: "present_perfect_passive",
    errorTag: "missing_been",
  },
  {
    question: "Complete the sentence: The character design can ___ after feedback.",
    options: [
      { label: "A", text: "be improved" },
      { label: "B", text: "improved" },
      { label: "C", text: "be improve" },
      { label: "D", text: "improving" },
    ],
    correctAnswer: "A",
    explanation: "`Can be improved` follows modal + be + past participle.",
    subtopic: "modal_passive",
    errorTag: "wrong_verb_form",
  },
];

const fallbackVocabularyTemplates = [
  {
    question: "Choose the word that means `a person who travels by plane, bus, or train`.",
    options: [
      { label: "A", text: "passenger" },
      { label: "B", text: "platform" },
      { label: "C", text: "receipt" },
      { label: "D", text: "luggage" },
    ],
    correctAnswer: "A",
    explanation: "`Passenger` means a person who travels in a vehicle.",
    subtopic: "basic_vocabulary",
    errorTag: "vocabulary_meaning_confusion",
  },
  {
    question: "Choose the best meaning of `luggage`.",
    options: [
      { label: "A", text: "bags and suitcases" },
      { label: "B", text: "a travel ticket" },
      { label: "C", text: "a hotel room" },
      { label: "D", text: "a bus stop" },
    ],
    correctAnswer: "A",
    explanation: "`Luggage` means bags and suitcases used when travelling.",
    subtopic: "basic_vocabulary",
    errorTag: "vocabulary_meaning_confusion",
  },
  {
    question: "Complete the sentence: I need to ___ a room for two nights.",
    options: [
      { label: "A", text: "book" },
      { label: "B", text: "borrow" },
      { label: "C", text: "break" },
      { label: "D", text: "build" },
    ],
    correctAnswer: "A",
    explanation: "`Book a room` means reserve a room.",
    subtopic: "travel_vocabulary",
    errorTag: "vocabulary_context_error",
  },
  {
    question: "Which word means `the place where you get on a train`?",
    options: [
      { label: "A", text: "platform" },
      { label: "B", text: "passport" },
      { label: "C", text: "pillow" },
      { label: "D", text: "payment" },
    ],
    correctAnswer: "A",
    explanation: "A train `platform` is the area where passengers get on or off.",
    subtopic: "travel_vocabulary",
    errorTag: "vocabulary_meaning_confusion",
  },
  {
    question: "Choose the opposite of `expensive`.",
    options: [
      { label: "A", text: "cheap" },
      { label: "B", text: "crowded" },
      { label: "C", text: "delayed" },
      { label: "D", text: "available" },
    ],
    correctAnswer: "A",
    explanation: "`Cheap` means not expensive.",
    subtopic: "adjectives",
    errorTag: "antonym_confusion",
  },
  {
    question: "Complete the sentence: The flight was ___, so we waited two hours.",
    options: [
      { label: "A", text: "delayed" },
      { label: "B", text: "direct" },
      { label: "C", text: "empty" },
      { label: "D", text: "local" },
    ],
    correctAnswer: "A",
    explanation: "`Delayed` means later than planned.",
    subtopic: "travel_vocabulary",
    errorTag: "vocabulary_context_error",
  },
  {
    question: "Choose the best word: Please keep your ___ with you at the airport.",
    options: [
      { label: "A", text: "passport" },
      { label: "B", text: "blanket" },
      { label: "C", text: "menu" },
      { label: "D", text: "receipt" },
    ],
    correctAnswer: "A",
    explanation: "A `passport` is an official travel document.",
    subtopic: "travel_vocabulary",
    errorTag: "vocabulary_context_error",
  },
  {
    question: "Which word means `free to use or buy now`?",
    options: [
      { label: "A", text: "available" },
      { label: "B", text: "ancient" },
      { label: "C", text: "asleep" },
      { label: "D", text: "angry" },
    ],
    correctAnswer: "A",
    explanation: "`Available` means ready or free to be used.",
    subtopic: "adjectives",
    errorTag: "vocabulary_meaning_confusion",
  },
  {
    question: "Choose the best meaning of `receipt`.",
    options: [
      { label: "A", text: "a paper or message that shows you paid" },
      { label: "B", text: "a place to sleep" },
      { label: "C", text: "a type of ticket gate" },
      { label: "D", text: "a heavy suitcase" },
    ],
    correctAnswer: "A",
    explanation: "A `receipt` shows that payment was made.",
    subtopic: "daily_vocabulary",
    errorTag: "vocabulary_meaning_confusion",
  },
  {
    question: "Complete the sentence: Could you ___ this word in Vietnamese?",
    options: [
      { label: "A", text: "translate" },
      { label: "B", text: "travel" },
      { label: "C", text: "train" },
      { label: "D", text: "try" },
    ],
    correctAnswer: "A",
    explanation: "`Translate` means change words from one language to another.",
    subtopic: "learning_vocabulary",
    errorTag: "vocabulary_context_error",
  },
];
