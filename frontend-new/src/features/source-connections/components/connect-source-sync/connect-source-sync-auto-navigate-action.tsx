import * as React from 'react';
import { ConnectSourcePrimaryActionButton } from '../connect-source-step-layout';

const ACTIVE_NAVIGATION_DELAY_SECONDS = 5;

export function ConnectSourceSyncAutoNavigateAction({
  onNavigate,
}: {
  onNavigate: () => void;
}) {
  const [countdownSeconds, setCountdownSeconds] = React.useState(
    ACTIVE_NAVIGATION_DELAY_SECONDS,
  );
  const [isHovered, setIsHovered] = React.useState(false);
  const [isFocused, setIsFocused] = React.useState(false);
  const isCountdownPaused = isHovered || isFocused;

  React.useEffect(() => {
    if (isCountdownPaused) {
      return;
    }

    if (countdownSeconds <= 0) {
      onNavigate();
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setCountdownSeconds((current) => current - 1);
    }, 1000);

    return () => window.clearTimeout(timeoutId);
  }, [countdownSeconds, isCountdownPaused, onNavigate]);

  const resetCountdown = React.useCallback(() => {
    setCountdownSeconds(ACTIVE_NAVIGATION_DELAY_SECONDS);
  }, []);

  return (
    <ConnectSourcePrimaryActionButton
      type="button"
      onBlur={() => setIsFocused(false)}
      onFocus={() => {
        resetCountdown();
        setIsFocused(true);
      }}
      onClick={onNavigate}
      onMouseEnter={() => {
        resetCountdown();
        setIsHovered(true);
      }}
      onMouseLeave={() => setIsHovered(false)}
    >
      Go to collection [in {countdownSeconds} s]
    </ConnectSourcePrimaryActionButton>
  );
}
