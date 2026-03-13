import { cn } from "@/lib/utils";
import type { ModalAppearance } from "../hooks/usePlaygroundState";

interface ConfigToolbarProps {
  modal: ModalAppearance;
  onUpdate: (patch: Partial<ModalAppearance>) => void;
}

const RADII = [8, 12, 16, 20];

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-1">
        {children}
      </div>
    </div>
  );
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2 py-0.5 rounded-md text-[11px] font-medium transition-colors",
        active
          ? "bg-muted text-foreground"
          : "text-muted-foreground/50 hover:text-muted-foreground hover:bg-muted/50"
      )}
    >
      {children}
    </button>
  );
}

export function ConfigToolbar({ modal, onUpdate }: ConfigToolbarProps) {
  return (
    <div className="space-y-0.5">
      <Row label="Radius">
        {RADII.map((r) => (
          <Pill key={r} active={modal.borderRadius === r} onClick={() => onUpdate({ borderRadius: r })}>
            {r}
          </Pill>
        ))}
      </Row>

      <Row label="Border">
        {[0, 1, 2].map((w) => (
          <Pill key={w} active={modal.borderWidth === w} onClick={() => onUpdate({ borderWidth: w })}>
            {w}px
          </Pill>
        ))}
        {modal.borderWidth > 0 && (
          <label className="relative cursor-pointer ml-1">
            <input
              type="color"
              value={modal.borderColor}
              onChange={(e) => onUpdate({ borderColor: e.target.value })}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div
              className="w-5 h-5 rounded-md border border-border/30"
              style={{ backgroundColor: modal.borderColor }}
            />
          </label>
        )}
      </Row>
    </div>
  );
}
