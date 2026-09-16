import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

export default function LearnPage() {
  return (
    <RoutePreviewScreen
      eyebrow="Learn"
      title="Learn & Knowledge"
      description="Browse grounded grammar, vocabulary and examples linked to the learner model."
      metricLabel="Knowledge coverage"
      metricValue={68}
      metricDetail="Topics are grouped by skill so Tutor and Practice can reuse the same context."
      primaryHref="/learn/topics/past-perfect"
      primaryLabel="Open topic"
      panels={[
        {
          title: "Past perfect",
          meta: "Grammar - B1+",
          body: "Place one past event before another and connect it to narrative sequence.",
        },
        {
          title: "Narrative tense contrast",
          meta: "Grammar - B1+",
          body: "Compare past perfect and simple past when the time order is implied.",
        },
        {
          title: "Passive voice",
          meta: "Grammar - B1",
          body: "Use be + past participle across common classroom and exam prompts.",
        },
        {
          title: "Travel vocabulary",
          meta: "Vocabulary - A2-B1",
          body: "Build useful airport, hotel and direction phrases for real conversations.",
        },
      ]}
    />
  );
}
