interface FormErrorAlertProps {
  message: string;
}

export function FormErrorAlert({ message }: FormErrorAlertProps) {
  return (
    <div
      className="mb-4 p-3 rounded-md text-sm"
      role="alert"
      style={{
        backgroundColor:
          "color-mix(in srgb, var(--connect-error) 10%, transparent)",
        color: "var(--connect-error)",
      }}
    >
      {message}
    </div>
  );
}
