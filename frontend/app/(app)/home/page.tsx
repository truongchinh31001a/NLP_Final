import { HomeScreen } from "@/features/home/screens/home-screen";
import { getDashboardSnapshot } from "@/lib/mock-data";

export default function HomePage() {
  return <HomeScreen snapshot={getDashboardSnapshot()} />;
}
