import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import {
    Pressable,
    Text,
    View,
} from "react-native";

import { borders, radius, sizes, spacing, typography } from "../../../shared/constants";
import type {
    TrendLatestSource,
    TrendSourcePlatform,
} from "../types/trend";


export interface TrendSourceSectionProps {
  source: TrendLatestSource | null;
  topic?: string;
  onOpenSource: (url: string) => void;
}

const INTEREST_SOURCE_URL =
  "https://trends.google.com/trending?geo=KR&hl=ko&hours=24";

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
  topic,
  onOpenSource,
}: TrendSourceSectionProps) {
  const { styles } = useStyles();
  if (source === null) {
    return (
      <Text style={styles.unavailable}>
        출처 정보가 없습니다.
      </Text>
    );
  }

  const interest =
    source.platform === "ETC" && source.source_url === INTEREST_SOURCE_URL;
  const igdb =
    source.platform === "ETC" &&
    /^https:\/\/www\.igdb\.com\/games\/[a-z0-9][a-z0-9-]{0,254}$/.test(
      source.source_url,
    );
  const godot =
    source.platform === "ETC" &&
    /^https:\/\/github\.com\/godotengine\/godot-builds\/releases\/tag\/[0-9]+\.[0-9]+(?:\.[0-9]+)?-(?:stable|beta[0-9]+|rc[0-9]+|dev[0-9]+)$/.test(
      source.source_url,
    );
  const platformLabel = interest ? "Google Trends" : igdb ? "IGDB"
    : godot ? "GitHub" : getPlatformLabel(source.platform);
  const sourceLabel = interest ? "관측 출처 보기" : "원문 보기";

  let encodedTopic: string | null = null;
  if (interest && topic?.trim()) {
    try {
      encodedTopic = encodeURIComponent(topic.trim());
    } catch {
      // A malformed title must not break the existing source link.
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.sourceCopy}>
        <Text style={styles.platform}>
          {platformLabel}
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

      {encodedTopic !== null && (
        <View style={styles.actions}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="관련 정보 검색"
            onPress={() => onOpenSource(
              `https://www.google.com/search?hl=ko&q=${encodedTopic}`,
            )}
            style={({ pressed }) => [
              styles.openButton,
              pressed && styles.pressedOpenButton,
            ]}
          >
            <Text style={styles.openButtonLabel}>관련 정보 검색</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="관련 뉴스 검색"
            onPress={() => onOpenSource(
              `https://news.google.com/search?hl=ko&gl=KR&ceid=KR%3Ako&q=${encodedTopic}`,
            )}
            style={({ pressed }) => [
              styles.openButton,
              pressed && styles.pressedOpenButton,
            ]}
          >
            <Text style={styles.openButtonLabel}>관련 뉴스 검색</Text>
          </Pressable>
        </View>
      )}

      <Pressable
        accessibilityLabel={sourceLabel}
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
          {sourceLabel}
        </Text>
      </Pressable>
    </View>
  );
}

const useStyles = createThemedStyles((colors) => ({
  container: {
    gap: spacing.space3,
  },

  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.space2,
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
}));
