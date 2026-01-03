import { ErrorState } from "../components/ui/error-state";
import type { ComponentPreviewConfig } from "./types";

export const errorStatePreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "A basic error state with an error message",
      preview: (
        <ErrorState error="Something went wrong. Please try again later." />
      ),
      code: `<ErrorState error="Something went wrong. Please try again later." />`,
    },
    {
      title: "With Title",
      description: "Error state with a title and message",
      preview: (
        <ErrorState
          title="Connection Failed"
          error="Unable to connect to the server. Please check your internet connection."
        />
      ),
      code: `<ErrorState
  title="Connection Failed"
  error="Unable to connect to the server. Please check your internet connection."
/>`,
    },
    {
      title: "Error Object",
      description: "Error state can accept an Error object",
      preview: (
        <ErrorState
          title="Request Failed"
          error={new Error("Network request failed: 500 Internal Server Error")}
        />
      ),
      code: `<ErrorState
  title="Request Failed"
  error={new Error("Network request failed: 500 Internal Server Error")}
/>`,
    },
    {
      title: "Various Contexts",
      description: "Different error scenarios",
      preview: (
        <div className="flex flex-col gap-4">
          <ErrorState error="Invalid email address format" />
          <ErrorState
            title="Authentication Error"
            error="Your session has expired. Please log in again."
          />
          <ErrorState
            title="Permission Denied"
            error="You don't have access to this resource."
          />
        </div>
      ),
      code: `<ErrorState error="Invalid email address format" />
<ErrorState
  title="Authentication Error"
  error="Your session has expired. Please log in again."
/>
<ErrorState
  title="Permission Denied"
  error="You don't have access to this resource."
/>`,
    },
  ],
};
