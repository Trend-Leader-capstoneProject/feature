
import {
  type InfiniteData,
  useInfiniteQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  getPersonalizedTrends,
} from "../api/getPersonalizedTrends";

import {
  trendQueryKeys,
} from "../queryKeys";

import type {
  TrendListData,
} from "../types/trend";

const DEFAULT_PERSONALIZED_TREND_LIMIT = 20;

export interface UsePersonalizedTrendsParams {
  limit?: number;
}

export function usePersonalizedTrends({
  limit = DEFAULT_PERSONALIZED_TREND_LIMIT,
}: UsePersonalizedTrendsParams = {}) {
  const queryClient = useQueryClient();

  const queryKey =
    trendQueryKeys.personalizedList(limit);

  // 1. Personalized Infinite Query
  const query = useInfiniteQuery({
    queryKey,

    queryFn: ({
      pageParam,
      signal,
    }) =>
      getPersonalizedTrends(
        {
          cursor: pageParam,
          limit,
        },
        signal,
      ),

    initialPageParam:
      undefined as string | undefined,

    getNextPageParam: (lastPage) => {
      if (!lastPage.has_next) {
        return undefined;
      }

      return lastPage.next_cursor ?? undefined;
    },

    // Personalized 목록은 Live Feed
    staleTime: 0,
    refetchOnMount: true,
  });

  // 2. 기존 Cursor Chain 폐기 및 첫 페이지 재조회
  async function restart(): Promise<void> {
    // 진행 중인 Personalized 요청 취소
    await queryClient.cancelQueries({
      queryKey,
      exact: true,
    });

    // 기존 Pages와 Cursor Chain 초기화
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
          pages: currentData.pages.slice(0, 1),
          pageParams: [undefined],
        };
      },
    );

    // Cursor 없는 첫 페이지부터 다시 조회
    await query.refetch();
  }

  // 3. 기존 Query 기능과 restart() 함께 반환
  return {
    ...query,
    restart,
  };
}
