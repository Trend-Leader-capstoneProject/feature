import {
  createNativeStackNavigator,
} from "@react-navigation/native-stack";

import {
  LoginScreen,
} from "../../features/auth/screens/LoginScreen";
import {
  SignupScreen,
} from "../../features/auth/screens/SignupScreen";
import { LatestTrendScreen } from "../../features/trend/screens/LatestTrendScreen";

export type AuthStackParamList = {
  Login: undefined;
  Signup: undefined;
  LatestTrend: undefined;
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
        component={LatestTrendScreen}
      />

    </Stack.Navigator>
  );
}
