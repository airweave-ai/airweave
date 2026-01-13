// Re-export all types from main connect package
export * from "airweave-connect/lib/types";

// Export utility functions
export {
  canConnect,
  getStatusColor,
  getStatusLabel,
} from "airweave-connect/lib/connection-utils";
export { getAppIconUrl } from "airweave-connect/lib/icons";

// Export theme defaults (useful for extending/customizing)
export {
  defaultLabels,
  defaultDarkColors,
  defaultLightColors,
  defaultOptions,
} from "airweave-connect/lib/theme-defaults";

// Export the main class and its types
export { AirweaveConnect } from "./AirweaveConnect";
export type {
  AirweaveConnectConfig,
  AirweaveConnectState,
  ModalStyle,
} from "./types";

// Export constants
export { DEFAULT_CONNECT_URL } from "./constants";
