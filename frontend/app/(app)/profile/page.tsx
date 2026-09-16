import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

export default function ProfilePage() {
  return (
    <RoutePreviewScreen
      eyebrow="Profile"
      title="Profile & personalization"
      description="Explicit profile, preferences and learned context kept separate from mastery."
      metricLabel="Profile confidence"
      metricValue={74}
      metricDetail="Declared level stays learner-provided while estimated level comes from evidence."
      primaryHref="/profile/preferences"
      primaryLabel="Edit preferences"
      panels={[
        {
          title: "Learner profile",
          meta: "Explicit",
          body: "Name, declared level, locale, timezone and active goal are editable profile facts.",
        },
        {
          title: "Estimated level",
          meta: "System-derived",
          body: "Calibration and graded evidence can update the estimate without overwriting declared level.",
        },
        {
          title: "Progressive setup",
          meta: "Optional",
          body: "Ask for high-value missing fields only when they improve the next learning decision.",
        },
        {
          title: "Learner memory",
          meta: "Reviewable",
          body: "Conversation-derived facts need provenance and confirmation controls.",
        },
      ]}
    />
  );
}
