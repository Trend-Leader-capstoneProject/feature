import {
    type InfiniteData,
    useInfiniteQuery,
    useQueryClient,
} from "@tanstack/react-query";

import {
    getTrends,
} from "../api/getTrends";
import {
    trendQueryKeys,
} from "../queryKeys";
import type {
    TrendListData,
} from "../types/trend";


const DEFAULT_TREND_LIMIT = 20;

export interface UseTrendsParams {
  categoryId: number | null;
  limit?: number;
}

export function useTrends({
  categoryId,
  limit = DEFAULT_TREND_LIMIT,
}: UseTrendsParams) {
  const queryClient = useQueryClient();

  const queryKey =
    trendQueryKeys.list(
      categoryId,
      limit,
    );

  const query = useInfiniteQuery({
    queryKey,

    queryFn: ({
      pageParam,
    }) =>
      getTrends({
        cursor: pageParam,
        limit,
        category_id:
          categoryId ?? undefined,
      }),

    initialPageParam:
      undefined as string | undefined,

    getNextPageParam: (
      lastPage,
    ) => {
      if (!lastPage.has_next) {
        return undefined;
      }

      return (
        lastPage.next_cursor ??
        undefined
      );
    },

    /*
     * 최신 목록은 live-feed이므로 Cache가 존재해도
     * 다시 관찰할 때 서버 최신성을 확인한다.
     *
     * 기존 Cache는 즉시 사용할 수 있고,
     * stale Query는 background refetch 대상이 된다.
     */
    staleTime: 0,
    refetchOnMount: true,
  });

  async function restart(): Promise<void> {
    /*
     * Infinite Query의 모든 페이지를 그대로 refetch하면
     * 기존 2, 3... 페이지까지 다시 조회할 수 있다.
     *
     * Refresh에서는 첫 페이지부터 새 탐색을 시작해야 하므로
     * Cache를 첫 페이지 하나로 축소한 뒤 refetch한다.
     */
    queryClient.setQueryData<
      InfiniteData<
        TrendListData,
        string | undefined
      >
    >(
      queryKey,
      (currentData) => {
        if (!currentData) {
          return currentData;
        }

        return {
          pages:
            currentData.pages.slice(
              0,
              1,
            ),
          pageParams:
            currentData.pageParams.slice(
              0,
              1,
            ),
        };
      },
    );

    await query.refetch();
  }

  return {
    ...query,
    restart,
  };
}
