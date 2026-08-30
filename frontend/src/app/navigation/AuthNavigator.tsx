import {
  createNativeStackNavigator,
} from "@react-navigation/native-stack";

import {
  LoginScreen,
} from "../../features/auth/screens/LoginScreen";
import {
  SignupScreen,
} from "../../features/auth/screens/SignupScreen";

export type AuthStackParamList = {
  Login: undefined;
  Signup: undefined;
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
    </Stack.Navigator>
  );
}
