import { RoutePreviewScreen } from "@/features/platform/screens/route-preview-screen";

type SkillPageProps = {
  params: Promise<{
    skillId: string;
  }>;
};

export default async function SkillPage({ params }: SkillPageProps) {
  const { skillId } = await params;

  return (
    <RoutePreviewScreen
      eyebrow="Skill detail"
      title={skillId.replaceAll("-", " ").replaceAll(".", " ")}
      description="Skill trend, recent observations, linked mistakes and related skills."
      metricLabel="Mastery"
      metricValue={76}
      metricDetail="Skill mastery is system-derived from graded evidence, not editable profile data."
      panels={[
        {
          title: "Trend",
          meta: "Rising",
          body: "Recent answers show stronger recognition of earlier past events.",
        },
        {
          title: "Linked mistake",
          meta: "Question 4",
          body: "The learner chose simple past where narrative order required past perfect.",
        },
        {
          title: "Related skill",
          meta: "Prerequisite",
          body: "Simple past event sequencing remains useful context.",
        },
        {
          title: "Next review",
          meta: "Scheduled",
          body: "Review spacing can move out once confidence stabilizes.",
        },
      ]}
    />
  );
}
