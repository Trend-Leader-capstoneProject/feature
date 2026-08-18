import {
    NavigationContainer,
} from "@react-navigation/native";
import {
    createNativeStackNavigator,
} from "@react-navigation/native-stack";

import { LoginScreen } from "../../features/auth/screens/LoginScreen";
import { InterestSelectScreen } from "../../features/interest/screens/InterestSelectScreen";

export type RootStackParamList = {
  Login: undefined;
  InterestSelect: undefined;
};

const Stack =
  createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName="Login"
        screenOptions={{
          headerShown: false,
        }}
      >
        <Stack.Screen
          name="Login"
          component={LoginScreen}
        />

        <Stack.Screen
          name="InterestSelect"
          component={InterestSelectScreen}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}