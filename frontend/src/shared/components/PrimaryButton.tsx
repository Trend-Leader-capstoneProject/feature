import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type PressableProps,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";

import {
  colors,
  radius,
  sizes,
  spacing,
  textLineLimits,
  typography,
} from "../constants";

export type PrimaryButtonProps = Omit<
  PressableProps,
  "children" | "disabled" | "style"
> & {
  disabled?: boolean;
  label: string;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
};

export function PrimaryButton({
  accessibilityLabel,
  accessibilityState,
  disabled = false,
  label,
  loading = false,
  style,
  textStyle,
  ...pressableProps
}: PrimaryButtonProps) {
  const isInteractionDisabled = disabled || loading;

  return (
    <Pressable
      {...pressableProps}
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityRole="button"
      accessibilityState={{
        ...accessibilityState,
        busy: loading || accessibilityState?.busy,
        disabled: isInteractionDisabled,
      }}
      disabled={isInteractionDisabled}
      style={({ pressed }) => [
        styles.button,
        pressed &&
          !isInteractionDisabled &&
          styles.pressedButton,
        disabled && styles.disabledButton,
        style,
      ]}
    >
      <View style={styles.content}>
        {loading && (
          <ActivityIndicator
            color={colors.actionPrimaryText}
            size="small"
          />
        )}

        <Text
          numberOfLines={textLineLimits.button}
          style={[
            styles.label,
            disabled && styles.disabledLabel,
            textStyle,
          ]}
        >
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: sizes.buttonHeight,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.space5,
    borderRadius: radius.radiusMedium,
    backgroundColor: colors.actionPrimary,
  },
  pressedButton: {
    backgroundColor: colors.actionPrimaryPressed,
  },
  disabledButton: {
    backgroundColor: colors.actionDisabled,
  },
  content: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.inlineGap,
  },
  label: {
    ...typography.button,
    color: colors.actionPrimaryText,
    textAlign: "center",
  },
  disabledLabel: {
    color: colors.actionDisabledText,
  },
});
