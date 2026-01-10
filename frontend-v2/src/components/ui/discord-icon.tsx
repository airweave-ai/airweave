import * as React from "react";

interface DiscordIconProps {
  className?: string;
  size?: number;
}

export const DiscordIcon: React.FC<DiscordIconProps> = ({
  className = "",
  size = 20,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M18.93 5.34a16.89 16.89 0 0 0-4.07-1.23.06.06 0 0 0-.07.03c-.18.31-.38.72-.52 1.04a15.65 15.65 0 0 0-4.54 0c-.14-.32-.35-.73-.52-1.04a.06.06 0 0 0-.07-.03 16.84 16.84 0 0 0-4.07 1.23.06.06 0 0 0-.03.02C2.4 9.36 1.73 13.27 2.1 17.13a.07.07 0 0 0 .03.05 16.94 16.94 0 0 0 5.04 2.49.06.06 0 0 0 .07-.02c.39-.52.73-1.06 1.03-1.64a.06.06 0 0 0-.04-.09 11.15 11.15 0 0 1-1.56-.73.06.06 0 0 1 0-.1c.1-.08.21-.16.31-.24a.06.06 0 0 1 .07-.01c3.27 1.46 6.82 1.46 10.05 0a.06.06 0 0 1 .07.01c.1.08.21.16.31.24a.06.06 0 0 1 0 .1c-.5.28-1.02.53-1.56.73a.06.06 0 0 0-.04.09c.3.58.65 1.12 1.03 1.64a.06.06 0 0 0 .07.02 16.9 16.9 0 0 0 5.04-2.49.07.07 0 0 0 .03-.05c.44-4.47-.75-8.34-3.13-11.77a.05.05 0 0 0-.03-.02Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx="9.5"
        cy="13"
        r="1.25"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <circle
        cx="14.5"
        cy="13"
        r="1.25"
        stroke="currentColor"
        strokeWidth="1.75"
      />
    </svg>
  );
};
