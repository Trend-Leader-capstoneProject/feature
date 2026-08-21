import {
    StyleSheet,
    Text,
    View,
} from "react-native";

import {
    ScreenContainer,
} from "../../shared/components";
import {
    colors,
    spacing,
    typography,
} from "../../shared/constants";

export function MainPlaceholderScreen() {
  return (
    <ScreenContainer
      contentStyle={styles.container}
    >
      <View style={styles.content}>
        <Text
          accessibilityRole="header"
          style={styles.title}
        >
          Trend Leader
        </Text>

        <Text style={styles.description}>
          로그인 세션이 정상적으로 복원되었습니다.
          {"\n"}
          메인 트렌드 기능은 후속 작업에서
          연결합니다.
        </Text>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: "center",
  },
  content: {
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
});
