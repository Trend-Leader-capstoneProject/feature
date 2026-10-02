import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import {
  act,
  renderHook,
  waitFor,
} from "@testing-library/react-native";
import type {
  PropsWithChildren,
} from "react";

import {
  getTrends,
} from "../../src/features/trend/api/getTrends";
import {
  useTrends,
} from "../../src/features/trend/hooks/useTrends";
import type {
  TrendListData,
} from "../../src/features/trend/types/trend";


jest.mock(
  "../../src/features/trend/api/getTrends",
  () => ({
    getTrends: jest.fn(),
  }),
);

const mockedGetTrends =
  jest.mocked(getTrends);

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
      <QueryClientProvider
        client={queryClient}
      >
        {children}
      </QueryClientProvider>
    );
  };
}

function createDeferred<T>() {
  let resolvePromise:
    | ((value: T) => void)
    | null = null;

  const promise = new Promise<T>(
    (resolve) => {
      resolvePromise = resolve;
    },
  );

  return {
    promise,

    resolve(value: T): void {
      if (!resolvePromise) {
        throw new Error(
          "Deferred Promise가 초기화되지 않았습니다.",
        );
      }

      resolvePromise(value);
    },
  };
}

function createPage(
  trendId: number,
  {
    nextCursor = null,
    hasNext = false,
  }: {
    nextCursor?: string | null;
    hasNext?: boolean;
  } = {},
): TrendListData {
  return {
    items: [
      {
        trend_id: trendId,
        title: `Trend ${trendId}`,
        summary: null,
        thumbnail_url: null,
        last_collected_at:
          "2026-10-01T09:00:00Z",
        categories: [],
        latest_source: null,
      },
    ],
    next_cursor: nextCursor,
    has_next: hasNext,
  };
}


describe("useTrends", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  test(
    "첫 페이지는 Cursor 없이 기본 limit과 Category 문맥으로 조회한다",
    async () => {
      mockedGetTrends.mockResolvedValueOnce(
        createPage(1),
      );

      const queryClient =
        createTestQueryClient();

      const { result } = await renderHook(
        () =>
          useTrends({
            categoryId: null,
          }),
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

      expect(
        mockedGetTrends,
      ).toHaveBeenCalledWith({
        cursor: undefined,
        limit: 20,
        category_id: undefined,
      });
    },
  );

  test(
    "다음 페이지는 서버의 next_cursor를 사용하고 마지막 페이지에서 중단한다",
    async () => {
      mockedGetTrends
        .mockResolvedValueOnce(
          createPage(1, {
            nextCursor: "CURSOR_1",
            hasNext: true,
          }),
        )
        .mockResolvedValueOnce(
          createPage(2),
        );

      const queryClient =
        createTestQueryClient();

      const { result } = await renderHook(
        () =>
          useTrends({
            categoryId: 10,
          }),
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

      expect(
        result.current.hasNextPage,
      ).toBe(true);

      await act(async () => {
        await result.current.fetchNextPage();
      });

      expect(
        mockedGetTrends,
      ).toHaveBeenNthCalledWith(
        2,
        {
          cursor: "CURSOR_1",
          limit: 20,
          category_id: 10,
        },
      );

      await waitFor(() => {
        expect(
          result.current.data?.pages,
        ).toHaveLength(2);

        expect(
          result.current.hasNextPage,
        ).toBe(false);
      });
    },
  );

  test(
    "필터 변경 전의 늦은 응답은 현재 Category 결과를 덮어쓰지 않는다",
    async () => {
      const categoryOne =
        createDeferred<TrendListData>();

      const categoryTwo =
        createDeferred<TrendListData>();

      mockedGetTrends.mockImplementation(
        (params = {}) => {
          if (params.category_id === 1) {
            return categoryOne.promise;
          }

          return categoryTwo.promise;
        },
      );

      const queryClient =
        createTestQueryClient();

      const { result, rerender } =
        await renderHook(
          ({
            categoryId,
          }: {
            categoryId: number;
          }) =>
            useTrends({
              categoryId,
            }),
          {
            initialProps: {
              categoryId: 1,
            },
            wrapper:
              createWrapper(queryClient),
          },
        );

      await waitFor(() => {
        expect(
          mockedGetTrends,
        ).toHaveBeenCalledTimes(1);
      });

      await rerender({
        categoryId: 2,
      });

      await waitFor(() => {
        expect(
          mockedGetTrends,
        ).toHaveBeenCalledTimes(2);
      });

      await act(async () => {
        categoryTwo.resolve(
          createPage(2),
        );
      });

      await waitFor(() => {
        expect(
          result.current.data
            ?.pages[0]
            .items[0]
            .trend_id,
        ).toBe(2);
      });

      await act(async () => {
        categoryOne.resolve(
          createPage(1),
        );
      });

      expect(
        result.current.data
          ?.pages[0]
          .items[0]
          .trend_id,
      ).toBe(2);
    },
  );

  test(
    "restart는 기존 Infinite Pages를 버리고 Cursor 없는 첫 페이지부터 다시 조회한다",
    async () => {
      mockedGetTrends
        .mockResolvedValueOnce(
          createPage(1, {
            nextCursor: "CURSOR_1",
            hasNext: true,
          }),
        )
        .mockResolvedValueOnce(
          createPage(2),
        )
        .mockResolvedValueOnce(
          createPage(100),
        );

      const queryClient =
        createTestQueryClient();

      const { result } = await renderHook(
        () =>
          useTrends({
            categoryId: null,
          }),
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

      await act(async () => {
        await result.current.fetchNextPage();
      });

      await waitFor(() => {
        expect(
          result.current.data?.pages,
        ).toHaveLength(2);
      });

      await act(async () => {
        await result.current.restart();
      });

      await waitFor(() => {
        expect(
          result.current.data
            ?.pages[0]
            .items[0]
            .trend_id,
        ).toBe(100);
      });

      expect(
        result.current.data?.pages,
      ).toHaveLength(1);

      expect(
        mockedGetTrends,
      ).toHaveBeenNthCalledWith(
        3,
        {
          cursor: undefined,
          limit: 20,
          category_id: undefined,
        },
      );
    },
  );
});
