import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import {
    Pressable,
    Text,
    View,
} from "react-native";

import { borders, radius, sizes, spacing, typography } from "../../../shared/constants";
import type {
    TrendLatestSource,
    TrendRelatedArticle,
    TrendSourcePlatform,
} from "../types/trend";


export interface TrendSourceSectionProps {
  source: TrendLatestSource | null;
  topic?: string;
  relatedArticles?: TrendRelatedArticle[];
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

// Defense in depth for API data: this is not a publisher-rights decision.
// The Writer and API own approval and freshness policy.
function visibleArticles(value: unknown): TrendRelatedArticle[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const result: TrendRelatedArticle[] = [];
  const urls = new Set<string>();

  for (const article of value) {
    if (
      !article || typeof article !== "object" ||
      typeof article.publisher !== "string" ||
      !article.publisher.trim() || article.publisher.length > 255 ||
      (article.title !== null &&
        (typeof article.title !== "string" || !article.title.trim() ||
          article.title.length > 255)) ||
      typeof article.url !== "string" || article.url.length > 2048 ||
      typeof article.published_at !== "string" ||
      !/(?:Z|[+-]00:00)$/.test(article.published_at) ||
      Number.isNaN(Date.parse(article.published_at))
    ) {
      continue;
    }

    // Accept the canonical HTTPS host/path form emitted by the Writer.
    // Do not interpret credentials, query strings, fragments or escaped paths.
    const match = /^https:\/\/([a-z0-9.-]+)\/(.+)$/.exec(article.url);
    if (!match) {
      continue;
    }
    const [, host, path] = match;
    if (
      !host.includes(".") ||
      !host.split(".").every((label) =>
        /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)) ||
      !/[a-z]/.test(host.split(".").at(-1) ?? "") ||
      host.endsWith(".localhost") || host.endsWith(".local") ||
      host.endsWith(".internal") ||
      !path.split("/").every((part) =>
        /^[A-Za-z0-9._~-]+$/.test(part) &&
        ![".", "..", "redirect", "goto", "out", "forward"].includes(
          part.toLowerCase(),
        )) ||
      urls.has(article.url)
    ) {
      continue;
    }

    urls.add(article.url);
    result.push(article);
    if (result.length === 2) {
      break;
    }
  }
  return result;
}

function formatPublishedAt(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function TrendSourceSection({
  source,
  topic,
  relatedArticles,
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
  const articles = interest ? visibleArticles(relatedArticles) : [];

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
          {articles.length === 0 && (
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
          )}
        </View>
      )}

      {articles.length > 0 && (
        <View style={styles.articles}>
          <Text style={styles.platform}>관련 뉴스</Text>
          <Text style={styles.articleMeta}>참고 기사 · 검색 상승 원인과는 별개</Text>
          {articles.map((article, index) => (
            <Pressable
              key={article.url}
              accessibilityRole="button"
              accessibilityLabel={`${article.publisher} 기사 보기 ${index + 1}`}
              onPress={() => onOpenSource(article.url)}
              style={({ pressed }) => [
                styles.articleButton,
                pressed && styles.pressedOpenButton,
              ]}
            >
              {article.title !== null && (
                <Text numberOfLines={2} style={styles.sourceTitle}>
                  {article.title}
                </Text>
              )}
              <Text style={styles.articleMeta}>
                {article.publisher} · {formatPublishedAt(article.published_at)}
              </Text>
              <Text style={styles.openButtonLabel}>기사 보기</Text>
            </Pressable>
          ))}
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

  articles: {
    gap: spacing.space2,
  },

  articleButton: {
    minHeight: sizes.touchTarget,
    gap: spacing.space1,
    padding: spacing.space3,
    borderWidth: borders.borderWidthDefault,
    borderColor: colors.borderDefault,
    borderRadius: radius.radiusMedium,
    backgroundColor: colors.actionSecondary,
  },

  articleMeta: {
    ...typography.caption,
    color: colors.textSecondary,
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
