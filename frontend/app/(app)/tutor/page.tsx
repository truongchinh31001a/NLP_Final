import { ChatWorkbench } from "@/components/chat-workbench";
import { getDashboardSnapshot } from "@/lib/mock-data";

export default function TutorPage() {
  return <ChatWorkbench snapshot={getDashboardSnapshot()} />;
}
