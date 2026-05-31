import { ChatWorkbench } from "@/components/chat-workbench";
import { getDashboardSnapshot } from "@/lib/mock-data";

export default function HomePage() {
  const snapshot = getDashboardSnapshot();

  return <ChatWorkbench snapshot={snapshot} />;
}
