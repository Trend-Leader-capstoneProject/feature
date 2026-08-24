import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { InterestSelectScreen } from "../../features/interest/screens/InterestSelectScreen";

type OnboardingStackParamList = {
    InterestSelect: undefined;
};

const Stack =
  createNativeStackNavigator<OnboardingStackParamList>();

export function OnboardingNavigator() {
    return (
        <Stack.Navigator
            screenOptions={{
                headerShown: false,
            }}
        >
            <Stack.Screen
                name="InterestSelect"
                component={InterestSelectScreen}
            />
        </Stack.Navigator>
    );
}
