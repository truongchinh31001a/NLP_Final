import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

export default function MemoryPage() {
  return (
    <RoutePreviewScreen
      eyebrow="Memory"
      title="Learner memory"
      description="Facts learned from conversation with confidence, status and provenance."
      metricLabel="Confirmed context"
      metricValue={64}
      metricDetail="Memory can personalize Tutor, but it should not directly edit mastery."
      panels={[
        {
          title: "Goal context",
          meta: "Active",
          body: "Learner wants stronger B2 communication for work or study.",
        },
        {
          title: "Weak pattern",
          meta: "Needs confirmation",
          body: "The learner may struggle when past events are implied rather than explicit.",
        },
        {
          title: "Mode preference",
          meta: "Active",
          body: "Focused practice is more useful than long open-ended sessions right now.",
        },
        {
          title: "Source trace",
          meta: "Conversation",
          body: "Each memory fact should keep the message that produced it.",
        },
      ]}
    />
  );
}
