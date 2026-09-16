import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

type GoalPageProps = {
  params: Promise<{
    goalId: string;
  }>;
};

export default async function GoalPage({ params }: GoalPageProps) {
  const { goalId } = await params;

  return (
    <RoutePreviewScreen
      eyebrow="Goal detail"
      title={goalId.replaceAll("-", " ")}
      description="Inspect the destination that the learning plan is trying to reach."
      metricLabel="Milestone progress"
      metricValue={58}
      metricDetail="Goal fields are learner-authoritative; mastery stays system-derived."
      panels={[
        {
          title: "Target level",
          meta: "B2",
          body: "Reach confident communication for work and study contexts.",
        },
        {
          title: "Grammar target",
          meta: "Core B2",
          body: "Use tense contrasts reliably in narrative explanations.",
        },
        {
          title: "Speaking target",
          meta: "8-10 min",
          body: "Sustain a conversation with fewer repair pauses.",
        },
        {
          title: "Plan link",
          meta: "Active",
          body: "Ordered plan items should continue to point back to this goal.",
        },
      ]}
    />
  );
}
