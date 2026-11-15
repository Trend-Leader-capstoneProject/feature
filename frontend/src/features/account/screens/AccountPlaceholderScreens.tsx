import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { StyleSheet, Text } from "react-native";
import type { AppStackParamList } from "../../../app/navigation/AppNavigator";
import { PrimaryButton, ScreenContainer } from "../../../shared/components";
import { useScreenReturn, type ReturnNavigation } from "../hooks/useScreenReturn";

function Page({ title, message, navigation }: { title: string; message: string; navigation: ReturnNavigation }) {
  const back = useScreenReturn(navigation);
  return <ScreenContainer contentStyle={styles.content}>
    <Text accessibilityRole="header" style={styles.title}>{title}</Text>
    <Text style={styles.message}>{message}</Text>
    <PrimaryButton label="돌아가기" disabled={back.disabled} onPress={back.goBack} />
  </ScreenContainer>;
}
export function MyPostsScreen({ navigation }: NativeStackScreenProps<AppStackParamList, "MyPosts">) {
  return <Page title="내 글 목록" message="목록 기능을 준비 중입니다" navigation={navigation} />;
}
export function MyCommentsScreen({ navigation }: NativeStackScreenProps<AppStackParamList, "MyComments">) {
  return <Page title="내 댓글 목록" message="목록 기능을 준비 중입니다" navigation={navigation} />;
}
export function AppSettingsScreen({ navigation }: NativeStackScreenProps<AppStackParamList, "AppSettings">) {
  return <Page title="앱 설정" message="설정 기능을 준비 중입니다" navigation={navigation} />;
}
const styles = StyleSheet.create({ content: { gap: 24 }, title: { fontSize: 24, fontWeight: "700" }, message: { fontSize: 17, lineHeight: 26 } });
