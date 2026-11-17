import {
  NavigationContainer,
  DefaultTheme,
  DarkTheme,
} from "@react-navigation/native";

import {
  useAuth,
} from "../providers/AuthProvider";
import {
  SessionRestoreErrorScreen,
} from "../screens/SessionRestoreErrorScreen";
import {
  SessionRestoreScreen,
} from "../screens/SessionRestoreScreen";
import {
  AppNavigator,
} from "./AppNavigator";
import {
  AuthNavigator,
} from "./AuthNavigator";
import {
  OnboardingNavigator,
} from "./OnboardingNavigator";

import { useAppTheme } from "../../shared/theme/ThemeProvider";

export function RootNavigator() {
  const { colors, scheme } = useAppTheme();
  const baseTheme = scheme === "dark" ? DarkTheme : DefaultTheme;
  const navigationTheme = { ...baseTheme, colors: { ...baseTheme.colors,
    primary: colors.textBrand, background: colors.backgroundCanvas,
    card: colors.backgroundSurface, text: colors.textPrimary,
    border: colors.borderDefault, notification: colors.statusNegative,
  } };
  const {
    authState,
  } = useAuth();

  if (
    authState.status === "RESTORING"
  ) {
    return <SessionRestoreScreen />;
  }

  if (
    authState.status === "RESTORE_ERROR"
  ) {
    return (
      <SessionRestoreErrorScreen />
    );
  }

  return (
    <NavigationContainer theme={navigationTheme}>
      {authState.status ===
      "UNAUTHENTICATED" ? (
        <AuthNavigator />
      ) : authState.session.next_step ===
        "INTEREST_SELECTION" ? (
        <OnboardingNavigator />
      ) : (
        <AppNavigator />
      )}
    </NavigationContainer>
  );
}
