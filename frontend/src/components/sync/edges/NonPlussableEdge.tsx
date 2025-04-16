import { memo } from "react";
import { BaseEdge, EdgeProps, getBezierPath } from 'reactflow';

export const NonPlussableEdge = memo(({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}: EdgeProps) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          strokeWidth: 2,
          stroke: '#94a3b8',
          strokeDasharray: '6 6',
          animation: 'flowMove 0.7s linear infinite',
        }}
      />
      <style>
        {`
          @keyframes flowMove {
            from {
              stroke-dashoffset: 12;
            }
            to {
              stroke-dashoffset: 0;
            }
          }
        `}
      </style>
    </>
  );
});

NonPlussableEdge.displayName = "NonPlussableEdge";
