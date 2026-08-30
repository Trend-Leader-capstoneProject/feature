import type {
    NativeStackScreenProps,
} from "@react-navigation/native-stack";
import {
    Pressable,
    StyleSheet,
    Text,
    View,
} from "react-native";

import type {
    AuthStackParamList,
} from "../../../app/navigation/AuthNavigator";
import {
    ScreenContainer,
} from "../../../shared/components";
import {
    colors,
    spacing,
    typography,
} from "../../../shared/constants";

type SignupScreenProps =
  NativeStackScreenProps<
    AuthStackParamList,
    "Signup"
  >;

export function SignupScreen({
  navigation,
}: SignupScreenProps) {
  return (
    <ScreenContainer>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text
            accessibilityRole="header"
            style={styles.title}
          >
            회원가입
          </Text>

          <Text style={styles.description}>
            Trend Leader 계정을 만들어
            관심 분야의 트렌드를 확인해 보세요.
          </Text>
        </View>

        <Pressable
          accessibilityRole="button"
          hitSlop={8}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.loginLink}>
            로그인으로 돌아가기
          </Text>
        </Pressable>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    gap: spacing.sectionGap,
  },
  header: {
    gap: spacing.contentGap,
  },
  title: {
    ...typography.screenTitle,
    color: colors.textPrimary,
  },
  description: {
    ...typography.body,
    color: colors.textSecondary,
  },
  loginLink: {
    ...typography.bodyStrong,
    color: colors.textLink,
  },
});
