import {
  createNativeStackNavigator,
} from "@react-navigation/native-stack";

import {
  PersonalizedMainScreen,
} from "../screens/PersonalizedMainScreen";

import {
  InterestEditScreen,
} from "../../features/interest/screens/InterestEditScreen";
import { LatestTrendScreen } from "../../features/trend/screens/LatestTrendScreen";
import { IgdbDevPreviewScreen } from "../../features/trend/screens/IgdbDevPreviewScreen";

import { MyInfoScreen } from "../../features/account/screens/MyInfoScreen";
import { PasswordChangeScreen } from "../../features/account/screens/PasswordChangeScreen";
import { MyPostsScreen, MyCommentsScreen } from "../../features/account/screens/AccountPlaceholderScreens";
import { AppSettingsScreen, AppInfoScreen, HelpSupportScreen } from "../../features/settings/screens/SettingsScreens";

export type AppStackParamList = {
  MyInfo: undefined;
  PasswordChange: undefined;
  MyPosts: undefined;
  MyComments: undefined;
  AppSettings: undefined;
  AppInfo: undefined;
  HelpSupport: undefined;
  Main: undefined;
  InterestEdit: undefined;
  LatestTrend: undefined;
  IgdbPreview: undefined;
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
        component={PersonalizedMainScreen}
      />

      <Stack.Screen
        name="InterestEdit"
        component={InterestEditScreen}
      />

      <Stack.Screen
        name="LatestTrend"
        component={LatestTrendScreen}
      />

      {__DEV__ && (
        <Stack.Screen name="IgdbPreview" component={IgdbDevPreviewScreen} />
      )}

      <Stack.Screen name="MyInfo" component={MyInfoScreen} />
      <Stack.Screen name="PasswordChange" component={PasswordChangeScreen} />
      <Stack.Screen name="MyPosts" component={MyPostsScreen} />
      <Stack.Screen name="MyComments" component={MyCommentsScreen} />
      <Stack.Screen name="AppSettings" component={AppSettingsScreen} />
      <Stack.Screen name="AppInfo" component={AppInfoScreen} />
      <Stack.Screen name="HelpSupport" component={HelpSupportScreen} />
    </Stack.Navigator>
  );
}
