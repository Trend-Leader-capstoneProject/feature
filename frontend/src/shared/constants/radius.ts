export const radius = {
  radiusSmall: 8,
  radiusMedium: 12,
  radiusFull: 999,
} as const;

export type RadiusToken = keyof typeof radius;
