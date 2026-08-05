export const spacing = {
  space0: 0,
  space1: 4,
  space2: 8,
  space3: 12,
  space4: 16,
  space5: 20,
  space6: 24,
  space8: 32,
  space10: 40,
  space12: 48,

  screenGutter: 20,
  screenTopSpacing: 24,
  screenBottomSpacing: 24,
  sectionGap: 32,
  itemGap: 16,
  contentGap: 12,
  inlineGap: 8,
  controlGap: 12,
  bottomActionGap: 16,
  feedbackGap: 16,
} as const;

export type SpacingToken = keyof typeof spacing;
