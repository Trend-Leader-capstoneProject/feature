export const motion = {
  motionFast: 120,
  motionNormal: 200,
  easingStandard: [0.2, 0, 0, 1] as const,
} as const;

export type MotionToken = keyof typeof motion;
