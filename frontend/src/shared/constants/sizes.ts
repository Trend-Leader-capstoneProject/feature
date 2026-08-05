export const sizes = {
  touchTarget: 44,
  buttonHeight: 52,
  inputHeight: 48,
  compactControlHeight: 40,
  iconSmall: 16,
  iconMedium: 20,
  iconLarge: 24,
  dividerHeight: 1,
} as const;

export type SizeToken = keyof typeof sizes;
