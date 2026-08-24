import {
  NavigationContainer,
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

export function RootNavigator() {
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
    <NavigationContainer>
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
