import { createThemedStyles } from "../theme/createThemedStyles";
import type { PropsWithChildren } from "react";
import {
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import {
  SafeAreaView,
  type Edge,
} from "react-native-safe-area-context";

import { spacing } from "../constants";

export type ScreenContainerProps = PropsWithChildren<{
  contentStyle?: StyleProp<ViewStyle>;
  edges?: readonly Edge[];
  style?: StyleProp<ViewStyle>;
}>;

export function ScreenContainer({
  children,
  contentStyle,
  edges,
  style,
}: ScreenContainerProps) {
  const { styles } = useStyles();
  return (
    <SafeAreaView
      edges={edges}
      style={[styles.safeArea, style]}
    >
      <View style={[styles.content, contentStyle]}>
        {children}
      </View>
    </SafeAreaView>
  );
}

const useStyles = createThemedStyles((colors) => ({
  safeArea: {
    flex: 1,
    backgroundColor: colors.backgroundCanvas,
  },
  content: {
    flex: 1,
    paddingHorizontal: spacing.screenGutter,
    paddingTop: spacing.screenTopSpacing,
    paddingBottom: spacing.screenBottomSpacing,
  },
}));
