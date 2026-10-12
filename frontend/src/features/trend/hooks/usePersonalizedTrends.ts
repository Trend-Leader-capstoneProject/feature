
import {
  type InfiniteData,
  useInfiniteQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { isAxiosError } from "axios";

import {
  getPersonalizedTrends,
} from "../api/getPersonalizedTrends";
import {
  trendQueryKeys,
} from "../queryKeys";
import type {
  TrendListData,
} from "../types/trend";
import {
  isInvalidPersonalizedCursorError,
} from "../utils/isInvalidPersonalizedCursorError";

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

    // 4xx 오류는 같은 요청으로 반복 재시도하지 않는다.
    // 네트워크 및 서버 오류에는 일반 Retry 정책 적용.
    retry: (failureCount, error) => {
      if (isAxiosError(error)) {
        const status = error.response?.status;

        if (
          status !== undefined &&
          status >= 400 &&
          status < 500
        ) {
          return false;
        }
      }

      return failureCount < 3;
    },

    staleTime: 0,
    refetchOnMount: true,
  });

  // 기존 Pages 및 Cursor Chain 폐기 후 첫 페이지 재조회
  async function restart(): Promise<void> {
    await queryClient.cancelQueries({
      queryKey,
      exact: true,
    });

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

    await query.refetch();
  }

  // 다음 페이지 오류가 INVALID_CURSOR인 경우 자동 복구
  async function fetchNextPage(
    options?: Parameters<
      typeof query.fetchNextPage
    >[0],
  ) {
    const fetchResult =
      await query.fetchNextPage(options);

    if (
      fetchResult.isFetchNextPageError &&
      isInvalidPersonalizedCursorError(
        fetchResult.error,
      )
    ) {
      // 추가 페이지 오류에서만 첫 페이지 재시작
      await restart();
    }

    return fetchResult;
  }

  return {
    ...query,
    fetchNextPage,
    restart,
  };
}
