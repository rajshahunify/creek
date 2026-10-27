import type { Modifier } from "@dnd-kit/core";

/** Queue rows only move up and down. */
export const restrictToVerticalAxis: Modifier = ({ transform }) => ({ ...transform, x: 0 });
