export function isStageAdvanceDrag(delta: { x: number; y: number }, target: string | null, current: string, next?: string): boolean {
  if (!next) return false;
  if (target === next) return true;
  return (!target || target === current) && delta.x >= 100 && delta.x > Math.abs(delta.y) * 1.5;
}
