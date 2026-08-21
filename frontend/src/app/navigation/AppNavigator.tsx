import {
    createNativeStackNavigator,
} from "@react-navigation/native-stack";

import {
    MainPlaceholderScreen,
} from "../screens/MainPlaceholderScreen";

type AppStackParamList = {
  Main: undefined;
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
    </Stack.Navigator>
  );
}
