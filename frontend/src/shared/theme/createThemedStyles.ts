import { StyleSheet } from "react-native";
import { colors, darkColors, type ThemeColors } from "../constants/colors";
import { useAppTheme } from "./ThemeProvider";

// Build each palette once; components still subscribe to context changes.
export function createThemedStyles<T extends StyleSheet.NamedStyles<T>>(factory: (palette: ThemeColors) => T) {
  const light = StyleSheet.create(factory(colors));
  const dark = StyleSheet.create(factory(darkColors));
  return function useThemedStyles() {
    const theme = useAppTheme();
    return { styles: theme.scheme === "dark" ? dark : light, colors: theme.colors, scheme: theme.scheme };
  };
}
