import { useRef, useState } from "react";
import { FlatList, StyleSheet, type ListRenderItemInfo } from "react-native";

import {
  EmptyView,
  ErrorView,
  LoadingView,
} from "../../../shared/components";
import { spacing } from "../../../shared/constants";
import { TrendCard } from "./TrendCard";
import { useTrends } from "../hooks/useTrends";
import type { TrendListItem } from "../types/trend";
import { openTrendSourceUrl } from "../utils/openTrendSourceUrl";

interface FilteredPersonalizedTrendListProps {
  categoryId: number;
}

/**
 * An explicitly selected interest category uses the existing public
 * category-filtered endpoint. No personalized cursor is reused here.
 */
export function FilteredPersonalizedTrendList({
  categoryId,
}: FilteredPersonalizedTrendListProps) {
  const {
    data,
    isPending,
    isError,
    isFetching,
    isFetchingNextPage,
    isFetchNextPageError,
    hasNextPage,
    fetchNextPage,
    refetch,
    restart,
  } = useTrends({ categoryId });

  const [refreshing, setRefreshing] = useState(false);
  const refreshInFlight = useRef(false);
  const nextPageInFlight = useRef<string | null>(null);

  const items = data?.pages.flatMap((page) => page.items) ?? [];
  const lastPage = data?.pages[data.pages.length - 1];
  const cursor = lastPage?.next_cursor ?? null;

  function refresh(): void {
    if (refreshInFlight.current) return;
    refreshInFlight.current = true;
    setRefreshing(true);
    void restart()
      .catch(() => undefined)
      .finally(() => {
        refreshInFlight.current = false;
        setRefreshing(false);
      });
  }

  function requestNextPage(): void {
    if (!hasNextPage || !cursor || isFetchingNextPage) return;

    const key = `${categoryId}:${cursor}`;
    if (nextPageInFlight.current === key) return;
    nextPageInFlight.current = key;

    void fetchNextPage()
      .catch(() => undefined)
      .finally(() => {
        if (nextPageInFlight.current === key) {
          nextPageInFlight.current = null;
        }
      });
  }

  if (isPending) {
    return <LoadingView message="선택한 분야의 트렌드를 불러오고 있습니다." />;
  }

  if (isError && data === undefined) {
    return (
      <ErrorView
        title="선택한 분야의 트렌드를 불러오지 못했습니다."
        message="잠시 후 다시 시도해 주세요."
        onRetry={() => void refetch()}
        retrying={isFetching}
      />
    );
  }

  if (items.length === 0) {
    return <EmptyView title="선택한 분야의 트렌드가 아직 없습니다." />;
  }

  function renderFooter() {
    if (isFetchingNextPage) {
      return <LoadingView accessibilityLabel="다음 트렌드를 불러오는 중입니다." />;
    }
    if (isFetchNextPageError) {
      return (
        <ErrorView
          title="다음 트렌드를 불러오지 못했습니다."
          message="잠시 후 다시 시도해 주세요."
          onRetry={requestNextPage}
          retrying={isFetchingNextPage}
        />
      );
    }
    return null;
  }

  function renderTrend({ item }: ListRenderItemInfo<TrendListItem>) {
    return (
      <TrendCard
        trend={item}
        onOpenSource={(url) => void openTrendSourceUrl(url)}
      />
    );
  }

  return (
    <FlatList
      contentContainerStyle={styles.list}
      data={items}
      keyExtractor={(item) => item.trend_id.toString()}
      renderItem={renderTrend}
      ListFooterComponent={renderFooter}
      onEndReached={() => {
        if (!isFetchNextPageError) requestNextPage();
      }}
      onEndReachedThreshold={0.4}
      onRefresh={refresh}
      refreshing={refreshing}
      showsVerticalScrollIndicator={false}
      testID="filtered-personalized-trend-list"
    />
  );
}

const styles = StyleSheet.create({
  list: {
    gap: spacing.itemGap,
    paddingBottom: spacing.screenBottomSpacing,
  },
});
