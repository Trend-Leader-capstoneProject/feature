import {
  createNativeStackNavigator,
} from "@react-navigation/native-stack";

import {
  MainPlaceholderScreen,
} from "../screens/MainPlaceholderScreen";

import {
  InterestEditScreen,
} from "../../features/interest/screens/InterestEditScreen";

export type AppStackParamList = {
  Main: undefined;
  InterestEdit: undefined;
};

const Stack =
  createNativeStackNavigator<AppStackParamList>();

export function AppNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen
        name="Main"
        component={MainPlaceholderScreen}
      />

      <Stack.Screen
        name="InterestEdit"
        component={InterestEditScreen}
      />

    </Stack.Navigator>
  );
}
