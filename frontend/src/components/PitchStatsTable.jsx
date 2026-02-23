import { useEffect, useRef } from "react";
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
 * Stats table showing all pitch types as columns with highlighted selection.
 *
 * Each pitch type is a column. Tapping a pitch type highlights that column.
 * Rows show velocity, movement, spin, and usage stats.
 *
 * @param {{ pitches: Array, hoveredPitchType: string|null, onHover: function }} props
 */
export default function PitchStatsTable({ pitches, hoveredPitchType, onHover }) {
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
        <View className="px-1.5 py-1 sm:px-3 sm:py-2">
          <Text className="text-[10px] font-medium uppercase tracking-wide text-gray-400 sm:text-xs">
            Stat
          </Text>
        </View>
        {ROWS.map((row) => (
          <View key={row.label} className="px-1.5 py-1 sm:px-3 sm:py-1.5">
            <Text
              className="text-[10px] font-medium text-gray-500 sm:text-xs"
              numberOfLines={1}
            >
              {row.label}
            </Text>
          </View>
        ))}
      </View>

      {/* Scrollable pitch type columns */}
      <ScrollView ref={scrollRef} horizontal showsHorizontalScrollIndicator={false}>
        {pitches.map((p) => {
          const color = PITCH_COLORS[p.pitch_type] || DEFAULT_COLOR;
          const isHovered = hoveredPitchType === p.pitch_type;
          return (
            <Pressable
              key={p.pitch_type}
              onPress={() => handlePress(p.pitch_type)}
              onLayout={(e) => { columnOffsets.current[p.pitch_type] = e.nativeEvent.layout.x; }}
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
                  {PITCH_NAMES[p.pitch_type] || p.pitch_type}
                </Text>
              </View>
              {/* Data rows */}
              {ROWS.map((row) => (
                <View
                  key={row.label}
                  className="px-1.5 py-1 sm:px-3 sm:py-1.5"
                >
                  <Text
                    className={`text-right text-[10px] text-gray-900 sm:text-xs ${
                      isHovered ? "font-semibold" : ""
                    }`}
                    numberOfLines={1}
                  >
                    {row.fn(p)}
                  </Text>
                </View>
              ))}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
