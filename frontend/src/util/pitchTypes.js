/**
 * Pitch type color and display name constants.
 *
 * Shared by PitchMovementChart and PitchStatBox to keep color coding and
 * naming consistent across the UI.
 */

/** Standard baseball analytics color mapping for pitch types. */
export const PITCH_COLORS = {
  FF: "#d32f2f",
  SI: "#8b0000",
  FC: "#f57c00",
  SL: "#fbc02d",
  ST: "#f9a825",
  CU: "#1976d2",
  KC: "#7b1fa2",
  CH: "#388e3c",
  FS: "#00897b",
  KN: "#757575",
};

/** Fallback color for unknown pitch type codes. */
export const DEFAULT_COLOR = "#9e9e9e";

/** Human-readable names for pitch type codes. */
export const PITCH_NAMES = {
  FF: "4-Seam Fastball",
  SI: "Sinker",
  FC: "Cutter",
  SL: "Slider",
  ST: "Sweeper",
  CU: "Curveball",
  KC: "Knuckle Curve",
  CH: "Changeup",
  FS: "Splitter",
  KN: "Knuckleball",
};
