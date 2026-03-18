interface SkeletonProps {
  className?: string;
}

function Bone({ className = "" }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded ${className}`}
      style={{
        backgroundColor:
          "color-mix(in srgb, var(--connect-text-muted) 15%, transparent)",
      }}
    />
  );
}

export function ConnectionItemSkeleton() {
  return (
    <div
      className="flex items-center justify-between p-4 rounded-lg gap-3"
      style={{
        backgroundColor: "var(--connect-surface)",
        border: "1px solid var(--connect-border)",
      }}
    >
      <div className="flex items-center gap-3 grow">
        <Bone className="size-8 shrink-0 rounded-lg" />
        <div className="grow flex flex-col gap-1.5">
          <Bone className="h-3.5 w-28 rounded" />
          <Bone className="h-3 w-16 rounded" />
        </div>
      </div>
      <Bone className="h-6 w-14 rounded-full" />
    </div>
  );
}

export function SourceItemSkeleton() {
  return (
    <div
      className="flex items-center gap-3 p-2 rounded-lg"
      style={{
        backgroundColor: "var(--connect-surface)",
        border: "1px solid var(--connect-border)",
      }}
    >
      <Bone className="size-8 shrink-0 rounded-lg" />
      <Bone className="h-3.5 w-32 rounded" />
    </div>
  );
}

export function SourceConfigSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      {/* Section heading */}
      <Bone className="h-4 w-28 rounded" />

      {/* Form field 1 */}
      <div className="flex flex-col gap-2">
        <Bone className="h-3 w-20 rounded" />
        <Bone className="h-10 w-full rounded-lg" />
      </div>

      {/* Form field 2 */}
      <div className="flex flex-col gap-2">
        <Bone className="h-3 w-24 rounded" />
        <Bone className="h-10 w-full rounded-lg" />
      </div>

      {/* Section heading */}
      <Bone className="h-4 w-24 rounded mt-2" />

      {/* Form field 3 */}
      <div className="flex flex-col gap-2">
        <Bone className="h-3 w-16 rounded" />
        <Bone className="h-10 w-full rounded-lg" />
      </div>
    </div>
  );
}
