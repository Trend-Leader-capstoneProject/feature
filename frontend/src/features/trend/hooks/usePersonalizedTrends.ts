import {
    useInfiniteQuery,
} from "@tanstack/react-query";

import {
    getPersonalizedTrends,
} from "../api/getPersonalizedTrends";

import {
    trendQueryKeys,
} from "../queryKeys";


const DEFAULT_PERSONALIZED_TREND_LIMIT = 20;


export interface UsePersonalizedTrendsParams {
  limit?: number;
}


export function usePersonalizedTrends({
  limit = DEFAULT_PERSONALIZED_TREND_LIMIT,
}: UsePersonalizedTrendsParams = {}) {
  return useInfiniteQuery({
    queryKey:
      trendQueryKeys.personalizedList(limit),

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

    // Personalized 목록도 최신성이 중요한 Live Feed
    staleTime: 0,
    refetchOnMount: true,
  });
}
