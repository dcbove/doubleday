import { useMemo, useEffect, useRef } from "react";
import { View, Text, ScrollView, Pressable } from "react-native";
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

const LABEL_WIDTH = 80;

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
  hoveredPitchType,
  onHover,
}) {
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

  const scrollRef = useRef(null);
  const columnOffsets = useRef({});

  function handlePress(pitchType) {
    onHover(hoveredPitchType === pitchType ? null : pitchType);
  }

  useEffect(() => {
    if (hoveredPitchType && scrollRef.current && columnOffsets.current[hoveredPitchType] != null) {
      scrollRef.current.scrollTo({ x: columnOffsets.current[hoveredPitchType], animated: true });
    }
  }, [hoveredPitchType]);

  return (
    <View className="flex-row">
      {/* Sticky label column */}
      <View style={{ width: LABEL_WIDTH }}>
        <View className="flex-row items-center px-1.5 py-1 sm:px-3 sm:py-2">
          <Text className="text-[10px] font-medium uppercase tracking-wide text-gray-400 sm:text-xs">
            Stat
          </Text>
        </View>
        {ROWS.map((row) => (
          <View key={row.label} className="justify-center px-1.5 py-1 sm:px-3 sm:py-1.5">
            {/* Two lines to match the A/B stacked data rows */}
            <Text
              className="text-[10px] font-medium text-gray-500 sm:text-xs"
              numberOfLines={1}
            >
              {row.label}
            </Text>
            <Text className="text-[10px] text-transparent sm:text-xs">
              {"\u00A0"}
            </Text>
          </View>
        ))}
      </View>

      {/* Scrollable pitch type columns */}
      <ScrollView ref={scrollRef} horizontal showsHorizontalScrollIndicator={false}>
        {pitchTypeColumns.map(({ pitchType, pitchA, pitchB }) => {
          const color = PITCH_COLORS[pitchType] || DEFAULT_COLOR;
          const isHovered = hoveredPitchType === pitchType;
          return (
            <Pressable
              key={pitchType}
              onPress={() => handlePress(pitchType)}
              onLayout={(e) => { columnOffsets.current[pitchType] = e.nativeEvent.layout.x; }}
              className={isHovered ? "bg-blue-50" : ""}
            >
              {/* Header */}
              <View className="flex-row items-center justify-end gap-1.5 px-1.5 py-1 sm:px-3 sm:py-2">
                <View
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <Text
                  className="text-[10px] font-semibold text-gray-900 sm:text-xs"
                  numberOfLines={1}
                >
                  {PITCH_NAMES[pitchType] || pitchType}
                </Text>
              </View>
              {/* Data rows with stacked A/B values */}
              {ROWS.map((row) => (
                <View
                  key={row.label}
                  className="items-end px-1.5 py-1 sm:px-3 sm:py-1.5"
                >
                  <View className="flex-row items-center gap-1">
                    <View className="h-1.5 w-1.5 rounded-full bg-gray-500" />
                    <Text
                      className={`text-[10px] text-gray-900 sm:text-xs ${
                        isHovered ? "font-semibold" : ""
                      }`}
                    >
                      {pitchA ? row.fn(pitchA) : "\u2014"}
                    </Text>
                  </View>
                  <View className="flex-row items-center gap-1">
                    <View className="h-1.5 w-1.5 rounded-full border border-gray-500 bg-white" />
                    <Text
                      className={`text-[10px] text-gray-900 sm:text-xs ${
                        isHovered ? "font-semibold" : ""
                      }`}
                    >
                      {pitchB ? row.fn(pitchB) : "\u2014"}
                    </Text>
                  </View>
                </View>
              ))}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
