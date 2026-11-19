import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { View } from "react-native";
import * as SystemUI from "expo-system-ui";
import { ThemeProvider, useAppTheme } from "./src/shared/theme/ThemeProvider";
import { SessionRestoreScreen } from "./src/app/screens/SessionRestoreScreen";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { RootNavigator } from "./src/app/navigation/RootNavigator";
import { AuthProvider } from "./src/app/providers/AuthProvider";
import { QueryProvider } from "./src/app/providers/QueryProvider";

function ThemedApp() {
  const { colors, scheme, ready } = useAppTheme();
  const [hasRestored, setHasRestored] = useState(false);
  useEffect(() => { if (ready) setHasRestored(true); }, [ready]);
  useEffect(() => {
    void SystemUI.setBackgroundColorAsync(colors.backgroundCanvas).catch(() => undefined);
  }, [colors.backgroundCanvas]);
  return <View style={{ flex: 1, backgroundColor: colors.backgroundCanvas }}>
    <StatusBar style={scheme === "dark" ? "light" : "dark"} />
    {hasRestored || ready ? <RootNavigator /> : <SessionRestoreScreen />}
  </View>;
}

export default function AppEntry() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <QueryProvider>
          <AuthProvider>
            <ThemedApp />
          </AuthProvider>
        </QueryProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
