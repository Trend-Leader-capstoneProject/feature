import {
  useState,
} from "react";
import {
  FlatList,
  StyleSheet,
  Text,
  View,
  type ListRenderItemInfo,
} from "react-native";

import {
  ScreenContainer,
} from "../../../shared/components";
import {
  colors,
  sizes,
  spacing,
  typography,
} from "../../../shared/constants";
import {
  useCategories,
} from "../../interest/hooks/useCategories";
import {
  TrendCard,
} from "../components/TrendCard";
import {
  TrendCategoryFilter,
  type TrendCategorySelection,
} from "../components/TrendCategoryFilter";
import {
  TrendListFeedback,
} from "../components/TrendListFeedback";
import {
  useTrends,
} from "../hooks/useTrends";
import type {
  TrendListItem,
} from "../types/trend";
import {
  openTrendSourceUrl,
} from "../utils/openTrendSourceUrl";


export function LatestTrendScreen() {
  const [
    selectedRootCategoryId,
    setSelectedRootCategoryId,
  ] = useState<number | null>(null);

  const [
    selectedCategoryId,
    setSelectedCategoryId,
  ] = useState<number | null>(null);

  const {
    data: categoryData,
  } = useCategories();

  const {
    data: trendData,
    isError,
    isFetching,
    isPending,
    refetch,
  } = useTrends({
    categoryId:
      selectedCategoryId,
  });

  const categories =
    categoryData?.categories ?? [];

  const trends =
    trendData?.pages.flatMap(
      (page) => page.items,
    ) ?? [];

  const isFiltered =
    selectedCategoryId !== null;

  function handleCategorySelection(
    selection: TrendCategorySelection,
  ): void {
    setSelectedRootCategoryId(
      selection.rootCategoryId,
    );

    setSelectedCategoryId(
      selection.categoryId,
    );
  }

  function handleOpenSource(
    url: string,
  ): void {
    void openTrendSourceUrl(url);
  }

  function renderTrend({
    item,
    index,
  }: ListRenderItemInfo<TrendListItem>) {
    return (
      <TrendCard
        displayNumber={index + 1}
        onOpenSource={
          handleOpenSource
        }
        trend={item}
      />
    );
  }

  function renderContent() {
    if (isPending) {
      return (
        <TrendListFeedback
          state="loading"
        />
      );
    }

    /*
     * Cache가 존재하는 background revalidation 오류까지
     * 전체 화면 오류로 덮어쓰지 않는다.
     */
    if (
      isError &&
      trendData === undefined
    ) {
      return (
        <TrendListFeedback
          onRetry={() => {
            void refetch();
          }}
          retrying={isFetching}
          state="error"
        />
      );
    }

    if (trends.length === 0) {
      return (
        <TrendListFeedback
          filtered={isFiltered}
          state="empty"
        />
      );
    }

    return (
      <FlatList
        contentContainerStyle={
          styles.trendList
        }
        data={trends}
        keyExtractor={(item) =>
          item.trend_id.toString()
        }
        renderItem={renderTrend}
        showsVerticalScrollIndicator={
          false
        }
      />
    );
  }

  return (
    <ScreenContainer>
      <View style={styles.brandHeader}>
        <View
          style={styles.headerSlot}
        />

        <Text style={styles.brand}>
          T&L
        </Text>

        <View
          style={styles.headerSlot}
        />
      </View>

      <View style={styles.intro}>
        <Text
          accessibilityRole="header"
          style={styles.title}
        >
          최신 트렌드
        </Text>

        <Text style={styles.description}>
          최근 업데이트된 다양한 트렌드를 확인해 보세요.
        </Text>
      </View>

      <View style={styles.filterRegion}>
        <TrendCategoryFilter
          categories={categories}
          onSelectionChange={
            handleCategorySelection
          }
          selectedCategoryId={
            selectedCategoryId
          }
          selectedRootCategoryId={
            selectedRootCategoryId
          }
        />
      </View>

      <View style={styles.contentRegion}>
        {renderContent()}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  brandHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent:
      "space-between",
    marginBottom: spacing.space5,
  },

  headerSlot: {
    width: sizes.touchTarget,
    height: sizes.touchTarget,
  },

  brand: {
    ...typography.sectionTitle,
    color: colors.textBrand,
    textAlign: "center",
  },

  intro: {
    gap: spacing.contentGap,
    marginBottom: spacing.space5,
  },

  title: {
    ...typography.screenTitle,
    color: colors.textPrimary,
  },

  description: {
    ...typography.body,
    color: colors.textSecondary,
  },

  /*
   * TrendCategoryFilter가 자체 screenGutter를 갖고 있으므로
   * ScreenContainer의 padding을 한 번 상쇄한다.
   */
  filterRegion: {
    marginHorizontal:
      -spacing.screenGutter,
    marginBottom: spacing.space5,
  },

  contentRegion: {
    flex: 1,
  },

  trendList: {
    gap: spacing.itemGap,
    paddingBottom:
      spacing.screenBottomSpacing,
  },
});
