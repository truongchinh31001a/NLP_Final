import { SurfaceCard } from "@/components/ui/surface-card";

export default function PracticeLoading() {
  return (
    <SurfaceCard className="p-ae-xl">
      <div className="h-5 w-40 animate-pulse rounded-ae-pill bg-ae-primary-soft" />
      <div className="mt-ae-md h-8 w-3/4 animate-pulse rounded-ae-control bg-ae-primary-soft" />
      <div className="mt-ae-lg grid gap-ae-sm">
        {[0, 1, 2, 3].map((item) => (
          <div
            className="h-14 animate-pulse rounded-ae-control bg-ae-page"
            key={item}
          />
        ))}
      </div>
    </SurfaceCard>
  );
}
