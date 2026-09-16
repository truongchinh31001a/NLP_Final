import type { ReactNode } from "react";

import { Sidebar } from "@/components/layout/sidebar";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-ae-page text-ae-ink">
      <div className="flex min-h-screen w-full">
        <Sidebar />
        <main className="min-w-0 flex-1 px-ae-md py-ae-lg pb-24 md:px-ae-xl md:py-ae-xl md:pb-ae-xl">
          {children}
        </main>
      </div>
    </div>
  );
}
