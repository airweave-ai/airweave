const APP_COLUMN_X = 38;
const SOURCE_COLUMN_X = 172;
const AIRWEAVE_COLUMN_X = 318;

export function OAuthFlowDiagram({ sourceName }: { sourceName: string }) {
  const sourceLabel = sourceName.trim() || 'Source';
  const sourceLabelFontSize =
    sourceLabel.length > 20 ? 9 : sourceLabel.length > 14 ? 10 : 12;
  const sourceLabelTextLength = sourceLabel.length > 14 ? 92 : undefined;

  return (
    <svg
      aria-label="OAuth flow between your app, the source, and Airweave"
      className="mx-auto w-full max-w-86"
      viewBox="0 0 352 175"
      fill="none"
      role="img"
      xmlns="http://www.w3.org/2000/svg"
    >
      <SvgText fill="#A3A3A3" x={APP_COLUMN_X} y={19}>
        Your App
      </SvgText>
      <SvgText
        fill="#FAFAFA"
        fontSize={sourceLabelFontSize}
        textLength={sourceLabelTextLength}
        x={SOURCE_COLUMN_X}
        y={19}
      >
        {sourceLabel}
      </SvgText>
      <SvgText fill="#A3A3A3" x={AIRWEAVE_COLUMN_X} y={19}>
        Airweave
      </SvgText>

      <line
        x1={APP_COLUMN_X}
        y1="28"
        x2={APP_COLUMN_X}
        y2="162"
        stroke="#737373"
        strokeDasharray="2 2"
      />
      <line
        x1={SOURCE_COLUMN_X}
        y1="28"
        x2={SOURCE_COLUMN_X}
        y2="162"
        stroke="#737373"
        strokeDasharray="2 2"
      />
      <line
        x1={AIRWEAVE_COLUMN_X}
        y1="28"
        x2={AIRWEAVE_COLUMN_X}
        y2="162"
        stroke="#737373"
        strokeDasharray="2 2"
      />

      <line x1="42" y1="50.5" x2="168" y2="50.5" stroke="#FAFAFA" />
      <path
        d="M165 47.5L169 50.5L165 53.5"
        stroke="#FAFAFA"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <SvgText fill="#FAFAFA" x="106" y="46">
        Post SC
      </SvgText>

      <line x1="170" y1="70.5" x2="44" y2="70.5" stroke="#737373" />
      <path
        d="M47 67.5L43 70.5L47 73.5"
        stroke="#737373"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <SvgText fill="#737373" x="107" y="66">
        auth_url
      </SvgText>

      <line x1="42" y1="92.5" x2="314" y2="92.5" stroke="#737373" />
      <path
        d="M311 89.5L315 92.5L311 95.5"
        stroke="#737373"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="128" y="82" width="92" height="20" rx="10" fill="#171717" />
      <SvgText fill="#737373" x="174" y="96">
        redirect user
      </SvgText>

      <line x1="314" y1="114.5" x2="178" y2="114.5" stroke="#737373" />
      <path
        d="M181 111.5L177 114.5L181 117.5"
        stroke="#737373"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <SvgText fill="#737373" x="246" y="110">
        code token
      </SvgText>

      <line x1="170" y1="136.5" x2="44" y2="136.5" stroke="#737373" />
      <path
        d="M47 133.5L43 136.5L47 139.5"
        stroke="#737373"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <SvgText fill="#737373" x="107" y="132">
        SC active
      </SvgText>
    </svg>
  );
}

function SvgText({
  children,
  fill,
  fontSize = 12,
  textLength,
  x,
  y,
}: {
  children: React.ReactNode;
  fill: string;
  fontSize?: number;
  textLength?: number;
  x: number | string;
  y: number | string;
}) {
  return (
    <text
      x={x}
      y={y}
      fill={fill}
      fontFamily="monospace"
      fontSize={fontSize}
      fontWeight="500"
      letterSpacing="0.02em"
      textAnchor="middle"
      lengthAdjust={textLength ? 'spacingAndGlyphs' : undefined}
      textLength={textLength}
    >
      {children}
    </text>
  );
}
