import type { ReactNode } from "react";
import {
  useAirweaveConnect,
  type UseAirweaveConnectOptions,
  type UseAirweaveConnectReturn,
} from "./useAirweaveConnect";

type RenderProps = UseAirweaveConnectReturn;

export interface AirweaveConnectProps extends UseAirweaveConnectOptions {
  /**
   * Render prop that receives all hook return values.
   * Use this to render your trigger button or any custom UI.
   *
   * @example
   * ```tsx
   * <AirweaveConnect getSessionToken={fetchToken}>
   *   {({ open, isLoading }) => (
   *     <button onClick={open} disabled={isLoading}>
   *       {isLoading ? "Loading..." : "Connect"}
   *     </button>
   *   )}
   * </AirweaveConnect>
   * ```
   */
  children: (props: RenderProps) => ReactNode;
}

/**
 * A component wrapper for the useAirweaveConnect hook.
 * Provides a simpler API for common use cases.
 *
 * @example
 * ```tsx
 * // Simple usage
 * <AirweaveConnect
 *   getSessionToken={async () => {
 *     const res = await fetch("/api/connect-session");
 *     const data = await res.json();
 *     return data.session_token;
 *   }}
 *   onSuccess={(connectionId) => {
 *     console.log("New connection:", connectionId);
 *   }}
 * >
 *   {({ open, isLoading }) => (
 *     <button onClick={open} disabled={isLoading}>
 *       {isLoading ? "Connecting..." : "Connect Apps"}
 *     </button>
 *   )}
 * </AirweaveConnect>
 *
 * // With all features
 * <AirweaveConnect
 *   getSessionToken={fetchToken}
 *   initialView="sources"
 *   showCloseButton
 *   modalStyle={{ maxWidth: "600px" }}
 *   onSuccess={handleSuccess}
 *   onClose={(reason) => console.log("Closed:", reason)}
 * >
 *   {({ open, isLoading, isOpen, navigate }) => (
 *     <div>
 *       <button onClick={open} disabled={isLoading || isOpen}>
 *         {isLoading ? "Preparing..." : "Connect Apps"}
 *       </button>
 *       {isOpen && (
 *         <button onClick={() => navigate("sources")}>
 *           Browse Sources
 *         </button>
 *       )}
 *     </div>
 *   )}
 * </AirweaveConnect>
 * ```
 */
export function AirweaveConnect({
  children,
  ...hookOptions
}: AirweaveConnectProps) {
  const hookReturn = useAirweaveConnect(hookOptions);
  return <>{children(hookReturn)}</>;
}
