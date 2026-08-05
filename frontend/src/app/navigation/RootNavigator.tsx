import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { InterestSelectScreen } from "../../features/interest/screens/InterestSelectScreen";

export type RootStackParamList = {
    InterestSelect: undefined;
};

const Stack =
    createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
    return (
        <NavigationContainer>
            <Stack.Navigator
                initialRouteName="InterestSelect"
                screenOptions={{
                    headerShown: false,
                }}
            >
            <Stack.Screen
                name="InterestSelect"
                component={InterestSelectScreen}
            />
        </Stack.Navigator>
        </NavigationContainer>
    )
}