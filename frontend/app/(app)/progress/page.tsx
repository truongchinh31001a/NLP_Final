import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

export default function ProgressPage() {
  return (
    <RoutePreviewScreen
      eyebrow="Progress"
      title="Your current mastery"
      description="Read-only progress, weak patterns and recent learning evidence."
      metricLabel="Overall mastery"
      metricValue={72}
      metricDetail="Progress is derived from graded activity and should not change by viewing this page."
      primaryHref="/progress/history"
      primaryLabel="View history"
      panels={[
        {
          title: "Past perfect selection",
          meta: "76% mastery",
          body: "Improving after the latest targeted activity, with one sequencing mistake still active.",
        },
        {
          title: "Narrative tense contrast",
          meta: "62% mastery",
          body: "Current weak pattern. The plan should prioritize short contrastive practice.",
        },
        {
          title: "Passive voice",
          meta: "71% mastery",
          body: "Stable enough for review spacing, but still useful in mixed grammar sets.",
        },
        {
          title: "Recent evidence",
          meta: "18 observations",
          body: "Skill observations from the last two weeks drive recommendations.",
        },
      ]}
    />
  );
}
