import {
    Pressable,
    StyleSheet,
    Text,
    View,
} from "react-native";

import {
    borders,
    colors,
    radius,
    sizes,
    spacing,
    typography,
} from "../../../shared/constants";
import type {
    TrendLatestSource,
    TrendSourcePlatform,
} from "../types/trend";


export interface TrendSourceSectionProps {
  source: TrendLatestSource | null;
  onOpenSource: (url: string) => void;
}

function getPlatformLabel(
  platform: TrendSourcePlatform,
): string {
  switch (platform) {
    case "GOOGLE":
      return "Google";

    case "YOUTUBE":
      return "YouTube";

    case "SNS":
      return "SNS";

    case "ETC":
      return "기타";
  }
}

export function TrendSourceSection({
  source,
  onOpenSource,
}: TrendSourceSectionProps) {
  if (source === null) {
    return (
      <Text style={styles.unavailable}>
        출처 정보가 없습니다.
      </Text>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.sourceCopy}>
        <Text style={styles.platform}>
          {getPlatformLabel(
            source.platform,
          )}
        </Text>

        {source.source_title !== null && (
          <Text
            numberOfLines={2}
            style={styles.sourceTitle}
          >
            {source.source_title}
          </Text>
        )}
      </View>

      <Pressable
        accessibilityLabel="원문 보기"
        accessibilityRole="button"
        onPress={() =>
          onOpenSource(
            source.source_url,
          )
        }
        style={({ pressed }) => [
          styles.openButton,
          pressed &&
            styles.pressedOpenButton,
        ]}
      >
        <Text style={styles.openButtonLabel}>
          원문 보기
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.space3,
  },

  sourceCopy: {
    gap: spacing.space1,
  },

  platform: {
    ...typography.label,
    color: colors.textBrand,
  },

  sourceTitle: {
    ...typography.body,
    color: colors.textPrimary,
  },

  unavailable: {
    ...typography.body,
    color: colors.textSecondary,
  },

  openButton: {
    minHeight: sizes.touchTarget,
    alignSelf: "flex-start",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal:
      spacing.space4,
    borderWidth:
      borders.borderWidthDefault,
    borderColor:
      colors.borderStrong,
    borderRadius:
      radius.radiusMedium,
    backgroundColor:
      colors.actionSecondary,
  },

  pressedOpenButton: {
    backgroundColor:
      colors.backgroundSubtle,
  },

  openButtonLabel: {
    ...typography.button,
    color:
      colors.actionSecondaryText,
  },
});
