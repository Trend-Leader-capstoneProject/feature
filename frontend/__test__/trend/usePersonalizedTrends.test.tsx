import {
    QueryClient,
    QueryClientProvider,
} from "@tanstack/react-query";

import {
    renderHook,
    waitFor,
} from "@testing-library/react-native";

import type {
    PropsWithChildren,
} from "react";

import {
    getPersonalizedTrends,
} from "../../src/features/trend/api/getPersonalizedTrends";

import {
    usePersonalizedTrends,
} from "../../src/features/trend/hooks/usePersonalizedTrends";

import {
    trendQueryKeys,
} from "../../src/features/trend/queryKeys";

import type {
    TrendListData,
} from "../../src/features/trend/types/trend";


jest.mock(
  "../../src/features/trend/api/getPersonalizedTrends",
  () => ({
    getPersonalizedTrends: jest.fn(),
  }),
);

const mockedGetPersonalizedTrends =
  jest.mocked(getPersonalizedTrends);


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


function createWrapper(
  queryClient: QueryClient,
) {
  return function TestWrapper({
    children,
  }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}


describe("usePersonalizedTrends", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  test(
    "첫 페이지를 Cursor 없이 조회하고 Public과 Cache를 분리한다",
    async () => {
      const firstPage: TrendListData = {
        items: [],
        next_cursor: null,
        has_next: false,
      };

      mockedGetPersonalizedTrends
        .mockResolvedValueOnce(firstPage);

      const queryClient =
        createTestQueryClient();

      const { result } = await renderHook(
        () => usePersonalizedTrends(),
        {
          wrapper:
            createWrapper(queryClient),
        },
      );

      await waitFor(() => {
        expect(
          result.current.isSuccess,
        ).toBe(true);
      });

      // 기본 limit과 첫 페이지 요청 확인
      expect(
        mockedGetPersonalizedTrends,
      ).toHaveBeenCalledTimes(1);

      expect(
        mockedGetPersonalizedTrends,
      ).toHaveBeenCalledWith(
        {
          cursor: undefined,
          limit: 20,
        },
        expect.any(AbortSignal),
      );

      // Personalized 전용 Cache 확인
      expect(
        queryClient.getQueryData(
          trendQueryKeys.personalizedList(20),
        ),
      ).toMatchObject({
        pages: [firstPage],
      });

      // Public Trend Cache와 분리되어야 한다.
      expect(
        queryClient.getQueryData(
          trendQueryKeys.list(null, 20),
        ),
      ).toBeUndefined();
    },
  );
});
