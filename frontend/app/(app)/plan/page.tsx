import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

export default function PlanPage() {
  return (
    <RoutePreviewScreen
      eyebrow="Plan"
      title="Learning plan"
      description="Long-term goal translated into an adaptive sequence of learning activities."
      metricLabel="Goal progress"
      metricValue={58}
      metricDetail="New graded evidence can reorder plan items while the active goal remains stable."
      primaryHref="/goals/b2-communication"
      primaryLabel="Open goal"
      panels={[
        {
          title: "Narrative tense contrast",
          meta: "Priority 1",
          body: "Due today. Activity spec is ready for targeted review.",
        },
        {
          title: "Past perfect in context",
          meta: "Priority 2",
          body: "Continue consolidation with short explanation and practice loops.",
        },
        {
          title: "Speaking fluency",
          meta: "Priority 3",
          body: "Use grammar in longer responses after tense contrast improves.",
        },
        {
          title: "Recommendation lifecycle",
          meta: "Accepting -> Ready",
          body: "The UI should navigate to Practice only when the activity is persisted and ready.",
        },
      ]}
    />
  );
}
