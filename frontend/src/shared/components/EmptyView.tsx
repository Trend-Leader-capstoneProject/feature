import { createThemedStyles } from "../theme/createThemedStyles";
import {
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { spacing, typography } from "../constants";

export type EmptyViewProps = {
  message?: string;
  style?: StyleProp<ViewStyle>;
  title: string;
};

export function EmptyView({
  message,
  style,
  title,
}: EmptyViewProps) {
  const { styles } = useStyles();
  return (
    <View
      accessibilityLiveRegion="polite"
      style={[styles.container, style]}
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
  );
}

const useStyles = createThemedStyles((colors) => ({
  container: {
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.inlineGap,
    paddingHorizontal: spacing.space4,
    paddingVertical: spacing.space8,
  },
  title: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
    textAlign: "center",
  },
  message: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: "center",
  },
}));
