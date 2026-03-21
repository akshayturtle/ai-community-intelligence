import { cn } from "../../lib/utils";

export default function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse bg-bg-tertiary rounded", className)} />;
}

export function CardSkeleton() {
  return (
    <div className="bg-bg-primary border border-border-primary rounded-xl p-5 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}
