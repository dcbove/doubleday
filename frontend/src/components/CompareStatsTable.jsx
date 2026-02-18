import { useMemo, useEffect, useRef } from "react";
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
  { label: "Horz Break", fn: (p) => `${fmt(p.avg_horz_break_in)} in.` },
  { label: "Vert Break", fn: (p) => `${fmt(p.avg_vert_break_in)} in.` },
  { label: "Spin Rate", fn: (p) => `${fmt(p.avg_spin_rate, 0)} rpm` },
  { label: "Usage", fn: (p) => `${fmt(p.usage_rate * 100)}%` },
  { label: "Count", fn: (p) => `${p.pitch_count}` },
];

/**
 * Side-by-side comparison stats table for two pitchers.
 *
 * Columns are the union of both pitchers' pitch types, sorted by max usage.
 * Each cell shows values for both pitchers stacked vertically.
 *
 * @param {{
 *   pitchesA: Array, pitchesB: Array,
 *   playerA: object, playerB: object,
 *   seasonA: number, seasonB: number,
 *   hoveredPitchType: string|null, onHover: function
 * }} props
 */
export default function CompareStatsTable({
  pitchesA,
  pitchesB,
  playerA,
  playerB,
  seasonA,
  seasonB,
  hoveredPitchType,
  onHover,
}) {
  const containerRef = useRef(null);
  const stickyRef = useRef(null);
  const colRefs = useRef({});

  const pitchTypeColumns = useMemo(() => {
    const mapA = new Map(pitchesA.map((p) => [p.pitch_type, p]));
    const mapB = new Map(pitchesB.map((p) => [p.pitch_type, p]));
    const allTypes = new Set([...mapA.keys(), ...mapB.keys()]);
    return [...allTypes]
      .map((pt) => ({
        pitchType: pt,
        pitchA: mapA.get(pt) || null,
        pitchB: mapB.get(pt) || null,
        maxUsage: Math.max(
          mapA.get(pt)?.usage_rate || 0,
          mapB.get(pt)?.usage_rate || 0,
        ),
      }))
      .sort((a, b) => b.maxUsage - a.maxUsage);
  }, [pitchesA, pitchesB]);

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
    <div>
      <div ref={containerRef} className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th
                ref={stickyRef}
                className="sticky left-0 bg-white px-1.5 py-1 text-left text-[10px] font-medium uppercase tracking-wide text-gray-400 sm:px-3 sm:py-2 sm:text-xs"
              >
                Stat
              </th>
              {pitchTypeColumns.map(({ pitchType }) => {
                const color = PITCH_COLORS[pitchType] || DEFAULT_COLOR;
                const isHovered = hoveredPitchType === pitchType;
                return (
                  <th
                    key={pitchType}
                    ref={(el) => {
                      colRefs.current[pitchType] = el;
                    }}
                    className={`cursor-pointer px-1.5 py-1 text-right text-[10px] font-semibold transition-colors sm:px-3 sm:py-2 sm:text-xs ${
                      isHovered ? "bg-blue-50" : ""
                    }`}
                    onMouseEnter={() => onHover(pitchType)}
                    onMouseLeave={() => onHover(null)}
                  >
                    <div className="flex items-center justify-end gap-1.5">
                      <span
                        className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                      <span className="text-gray-900">
                        {PITCH_NAMES[pitchType] || pitchType}
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
                {pitchTypeColumns.map(({ pitchType, pitchA, pitchB }) => {
                  const isHovered = hoveredPitchType === pitchType;
                  return (
                    <td
                      key={pitchType}
                      className={`cursor-pointer whitespace-nowrap px-1.5 py-1 text-right tabular-nums text-[10px] text-gray-900 transition-colors sm:px-3 sm:py-1.5 sm:text-xs ${
                        isHovered ? "bg-blue-50 font-semibold" : ""
                      }`}
                      onMouseEnter={() => onHover(pitchType)}
                      onMouseLeave={() => onHover(null)}
                    >
                      <div className="flex flex-col items-end gap-0.5">
                        <span className="flex items-center gap-1">
                          <span className="inline-block h-1.5 w-1.5 rounded-full bg-gray-500" />
                          {pitchA ? row.fn(pitchA) : "\u2014"}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="inline-block h-1.5 w-1.5 rounded-full border border-gray-500 bg-white" />
                          {pitchB ? row.fn(pitchB) : "\u2014"}
                        </span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
