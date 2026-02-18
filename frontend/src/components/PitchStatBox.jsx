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

/**
 * Single stat row with label and value.
 *
 * @param {{ label: string, value: string }} props
 */
function StatRow({ label, value }) {
  return (
    <div className="flex justify-between py-0.5">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}

/**
 * Stat panel showing detailed stats for a hovered pitch type.
 *
 * Displays velocity, movement, spin, and usage metrics when a pitch type
 * is hovered. Shows a prompt message when nothing is selected.
 *
 * @param {{ pitch: object|null }} props
 */
export default function PitchStatBox({ pitch }) {
  if (!pitch) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="text-sm text-gray-400">
          Hover over a pitch type to see details.
        </p>
      </div>
    );
  }

  const color = PITCH_COLORS[pitch.pitch_type] || DEFAULT_COLOR;
  const name = PITCH_NAMES[pitch.pitch_type] || pitch.pitch_type;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm">
      <div className="mb-3 flex items-center gap-2">
        <span
          className="inline-block h-4 w-4 rounded-full"
          style={{ backgroundColor: color }}
        />
        <span className="text-base font-semibold text-gray-900">{name}</span>
        <span className="text-gray-400">({pitch.pitch_type})</span>
      </div>

      <div className="mb-3">
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
          Velocity
        </h4>
        <StatRow label="Average" value={`${fmt(pitch.avg_velocity)} mph`} />
        <StatRow label="10th %ile" value={`${fmt(pitch.p10_velocity)} mph`} />
        <StatRow label="90th %ile" value={`${fmt(pitch.p90_velocity)} mph`} />
      </div>

      <div className="mb-3">
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
          Movement
        </h4>
        <StatRow
          label="Horizontal"
          value={`${fmt(pitch.avg_horz_break_in)} in.`}
        />
        <StatRow label="Vert. Break" value={`${fmt(pitch.avg_vert_break_in)} in.`} />
      </div>

      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
          Spin &amp; Usage
        </h4>
        <StatRow label="Spin Rate" value={`${fmt(pitch.avg_spin_rate, 0)} rpm`} />
        <StatRow
          label="Usage"
          value={`${fmt(pitch.usage_rate * 100)}%`}
        />
        <StatRow label="Count" value={`${pitch.pitch_count}`} />
      </div>
    </div>
  );
}
