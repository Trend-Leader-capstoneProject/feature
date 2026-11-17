const colorPrimitives = {
  neutral0: "#FFFFFF",
  neutral50: "#FAF9F7",
  neutral100: "#F4F2EE",
  neutral200: "#E5E1DA",
  neutral300: "#CDC8BF",
  neutral400: "#A39E95",
  neutral500: "#767168",
  neutral700: "#47433D",
  neutral900: "#171612",

  indigo100: "#E4E8FF",
  indigo200: "#BCC5FF",
  indigo400: "#8E9DFF",
  indigo500: "#7789F6",
  indigo700: "#3B4CA8",
  indigo900: "#1414BC",

  signalYellow: "#FFDD55",
  signalYellowSubtle: "#FFF5C2",

  positive100: "#E8F6EF",
  positive700: "#147A52",

  negative100: "#FDECEA",
  negative500: "#FF543E",
  negative700: "#B42318",

  warning100: "#FFF4D6",
  warning700: "#8A5A00",

  information100: "#EAF2FC",
  information700: "#2F6FBE",
} as const;

export const colors = {
  backgroundCanvas: colorPrimitives.neutral50,
  backgroundSurface: colorPrimitives.neutral0,
  backgroundSubtle: colorPrimitives.neutral100,
  backgroundSelected: colorPrimitives.indigo100,
  backgroundBrandMuted: colorPrimitives.indigo200,
  backgroundSignal: colorPrimitives.signalYellow,
  backgroundDisabled: colorPrimitives.neutral100,

  textPrimary: colorPrimitives.neutral900,
  textSecondary: colorPrimitives.neutral500,
  textStrongSecondary: colorPrimitives.neutral700,
  textDisabled: colorPrimitives.neutral400,
  textInverse: colorPrimitives.neutral0,
  textBrand: colorPrimitives.indigo700,
  textLink: colorPrimitives.indigo900,
  textOnPrimary: colorPrimitives.neutral900,
  textOnSignal: colorPrimitives.neutral900,

  borderDefault: colorPrimitives.neutral200,
  borderStrong: colorPrimitives.neutral300,
  borderSelected: colorPrimitives.indigo700,
  borderError: colorPrimitives.negative700,
  dividerDefault: colorPrimitives.neutral200,
  focusRing: colorPrimitives.indigo900,

  actionPrimary: colorPrimitives.indigo400,
  actionPrimaryPressed: colorPrimitives.indigo500,
  actionPrimaryText: colorPrimitives.neutral900,
  actionSecondary: colorPrimitives.neutral0,
  actionSecondaryText: colorPrimitives.indigo700,
  actionDisabled: colorPrimitives.neutral200,
  actionDisabledText: colorPrimitives.neutral400,

  statusPositive: colorPrimitives.positive700,
  statusPositiveSubtle: colorPrimitives.positive100,
  statusNegative: colorPrimitives.negative700,
  statusNegativeSubtle: colorPrimitives.negative100,
  statusWarning: colorPrimitives.warning700,
  statusWarningSubtle: colorPrimitives.warning100,
  statusInformation: colorPrimitives.information700,
  statusInformationSubtle: colorPrimitives.information100,

  signalHighlight: colorPrimitives.signalYellow,
  signalHighlightSubtle: colorPrimitives.signalYellowSubtle,
} as const;

export type ColorToken = keyof typeof colors;
export type ThemeColors = Record<ColorToken, string>;
export const darkColors: ThemeColors = {
  backgroundCanvas: "#14151B", backgroundSurface: "#1E2029", backgroundSubtle: "#292C38",
  backgroundSelected: "#303959", backgroundBrandMuted: "#414A75", backgroundSignal: "#FFDD55",
  backgroundDisabled: "#292C38",
  textPrimary: "#F1F2F7", textSecondary: "#B3B7C6", textStrongSecondary: "#D5D8E3",
  textDisabled: "#858C9E", textInverse: "#FFFFFF", textBrand: "#BBC5FF", textLink: "#BBC5FF",
  textOnPrimary: "#171612", textOnSignal: "#171612",
  borderDefault: "#3B4050", borderStrong: "#596176", borderSelected: "#AEBBFF",
  borderError: "#FFAEA5", dividerDefault: "#3B4050", focusRing: "#C0CAFF",
  actionPrimary: "#A8B5FF", actionPrimaryPressed: "#8E9DFF", actionPrimaryText: "#171612",
  actionSecondary: "#1E2029", actionSecondaryText: "#BBC5FF",
  actionDisabled: "#343846", actionDisabledText: "#9198AB",
  statusPositive: "#8FE0BA", statusPositiveSubtle: "#163B2D",
  statusNegative: "#FFAEA5", statusNegativeSubtle: "#492623",
  statusWarning: "#FFD684", statusWarningSubtle: "#41351C",
  statusInformation: "#9FCAFF", statusInformationSubtle: "#203851",
  signalHighlight: "#FFDD55", signalHighlightSubtle: "#433A1B",
};
