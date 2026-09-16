import type { ReactNode } from "react";

type SurfaceCardProps = {
  children: ReactNode;
  className?: string;
};

export function SurfaceCard({ children, className = "" }: SurfaceCardProps) {
  return (
    <section
      className={`rounded-ae-card border border-ae-line bg-ae-surface shadow-[0_18px_46px_rgba(30,41,59,0.08)] ${className}`}
    >
      {children}
    </section>
  );
}
