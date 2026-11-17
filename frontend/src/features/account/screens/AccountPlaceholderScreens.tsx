import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { Text } from "react-native";
import type { AppStackParamList } from "../../../app/navigation/AppNavigator";
import { PrimaryButton, ScreenContainer } from "../../../shared/components";
import { useScreenReturn, type ReturnNavigation } from "../hooks/useScreenReturn";

function Page({ title, message, navigation }: { title: string; message: string; navigation: ReturnNavigation }) {
  const { styles } = useStyles();
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
const useStyles = createThemedStyles((colors) => ({ content: { gap: 24 }, title: { color: colors.textPrimary, fontSize: 24, fontWeight: "700" }, message: { color: colors.textPrimary, fontSize: 17, lineHeight: 26 } }));
