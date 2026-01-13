import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary";

interface ButtonProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: ButtonVariant;
  className?: string;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  form?: string;
}

export function Button({
  children,
  onClick,
  variant = "primary",
  className = "",
  type = "button",
  disabled = false,
  form,
}: ButtonProps) {
  const variantClasses =
    variant === "primary"
      ? "[background-color:var(--connect-primary)] [color:var(--connect-primary-foreground)] hover:[background-color:var(--connect-primary-hover)]"
      : "[background-color:var(--connect-secondary)] [color:var(--connect-text)] hover:[background-color:var(--connect-secondary-hover)]";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      form={form}
      className={`px-4 py-1.5 font-medium rounded-md text-sm transition-colors flex items-center gap-2 cursor-pointer border-none disabled:opacity-50 disabled:cursor-not-allowed ${variantClasses} ${className}`}
      style={{ fontFamily: "var(--connect-font-button)" }}
    >
      {children}
    </button>
  );
}
