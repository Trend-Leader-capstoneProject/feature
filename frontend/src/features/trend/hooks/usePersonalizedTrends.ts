
import { useRef } from "react";

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

  // 진행 중인 첫 페이지 재시작 Promise를 공유한다.
  const restartPromiseRef = useRef<
    ReturnType<typeof query.refetch> | null
  >(null);

  // 기존 Pages와 Cursor를 폐기하고 첫 페이지부터 재조회한다.
  async function restart(): Promise<void> {
    // 이미 재시작 중이면 중복 요청을 만들지 않는다.
    if (restartPromiseRef.current) {
      await restartPromiseRef.current;
      return;
    }

    const restartPromise = (async () => {
      // 1. 진행 중인 기존 Query 취소
      await queryClient.cancelQueries({
        queryKey,
        exact: true,
      });

      // 2. 기존 Cursor Chain 초기화
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

      // 3. Cursor 없는 첫 페이지 재조회
      return query.refetch();
    })();

    // 복구 작업의 Promise 등록
    restartPromiseRef.current = restartPromise;

    try {
      await restartPromise;
    } finally {
      // 정상 완료와 오류 모두 참조를 해제한다.
      if (
        restartPromiseRef.current ===
        restartPromise
      ) {
        restartPromiseRef.current = null;
      }
    }
  }

  // 추가 페이지 조회 및 INVALID_CURSOR 자동 복구
  async function fetchNextPage(
    options?: Parameters<
      typeof query.fetchNextPage
    >[0],
  ) {
    // 첫 페이지 재시작 중에는 추가 페이지 요청을 만들지 않는다.
    if (restartPromiseRef.current) {
      return restartPromiseRef.current;
    }

    const fetchResult =
      await query.fetchNextPage(options);

    if (
      fetchResult.isFetchNextPageError &&
      isInvalidPersonalizedCursorError(
        fetchResult.error,
      )
    ) {
      // INVALID_CURSOR 발생 시 자동 재시작
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
