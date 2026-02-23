import { useMemo } from "react";
import { View, Pressable } from "react-native";
import Svg, {
  Rect,
  Line,
  Circle,
  Ellipse,
  Text as SvgText,
} from "react-native-svg";
import { PITCH_COLORS, DEFAULT_COLOR } from "../util/pitchTypes";

const SVG_WIDTH = 600;
const SVG_HEIGHT = 500;
const MARGIN = { top: 20, right: 20, bottom: 50, left: 60 };
const PLOT_WIDTH = SVG_WIDTH - MARGIN.left - MARGIN.right;
const PLOT_HEIGHT = SVG_HEIGHT - MARGIN.top - MARGIN.bottom;

/**
 * Interactive SVG scatter chart of pitch movement by type.
 *
 * Plots each pitch type as a colored circle at its average (horizontal break,
 * IVB) position with a semi-transparent ellipse showing the p10-p90 spread.
 * Tapping a pitch type toggles highlight; tapping again deselects.
 *
 * @param {{ pitches: Array, hoveredPitchType: string|null, onHover: function }} props
 */
export default function PitchMovementChart({
  pitches,
  hoveredPitchType,
  onHover,
}) {
  const { xMin, xMax, yMin, yMax } = useMemo(() => {
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (const p of pitches) {
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
  }, [pitches]);

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

  function handlePress(pitchType) {
    onHover(hoveredPitchType === pitchType ? null : pitchType);
  }

  return (
    <View style={{ aspectRatio: SVG_WIDTH / SVG_HEIGHT }} className="w-full max-w-[250px] sm:max-w-[400px]">
      <Svg
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        width="100%"
        height="100%"
      >
        {/* Plot background */}
        <Rect
          x={MARGIN.left}
          y={MARGIN.top}
          width={PLOT_WIDTH}
          height={PLOT_HEIGHT}
          fill="white"
        />

        {/* Minor grid lines (every 1 inch) */}
        {xMinorTicks.map((v) => (
          <Line
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
          <Line
            key={`gmy-${v}`}
            x1={MARGIN.left}
            x2={SVG_WIDTH - MARGIN.right}
            y1={scaleY(v)}
            y2={scaleY(v)}
            stroke="#f3f4f6"
            strokeWidth={1}
          />
        ))}

        {/* Major grid lines (every 5 inches) */}
        {xTicks.map((v) => (
          <Line
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
          <Line
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
          <Line
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
          <Line
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
          <SvgText
            key={`tx-${v}`}
            x={scaleX(v)}
            y={SVG_HEIGHT - MARGIN.bottom + 18}
            textAnchor="middle"
            fontSize={18}
            fill="#6b7280"
          >
            {v}
          </SvgText>
        ))}
        {yTicks.map((v) => (
          <SvgText
            key={`ty-${v}`}
            x={MARGIN.left - 10}
            y={scaleY(v) + 4}
            textAnchor="end"
            fontSize={18}
            fill="#6b7280"
          >
            {v}
          </SvgText>
        ))}

        {/* Axis labels */}
        <SvgText
          x={MARGIN.left + PLOT_WIDTH / 2}
          y={SVG_HEIGHT - 6}
          textAnchor="middle"
          fontSize={21}
          fill="#374151"
        >
          Horizontal Break (in.)
        </SvgText>
        <SvgText
          x={16}
          y={MARGIN.top + PLOT_HEIGHT / 2}
          textAnchor="middle"
          fontSize={21}
          fill="#374151"
          rotation={-90}
          originX={16}
          originY={MARGIN.top + PLOT_HEIGHT / 2}
        >
          Vertical Break (in.)
        </SvgText>

        {/* Ellipses (p10-p90 spread) */}
        {pitches.map((p) => {
          const color = PITCH_COLORS[p.pitch_type] || DEFAULT_COLOR;
          const isHovered = hoveredPitchType === p.pitch_type;
          const dimmed = hoveredPitchType && !isHovered;
          return (
            <Ellipse
              key={`e-${p.pitch_type}`}
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

        {/* Center circles */}
        {pitches.map((p) => {
          const color = PITCH_COLORS[p.pitch_type] || DEFAULT_COLOR;
          const isHovered = hoveredPitchType === p.pitch_type;
          const dimmed = hoveredPitchType && !isHovered;
          return (
            <Circle
              key={`c-${p.pitch_type}`}
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

        {/* Tap targets */}
        {pitches.map((p) => (
          <Circle
            key={`h-${p.pitch_type}`}
            cx={scaleX(p.avg_horz_break_in)}
            cy={scaleY(p.avg_vert_break_in)}
            r={20}
            fill="transparent"
            onPress={() => handlePress(p.pitch_type)}
          />
        ))}
      </Svg>
    </View>
  );
}
