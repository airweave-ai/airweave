import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary";

interface ButtonProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: ButtonVariant;
  className?: string;
}

const variantStyles: Record<
  ButtonVariant,
  { bg: string; hover: string; color: string }
> = {
  primary: {
    bg: "var(--connect-primary)",
    hover: "var(--connect-primary-hover)",
    color: "white",
  },
  secondary: {
    bg: "var(--connect-secondary)",
    hover: "var(--connect-secondary-hover)",
    color: "var(--connect-text)",
  },
};

export function Button({
  children,
  onClick,
  variant = "primary",
  className = "",
}: ButtonProps) {
  const styles = variantStyles[variant];

  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 font-medium rounded-md text-sm transition-colors flex items-center gap-2 ${className}`}
      style={{
        backgroundColor: styles.bg,
        color: styles.color,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = styles.hover;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = styles.bg;
      }}
    >
      {children}
    </button>
  );
}
