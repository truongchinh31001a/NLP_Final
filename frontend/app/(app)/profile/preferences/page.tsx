import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

export default function PreferencesPage() {
  return (
    <RoutePreviewScreen
      eyebrow="Preferences"
      title="Learning preferences"
      description="User-authoritative settings used by activity generation and planning."
      metricLabel="Preference fit"
      metricValue={82}
      metricDetail="Preference changes should refresh recommendation-sensitive reads later."
      panels={[
        {
          title: "Preferred difficulty",
          meta: "Adaptive / B1+",
          body: "The learner can guide difficulty while the system still adapts from evidence.",
        },
        {
          title: "Questions per practice",
          meta: "5",
          body: "Short sessions keep the loop fast enough for repeated practice.",
        },
        {
          title: "Preferred mode",
          meta: "Focused practice",
          body: "Used when generating the next activity specification.",
        },
        {
          title: "Explanation style",
          meta: "Examples first",
          body: "Tutor responses can favor short explanations with concrete examples.",
        },
      ]}
    />
  );
}
