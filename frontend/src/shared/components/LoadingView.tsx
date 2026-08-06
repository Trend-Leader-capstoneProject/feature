import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import {
  colors,
  spacing,
  typography,
} from "../constants";

export type LoadingViewProps = {
  accessibilityLabel?: string;
  message?: string;
  style?: StyleProp<ViewStyle>;
};

export function LoadingView({
  accessibilityLabel,
  message,
  style,
}: LoadingViewProps) {
  const resolvedAccessibilityLabel =
    accessibilityLabel ??
    message ??
    "콘텐츠를 불러오는 중입니다.";

  return (
    <View
      accessibilityLabel={resolvedAccessibilityLabel}
      accessibilityLiveRegion="polite"
      accessibilityRole="progressbar"
      style={[styles.container, style]}
    >
      <ActivityIndicator
        color={colors.textBrand}
        size="large"
      />

      {message && (
        <Text style={styles.message}>
          {message}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.feedbackGap,
    paddingHorizontal: spacing.space4,
    paddingVertical: spacing.space8,
  },
  message: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: "center",
  },
});
