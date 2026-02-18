import { useMemo } from "react";
import { PITCH_COLORS, DEFAULT_COLOR } from "../util/pitchTypes";

const SVG_WIDTH = 600;
const SVG_HEIGHT = 500;
const MARGIN = { top: 20, right: 20, bottom: 50, left: 60 };
const PLOT_WIDTH = SVG_WIDTH - MARGIN.left - MARGIN.right;
const PLOT_HEIGHT = SVG_HEIGHT - MARGIN.top - MARGIN.bottom;

/**
 * Overlay movement chart comparing two pitchers.
 *
 * Pitcher A is drawn with filled circles and solid ellipses; Pitcher B uses
 * outlined circles (white fill, colored stroke) and dashed ellipses. Axis
 * bounds are computed from the union of both pitchers' p10/p90 data.
 *
 * @param {{
 *   pitchesA: Array, pitchesB: Array,
 *   playerA: object, playerB: object,
 *   seasonA: number, seasonB: number,
 *   hoveredPitchType: string|null, onHover: function
 * }} props
 */
export default function CompareMovementChart({
  pitchesA,
  pitchesB,
  playerA,
  playerB,
  seasonA,
  seasonB,
  hoveredPitchType,
  onHover,
}) {
  const allPitches = useMemo(
    () => [...pitchesA, ...pitchesB],
    [pitchesA, pitchesB],
  );

  const { xMin, xMax, yMin, yMax } = useMemo(() => {
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (const p of allPitches) {
      minX = Math.min(minX, p.p10_horz_break_in);
      maxX = Math.max(maxX, p.p90_horz_break_in);
      minY = Math.min(minY, p.p10_vert_break_in);
      maxY = Math.max(maxY, p.p90_vert_break_in);
    }
    const PAD = 3;
    return {
      xMin: Math.floor((minX - PAD) / 5) * 5,
      xMax: Math.ceil((maxX + PAD) / 5) * 5,
      yMin: Math.floor((minY - PAD) / 5) * 5,
      yMax: Math.ceil((maxY + PAD) / 5) * 5,
    };
  }, [allPitches]);

  function scaleX(val) {
    return MARGIN.left + ((val - xMin) / (xMax - xMin)) * PLOT_WIDTH;
  }

  function scaleY(val) {
    return MARGIN.top + ((yMax - val) / (yMax - yMin)) * PLOT_HEIGHT;
  }

  const xTicks = [];
  for (let v = xMin; v <= xMax; v += 5) xTicks.push(v);

  const yTicks = [];
  for (let v = yMin; v <= yMax; v += 5) yTicks.push(v);

  const xMinorTicks = [];
  for (let v = xMin; v <= xMax; v += 1) {
    if (v % 5 !== 0) xMinorTicks.push(v);
  }

  const yMinorTicks = [];
  for (let v = yMin; v <= yMax; v += 1) {
    if (v % 5 !== 0) yMinorTicks.push(v);
  }

  return (
    <div>
      <svg
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        className="w-full max-w-[250px] sm:max-w-[400px]"
        role="img"
        aria-label="Pitch movement comparison chart"
      >
        {/* Plot background */}
        <rect
          x={MARGIN.left}
          y={MARGIN.top}
          width={PLOT_WIDTH}
          height={PLOT_HEIGHT}
          fill="white"
        />

        {/* Minor grid lines */}
        {xMinorTicks.map((v) => (
          <line
            key={`gmx-${v}`}
            x1={scaleX(v)}
            x2={scaleX(v)}
            y1={MARGIN.top}
            y2={SVG_HEIGHT - MARGIN.bottom}
            stroke="#f3f4f6"
            strokeWidth={1}
          />
        ))}
        {yMinorTicks.map((v) => (
          <line
            key={`gmy-${v}`}
            x1={MARGIN.left}
            x2={SVG_WIDTH - MARGIN.right}
            y1={scaleY(v)}
            y2={scaleY(v)}
            stroke="#f3f4f6"
            strokeWidth={1}
          />
        ))}

        {/* Major grid lines */}
        {xTicks.map((v) => (
          <line
            key={`gx-${v}`}
            x1={scaleX(v)}
            x2={scaleX(v)}
            y1={MARGIN.top}
            y2={SVG_HEIGHT - MARGIN.bottom}
            stroke="#e5e7eb"
            strokeWidth={1.5}
          />
        ))}
        {yTicks.map((v) => (
          <line
            key={`gy-${v}`}
            x1={MARGIN.left}
            x2={SVG_WIDTH - MARGIN.right}
            y1={scaleY(v)}
            y2={scaleY(v)}
            stroke="#e5e7eb"
            strokeWidth={1.5}
          />
        ))}

        {/* Zero crosshair lines */}
        {xMin <= 0 && xMax >= 0 && (
          <line
            x1={scaleX(0)}
            x2={scaleX(0)}
            y1={MARGIN.top}
            y2={SVG_HEIGHT - MARGIN.bottom}
            stroke="#9ca3af"
            strokeWidth={1.5}
            strokeDasharray="4 2"
          />
        )}
        {yMin <= 0 && yMax >= 0 && (
          <line
            x1={MARGIN.left}
            x2={SVG_WIDTH - MARGIN.right}
            y1={scaleY(0)}
            y2={scaleY(0)}
            stroke="#9ca3af"
            strokeWidth={1.5}
            strokeDasharray="4 2"
          />
        )}

        {/* Tick labels */}
        {xTicks.map((v) => (
          <text
            key={`tx-${v}`}
            x={scaleX(v)}
            y={SVG_HEIGHT - MARGIN.bottom + 18}
            textAnchor="middle"
            fontSize={18}
            fill="#6b7280"
          >
            {v}
          </text>
        ))}
        {yTicks.map((v) => (
          <text
            key={`ty-${v}`}
            x={MARGIN.left - 10}
            y={scaleY(v) + 4}
            textAnchor="end"
            fontSize={18}
            fill="#6b7280"
          >
            {v}
          </text>
        ))}

        {/* Axis labels */}
        <text
          x={MARGIN.left + PLOT_WIDTH / 2}
          y={SVG_HEIGHT - 6}
          textAnchor="middle"
          fontSize={21}
          fill="#374151"
        >
          Horizontal Break (in.)
        </text>
        <text
          x={16}
          y={MARGIN.top + PLOT_HEIGHT / 2}
          textAnchor="middle"
          fontSize={21}
          fill="#374151"
          transform={`rotate(-90, 16, ${MARGIN.top + PLOT_HEIGHT / 2})`}
        >
          Vertical Break (in.)
        </text>

        {/* Pitcher A ellipses (solid) */}
        {pitchesA.map((p) => {
          const color = PITCH_COLORS[p.pitch_type] || DEFAULT_COLOR;
          const isHovered = hoveredPitchType === p.pitch_type;
          const dimmed = hoveredPitchType && !isHovered;
          return (
            <ellipse
              key={`ea-${p.pitch_type}`}
              cx={scaleX(p.avg_horz_break_in)}
              cy={scaleY(p.avg_vert_break_in)}
              rx={
                Math.abs(
                  scaleX(p.p90_horz_break_in) - scaleX(p.p10_horz_break_in),
                ) / 2
              }
              ry={
                Math.abs(
                  scaleY(p.p10_vert_break_in) - scaleY(p.p90_vert_break_in),
                ) / 2
              }
              fill={color}
              fillOpacity={isHovered ? 0.25 : 0.12}
              stroke={color}
              strokeWidth={isHovered ? 1.5 : 0.5}
              strokeOpacity={isHovered ? 0.8 : 0.3}
              opacity={dimmed ? 0.3 : 1}
            />
          );
        })}

        {/* Pitcher B ellipses (dashed) */}
        {pitchesB.map((p) => {
          const color = PITCH_COLORS[p.pitch_type] || DEFAULT_COLOR;
          const isHovered = hoveredPitchType === p.pitch_type;
          const dimmed = hoveredPitchType && !isHovered;
          return (
            <ellipse
              key={`eb-${p.pitch_type}`}
              cx={scaleX(p.avg_horz_break_in)}
              cy={scaleY(p.avg_vert_break_in)}
              rx={
                Math.abs(
                  scaleX(p.p90_horz_break_in) - scaleX(p.p10_horz_break_in),
                ) / 2
              }
              ry={
                Math.abs(
                  scaleY(p.p10_vert_break_in) - scaleY(p.p90_vert_break_in),
                ) / 2
              }
              fill="transparent"
              stroke={color}
              strokeWidth={isHovered ? 2 : 1}
              strokeOpacity={isHovered ? 0.8 : 0.4}
              strokeDasharray="6 3"
              opacity={dimmed ? 0.3 : 1}
            />
          );
        })}

        {/* Pitcher A circles (filled) */}
        {pitchesA.map((p) => {
          const color = PITCH_COLORS[p.pitch_type] || DEFAULT_COLOR;
          const isHovered = hoveredPitchType === p.pitch_type;
          const dimmed = hoveredPitchType && !isHovered;
          return (
            <circle
              key={`ca-${p.pitch_type}`}
              cx={scaleX(p.avg_horz_break_in)}
              cy={scaleY(p.avg_vert_break_in)}
              r={isHovered ? 11 : 9}
              fill={color}
              stroke="white"
              strokeWidth={2}
              opacity={dimmed ? 0.3 : 1}
            />
          );
        })}

        {/* Pitcher B circles (outlined) */}
        {pitchesB.map((p) => {
          const color = PITCH_COLORS[p.pitch_type] || DEFAULT_COLOR;
          const isHovered = hoveredPitchType === p.pitch_type;
          const dimmed = hoveredPitchType && !isHovered;
          return (
            <circle
              key={`cb-${p.pitch_type}`}
              cx={scaleX(p.avg_horz_break_in)}
              cy={scaleY(p.avg_vert_break_in)}
              r={isHovered ? 11 : 9}
              fill="white"
              stroke={color}
              strokeWidth={2.5}
              opacity={dimmed ? 0.3 : 1}
            />
          );
        })}

        {/* Invisible hit targets for both pitchers */}
        {pitchesA.map((p) => (
          <circle
            key={`ha-${p.pitch_type}`}
            cx={scaleX(p.avg_horz_break_in)}
            cy={scaleY(p.avg_vert_break_in)}
            r={16}
            fill="transparent"
            style={{ cursor: "pointer" }}
            onMouseEnter={() => onHover(p.pitch_type)}
            onMouseLeave={() => onHover(null)}
          />
        ))}
        {pitchesB.map((p) => (
          <circle
            key={`hb-${p.pitch_type}`}
            cx={scaleX(p.avg_horz_break_in)}
            cy={scaleY(p.avg_vert_break_in)}
            r={16}
            fill="transparent"
            style={{ cursor: "pointer" }}
            onMouseEnter={() => onHover(p.pitch_type)}
            onMouseLeave={() => onHover(null)}
          />
        ))}
      </svg>
    </div>
  );
}
