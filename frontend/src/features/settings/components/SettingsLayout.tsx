import type { PropsWithChildren } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { ScreenContainer } from "../../../shared/components";
import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import { typography } from "../../../shared/constants";

type Props = PropsWithChildren<{ title: string; onBack: () => void; disabled: boolean }>;
export function SettingsLayout({ title, onBack, disabled, children }: Props) {
  const { styles } = useStyles();
  return <ScreenContainer contentStyle={styles.container}>
    <View style={styles.header}>
      <Pressable accessibilityRole="button" accessibilityLabel="돌아가기"
        accessibilityState={{ disabled }} disabled={disabled} onPress={onBack} style={styles.back}>
        <Text style={styles.arrow}>←</Text>
      </Pressable>
      <Text accessibilityRole="header" style={styles.title}>{title}</Text>
      <View style={styles.spacer} />
    </View>
    <ScrollView contentContainerStyle={styles.content}>{children}</ScrollView>
  </ScreenContainer>;
}
const useStyles = createThemedStyles(colors => ({
  container: { paddingHorizontal: 0, paddingTop: 0, paddingBottom: 0 },
  header: { flexDirection: "row", alignItems: "center", minHeight: 60, borderBottomWidth: 1, borderColor: colors.dividerDefault, backgroundColor: colors.backgroundSurface },
  back: { width: 56, minHeight: 52, alignItems: "center", justifyContent: "center" },
  arrow: { fontSize: 28, color: colors.textLink },
  title: { ...typography.itemTitle, color: colors.textPrimary, textAlign: "center", flex: 1 },
  spacer: { width: 56 },
  content: { padding: 20, paddingBottom: 40, gap: 20 },
}));
