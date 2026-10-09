import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { renderHook, waitFor } from "@testing-library/react-native";

import { act, type PropsWithChildren } from "react";

import { getPersonalizedTrends } from "../../src/features/trend/api/getPersonalizedTrends";

import { usePersonalizedTrends } from "../../src/features/trend/hooks/usePersonalizedTrends";

import { trendQueryKeys } from "../../src/features/trend/queryKeys";

import type { TrendListData } from "../../src/features/trend/types/trend";

jest.mock("../../src/features/trend/api/getPersonalizedTrends", () => ({
  getPersonalizedTrends: jest.fn(),
}));

const mockedGetPersonalizedTrends = jest.mocked(getPersonalizedTrends);

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return function TestWrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("usePersonalizedTrends", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  test("첫 페이지를 Cursor 없이 조회하고 Public과 Cache를 분리한다", async () => {
    const firstPage: TrendListData = {
      items: [],
      next_cursor: null,
      has_next: false,
    };

    mockedGetPersonalizedTrends.mockResolvedValueOnce(firstPage);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(() => usePersonalizedTrends(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // 기본 limit과 첫 페이지 요청 확인
    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(1);

    expect(mockedGetPersonalizedTrends).toHaveBeenCalledWith(
      {
        cursor: undefined,
        limit: 20,
      },
      expect.any(AbortSignal),
    );

    // Personalized 전용 Cache 확인
    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(20)),
    ).toMatchObject({
      pages: [firstPage],
    });

    // Public Trend Cache와 분리되어야 한다.
    expect(
      queryClient.getQueryData(trendQueryKeys.list(null, 20)),
    ).toBeUndefined();
  });

  test("서버 Cursor로 다음 페이지를 조회하고 마지막 페이지에서 중단한다", async () => {
    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "Trend 101",
          summary: null,
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "CURSOR_PAGE_2",
      has_next: true,
    };

    const secondPage: TrendListData = {
      items: [
        {
          trend_id: 102,
          title: "Trend 102",
          summary: null,
          thumbnail_url: null,
          last_collected_at: "2026-10-01T08:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(secondPage);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(
      () => usePersonalizedTrends({ limit: 5 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    // 1. 첫 페이지 조회 완료
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.hasNextPage).toBe(true);

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      1,
      {
        cursor: undefined,
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    // 2. 다음 페이지 요청
    await act(async () => {
      await result.current.fetchNextPage();
    });

    // 3. 서버의 next_cursor 사용 확인
    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      2,
      {
        cursor: "CURSOR_PAGE_2",
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    // 4. 기존 페이지를 보존하고 새 페이지 누적
    await waitFor(() => {
      expect(result.current.data?.pages).toEqual([firstPage, secondPage]);
    });

    expect(result.current.data?.pageParams).toEqual([
      undefined,
      "CURSOR_PAGE_2",
    ]);

    // 5. 마지막 페이지이므로 추가 페이지 없음
    expect(result.current.hasNextPage).toBe(false);

    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(2);
  });
});
