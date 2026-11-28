import {
  createNativeStackNavigator,
} from "@react-navigation/native-stack";

import {
  LoginScreen,
} from "../../features/auth/screens/LoginScreen";
import {
  SignupScreen,
} from "../../features/auth/screens/SignupScreen";
import { LatestTrendRoute } from "../../features/trend/screens/LatestTrendScreen";
import { AppSettingsScreen, AppInfoScreen, HelpSupportScreen } from "../../features/settings/screens/SettingsScreens";

export type AuthStackParamList = {
  Login: undefined;
  Signup: undefined;
  LatestTrend: undefined;
  AppSettings: undefined;
  AppInfo: undefined;
  HelpSupport: undefined;
};

const Stack =
  createNativeStackNavigator<AuthStackParamList>();

export function AuthNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen
        name="Login"
        component={LoginScreen}
      />

      <Stack.Screen
        name="Signup"
        component={SignupScreen}
      />

      <Stack.Screen
        name="LatestTrend"
        component={LatestTrendRoute}
      />

      <Stack.Screen name="AppSettings" component={AppSettingsScreen} />
      <Stack.Screen name="AppInfo" component={AppInfoScreen} />
      <Stack.Screen name="HelpSupport" component={HelpSupportScreen} />

    </Stack.Navigator>
  );
}
