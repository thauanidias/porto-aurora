import { describe, expect, it } from "vitest";
import { isStageAdvanceDrag } from "./stageDrag";

describe("advance by dragging", () => {
  it("accepts a deliberate right drag or a drop on the next stage", () => {
    expect(isStageAdvanceDrag({ x: 120, y: 15 }, "current", "current", "next")).toBe(true);
    expect(isStageAdvanceDrag({ x: 0, y: 100 }, "next", "current", "next")).toBe(true);
  });
  it("ignores scrolling, short gestures, backwards drags and other destinations", () => {
    for (const delta of [{ x: 20, y: 0 }, { x: 110, y: 150 }, { x: -150, y: 0 }]) {
      expect(isStageAdvanceDrag(delta, null, "current", "next")).toBe(false);
    }
    expect(isStageAdvanceDrag({ x: 150, y: 0 }, "other", "current", "next")).toBe(false);
    expect(isStageAdvanceDrag({ x: 150, y: 0 }, null, "current")).toBe(false);
  });
});
