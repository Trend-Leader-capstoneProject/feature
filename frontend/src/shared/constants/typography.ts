import type { TextStyle } from "react-native";

export type TypographyTokenName =
  | "display"
  | "screenTitle"
  | "sectionTitle"
  | "itemTitle"
  | "body"
  | "bodyStrong"
  | "caption"
  | "label"
  | "button"
  | "dataRank"
  | "dataDelta"
  | "input";

export type TypographyToken = Pick<
  TextStyle,
  | "fontSize"
  | "lineHeight"
  | "fontWeight"
  | "letterSpacing"
  | "fontVariant"
>;

export const typography: Record<
  TypographyTokenName,
  TypographyToken
> = {
  display: {
    fontSize: 32,
    lineHeight: 40,
    fontWeight: "700",
    letterSpacing: -0.4,
  },
  screenTitle: {
    fontSize: 26,
    lineHeight: 34,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
  sectionTitle: {
    fontSize: 20,
    lineHeight: 28,
    fontWeight: "700",
    letterSpacing: -0.1,
  },
  itemTitle: {
    fontSize: 17,
    lineHeight: 24,
    fontWeight: "600",
    letterSpacing: 0,
  },
  body: {
    fontSize: 15,
    lineHeight: 22,
    fontWeight: "400",
    letterSpacing: 0,
  },
  bodyStrong: {
    fontSize: 15,
    lineHeight: 22,
    fontWeight: "600",
    letterSpacing: 0,
  },
  caption: {
    fontSize: 13,
    lineHeight: 18,
    fontWeight: "400",
    letterSpacing: 0,
  },
  label: {
    fontSize: 13,
    lineHeight: 18,
    fontWeight: "600",
    letterSpacing: 0.1,
  },
  button: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: "700",
    letterSpacing: 0,
  },
  dataRank: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "700",
    letterSpacing: -0.3,
    fontVariant: ["tabular-nums"],
  },
  dataDelta: {
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "600",
    letterSpacing: 0,
    fontVariant: ["tabular-nums"],
  },
  input: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: "400",
    letterSpacing: 0,
  },
};

export const textLineLimits = {
  display: 2,
  screenTitle: 2,
  sectionTitle: 2,
  itemTitle: 2,
  caption: 2,
  label: 1,
  button: 1,
  dataRank: 1,
  dataDelta: 1,
} as const;
