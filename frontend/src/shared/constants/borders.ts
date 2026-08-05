export const borders = {
  borderWidthDefault: 1,
  borderWidthStrong: 2,
} as const;

export const elevations = {
  elevationNone: 0,
  elevationRaised: 2,
} as const;

export type BorderToken = keyof typeof borders;
export type ElevationToken = keyof typeof elevations;
