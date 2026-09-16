import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

export default function ProgressHistoryPage() {
  return (
    <RoutePreviewScreen
      eyebrow="Evidence history"
      title="Learning evidence timeline"
      description="Activities, submissions, reviews, mastery events and recommendations in one read model."
      metricLabel="Evidence freshness"
      metricValue={84}
      metricDetail="Newest graded activity should be reflected here and on Home without a full reload."
      panels={[
        {
          title: "Practice submitted",
          meta: "Today",
          body: "Past perfect targeted practice produced four positive and one negative observation.",
        },
        {
          title: "Review opened",
          meta: "Guidance only",
          body: "Review explains a mistake but does not create new mastery evidence.",
        },
        {
          title: "Recommendation updated",
          meta: "Adaptive",
          body: "Next action shifted toward narrative tense contrast after grading.",
        },
        {
          title: "Plan refreshed",
          meta: "Read model",
          body: "Plan order can change while the active learning goal stays stable.",
        },
      ]}
    />
  );
}
