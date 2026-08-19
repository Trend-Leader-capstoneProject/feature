import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { RootNavigator } from "./src/app/navigation/RootNavigator";
import { AuthProvider } from "./src/app/providers/AuthProvider";
import { QueryProvider } from "./src/app/providers/QueryProvider";

export default function AppEntry() {
  return (
    <SafeAreaProvider>
      <QueryProvider>
        <AuthProvider>
          <StatusBar style="dark" />
          <RootNavigator />
        </AuthProvider>
      </QueryProvider>
    </SafeAreaProvider>
  );
}
