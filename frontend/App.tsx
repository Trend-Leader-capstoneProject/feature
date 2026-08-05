import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { RootNavigator } from "./src/app/navigation/RootNavigator";
import { QueryProvider } from "./src/app/providers/QueryProvider";

export default function AppEntry() {
  return (
    <SafeAreaProvider>
      <QueryProvider>
        <StatusBar style="dark" />
        <RootNavigator />
      </QueryProvider>
    </SafeAreaProvider>
  );
}