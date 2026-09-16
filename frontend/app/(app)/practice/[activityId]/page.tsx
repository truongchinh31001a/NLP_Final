import { PracticeRouteScreen } from "@/features/practice/screens/practice-route-screen";

type PracticePageProps = {
  params: Promise<{
    activityId: string;
  }>;
};

export default async function PracticePage({ params }: PracticePageProps) {
  const { activityId } = await params;
  return <PracticeRouteScreen activityId={activityId} />;
}
