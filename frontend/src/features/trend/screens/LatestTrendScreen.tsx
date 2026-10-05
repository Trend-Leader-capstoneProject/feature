import { useRef, useState } from "react";
import {
  FlatList,
  Image,
  StyleSheet,
  Text,
  View,
  type ListRenderItemInfo,
} from "react-native";

import {
  appImages,
} from "../../../assets";

import {
  ErrorView,
  LoadingView,
  ScreenContainer,
} from "../../../shared/components";
import { colors, sizes, spacing, typography } from "../../../shared/constants";
import { useCategories } from "../../interest/hooks/useCategories";
import { TrendCard } from "../components/TrendCard";
import {
  TrendCategoryFilter,
  type TrendCategorySelection,
} from "../components/TrendCategoryFilter";
import { TrendListFeedback } from "../components/TrendListFeedback";
import { useTrends } from "../hooks/useTrends";
import type { TrendListItem } from "../types/trend";
import { openTrendSourceUrl } from "../utils/openTrendSourceUrl";

export function LatestTrendScreen() {
  const [selectedRootCategoryId, setSelectedRootCategoryId] = useState<
    number | null
  >(null);

  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(
    null,
  );

  const [
    isRefreshing,
    setIsRefreshing,
  ] = useState(false);

  const nextPageRequestKeyRef = useRef<string | null>(null);

  const { data: categoryData } = useCategories();

  const {
    data: trendData,
    fetchNextPage,
    hasNextPage,
    isError,
    isFetchNextPageError,
    isFetching,
    isFetchingNextPage,
    isPending,
    refetch,
    restart,
  } = useTrends({
    categoryId: selectedCategoryId,
  });

  const categories = categoryData?.categories ?? [];

  const trends = trendData?.pages.flatMap((page) => page.items) ?? [];

  const isFiltered = selectedCategoryId !== null;

  const lastPage = trendData?.pages[(trendData?.pages.length ?? 1) - 1];

  const nextCursor = lastPage?.next_cursor ?? null;

  function handleCategorySelection(selection: TrendCategorySelection): void {
    setSelectedRootCategoryId(selection.rootCategoryId);

    setSelectedCategoryId(selection.categoryId);
  }

  function handleOpenSource(url: string): void {
    void openTrendSourceUrl(url);
  }

  function handleRefresh(): void {
    if (isRefreshing) {
      return;
    }

    setIsRefreshing(true);

    void restart()
      .catch(() => undefined)
      .finally(() => {
        setIsRefreshing(false);
      });
  }
  function renderTrend({ item, index }: ListRenderItemInfo<TrendListItem>) {
    return (
      <TrendCard
        displayNumber={index + 1}
        onOpenSource={handleOpenSource}
        trend={item}
      />
    );
  }

  function renderListFooter() {
    if (isFetchingNextPage) {
      return (
        <LoadingView
          accessibilityLabel="다음 트렌드를 불러오는 중입니다."
          style={styles.nextPageFeedback}
        />
      );
    }

    if (isFetchNextPageError) {
      return (
        <ErrorView
          onRetry={handleRetryNextPage}
          retrying={isFetchingNextPage}
          style={styles.nextPageFeedback}
          title="다음 트렌드를 불러오지 못했습니다."
        />
      );
    }

    return null;
  }

  function renderContent() {
    if (isPending) {
      return <TrendListFeedback state="loading" />;
    }

    /*
     * Cache가 존재하는 background revalidation 오류까지
     * 전체 화면 오류로 덮어쓰지 않는다.
     */
    if (isError && trendData === undefined) {
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
      return <TrendListFeedback filtered={isFiltered} state="empty" />;
    }

    return (
      <FlatList
        contentContainerStyle={styles.trendList}
        data={trends}
        keyExtractor={(item) =>
          item.trend_id.toString()
        }
        ListFooterComponent={
          renderListFooter
        }
        onEndReached={
          handleEndReached
        }
        onEndReachedThreshold={0.4}
        onRefresh={
          handleRefresh
        }
        refreshing={
          isRefreshing
        }
        renderItem={renderTrend}
        showsVerticalScrollIndicator={
          false
        }
        testID="trend-list"
      />
    );
  }

  function requestNextPage(): void {
    if (!hasNextPage || nextCursor === null || isFetchingNextPage) {
      return;
    }

    const requestKey = `${selectedCategoryId ?? "all"}:${nextCursor}`;

    if (nextPageRequestKeyRef.current === requestKey) {
      return;
    }

    nextPageRequestKeyRef.current = requestKey;

    void fetchNextPage().finally(() => {
      if (nextPageRequestKeyRef.current === requestKey) {
        nextPageRequestKeyRef.current = null;
      }
    });
  }

  function handleEndReached(): void {
    /*
     * 실패 직후 FlatList가 다시 onEndReached를 발생시켜
     * 자동 Retry하지 않도록 한다.
     */
    if (isFetchNextPageError) {
      return;
    }

    requestNextPage();
  }

  function handleRetryNextPage(): void {
    requestNextPage();
  }

  return (
    <ScreenContainer>
      <View style={styles.brandHeader}>
        <View style={styles.headerSlot} />

        <Image
          accessibilityLabel="Trend Leader"
          accessible
          resizeMode="contain"
          source={appImages.trendLeaderLogo}
          style={styles.brandLogo}
        />

        <View style={styles.headerSlot} />
      </View>

      <View style={styles.intro}>
        <Text accessibilityRole="header" style={styles.title}>
          최신 트렌드
        </Text>

        <Text style={styles.description}>
          최근 업데이트된 다양한 트렌드를 확인해 보세요.
        </Text>
      </View>

      <View style={styles.filterRegion}>
        <TrendCategoryFilter
          categories={categories}
          onSelectionChange={handleCategorySelection}
          selectedCategoryId={selectedCategoryId}
          selectedRootCategoryId={selectedRootCategoryId}
        />
      </View>

      <View style={styles.contentRegion}>{renderContent()}</View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  brandHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.space5,
  },

  headerSlot: {
    width: sizes.touchTarget,
    height: sizes.touchTarget,
  },

  brandLogo: {
    width: sizes.touchTarget,
    height: sizes.touchTarget,
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
    marginHorizontal: -spacing.screenGutter,
    marginBottom: spacing.space5,
  },

  contentRegion: {
    flex: 1,
  },

  trendList: {
    gap: spacing.itemGap,
    paddingBottom: spacing.screenBottomSpacing,
  },

  nextPageFeedback: {
    paddingVertical: spacing.space4,
  },
});
