import { useEffect, useRef } from "react";
import { PITCH_COLORS, PITCH_NAMES, DEFAULT_COLOR } from "../util/pitchTypes";

/**
 * Format a numeric value to a fixed number of decimal places.
 *
 * @param {number|null|undefined} val - Value to format.
 * @param {number} decimals - Decimal places (default 1).
 * @returns {string} Formatted string or em dash for null/undefined.
 */
function fmt(val, decimals = 1) {
  if (val == null) return "\u2014";
  return val.toFixed(decimals);
}

const ROWS = [
  { label: "Velocity", fn: (p) => `${fmt(p.avg_velocity)} mph` },
  { label: "Velo 10th", fn: (p) => `${fmt(p.p10_velocity)} mph` },
  { label: "Velo 90th", fn: (p) => `${fmt(p.p90_velocity)} mph` },
  { label: "Horz Break", fn: (p) => `${fmt(p.avg_horz_break)} in.` },
  { label: "IVB", fn: (p) => `${fmt(p.avg_ivb)} in.` },
  { label: "Spin Rate", fn: (p) => `${fmt(p.avg_spin_rate, 0)} rpm` },
  { label: "Usage", fn: (p) => `${fmt(p.usage_rate * 100)}%` },
  { label: "Count", fn: (p) => `${p.pitch_count}` },
];

/**
 * Stats table showing all pitch types as columns with highlighted selection.
 *
 * Each pitch type is a column. Hovering or selecting a pitch type highlights
 * that column. Rows show velocity, movement, spin, and usage stats.
 *
 * @param {{ pitches: Array, hoveredPitchType: string|null, onHover: function }} props
 */
export default function PitchStatsTable({ pitches, hoveredPitchType, onHover }) {
  const containerRef = useRef(null);
  const stickyRef = useRef(null);
  const colRefs = useRef({});

  useEffect(() => {
    const col = colRefs.current[hoveredPitchType];
    const container = containerRef.current;
    const sticky = stickyRef.current;
    if (!col || !container || !sticky) return;

    const stickyWidth = sticky.offsetWidth;
    const colLeft = col.offsetLeft;
    const colRight = colLeft + col.offsetWidth;
    const visibleLeft = container.scrollLeft + stickyWidth;
    const visibleRight = container.scrollLeft + container.clientWidth;

    if (colRight > visibleRight) {
      container.scrollTo({
        left: colRight - container.clientWidth + 8,
        behavior: "smooth",
      });
    } else if (colLeft < visibleLeft) {
      container.scrollTo({
        left: colLeft - stickyWidth - 8,
        behavior: "smooth",
      });
    }
  }, [hoveredPitchType]);

  return (
    <div ref={containerRef} className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th ref={stickyRef} className="sticky left-0 bg-white px-1.5 py-1 text-left text-[10px] font-medium uppercase tracking-wide text-gray-400 sm:px-3 sm:py-2 sm:text-xs">
              Stat
            </th>
            {pitches.map((p) => {
              const color = PITCH_COLORS[p.pitch_type] || DEFAULT_COLOR;
              const isHovered = hoveredPitchType === p.pitch_type;
              return (
                <th
                  key={p.pitch_type}
                  ref={(el) => { colRefs.current[p.pitch_type] = el; }}
                  className={`cursor-pointer px-1.5 py-1 text-right text-[10px] font-semibold transition-colors sm:px-3 sm:py-2 sm:text-xs ${
                    isHovered ? "bg-blue-50" : ""
                  }`}
                  onMouseEnter={() => onHover(p.pitch_type)}
                  onMouseLeave={() => onHover(null)}
                >
                  <div className="flex items-center justify-end gap-1.5">
                    <span
                      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-gray-900">
                      {PITCH_NAMES[p.pitch_type] || p.pitch_type}
                    </span>
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {ROWS.map((row) => (
            <tr key={row.label}>
              <td className="sticky left-0 bg-white whitespace-nowrap px-1.5 py-1 text-[10px] font-medium text-gray-500 sm:px-3 sm:py-1.5 sm:text-xs">
                {row.label}
              </td>
              {pitches.map((p) => {
                const isHovered = hoveredPitchType === p.pitch_type;
                return (
                  <td
                    key={p.pitch_type}
                    className={`cursor-pointer whitespace-nowrap px-1.5 py-1 text-right tabular-nums text-[10px] text-gray-900 transition-colors sm:px-3 sm:py-1.5 sm:text-xs ${
                      isHovered ? "bg-blue-50 font-semibold" : ""
                    }`}
                    onMouseEnter={() => onHover(p.pitch_type)}
                    onMouseLeave={() => onHover(null)}
                  >
                    {row.fn(p)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
