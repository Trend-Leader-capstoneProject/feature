import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import {
  borders,
  colors,
  radius,
  sizes,
  spacing,
  textLineLimits,
  typography,
} from "../constants";

export type ErrorViewProps = {
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
  retrying?: boolean;
  style?: StyleProp<ViewStyle>;
  title: string;
};

export function ErrorView({
  message,
  onRetry,
  retryLabel = "다시 시도",
  retrying = false,
  style,
  title,
}: ErrorViewProps) {
  return (
    <View style={[styles.container, style]}>
      <View
        accessible
        accessibilityLabel={
          message ? `${title}. ${message}` : title
        }
        accessibilityLiveRegion="assertive"
        accessibilityRole="alert"
        style={styles.copy}
      >
        <Text style={styles.title}>
          {title}
        </Text>

        {message && (
          <Text style={styles.message}>
            {message}
          </Text>
        )}
      </View>

      {onRetry && (
        <Pressable
          accessibilityLabel={retryLabel}
          accessibilityRole="button"
          accessibilityState={{
            busy: retrying,
            disabled: retrying,
          }}
          disabled={retrying}
          onPress={onRetry}
          style={({ pressed }) => [
            styles.retryButton,
            pressed &&
              !retrying &&
              styles.pressedRetryButton,
          ]}
        >
          <View style={styles.retryContent}>
            {retrying && (
              <ActivityIndicator
                color={colors.actionSecondaryText}
                size="small"
              />
            )}

            <Text
              numberOfLines={textLineLimits.button}
              style={styles.retryLabel}
            >
              {retryLabel}
            </Text>
          </View>
        </Pressable>
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
  copy: {
    alignItems: "center",
    gap: spacing.inlineGap,
  },
  title: {
    ...typography.bodyStrong,
    color: colors.statusNegative,
    textAlign: "center",
  },
  message: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: "center",
  },
  retryButton: {
    minHeight: sizes.touchTarget,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.space4,
    borderWidth: borders.borderWidthDefault,
    borderColor: colors.borderStrong,
    borderRadius: radius.radiusMedium,
    backgroundColor: colors.actionSecondary,
  },
  pressedRetryButton: {
    backgroundColor: colors.backgroundSubtle,
  },
  retryContent: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.inlineGap,
  },
  retryLabel: {
    ...typography.button,
    color: colors.actionSecondaryText,
    textAlign: "center",
  },
});
