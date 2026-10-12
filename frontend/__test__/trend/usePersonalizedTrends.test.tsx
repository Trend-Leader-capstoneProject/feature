import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { renderHook, waitFor } from "@testing-library/react-native";

import { act, type PropsWithChildren } from "react";

import { getPersonalizedTrends } from "../../src/features/trend/api/getPersonalizedTrends";

import { usePersonalizedTrends } from "../../src/features/trend/hooks/usePersonalizedTrends";

import { trendQueryKeys } from "../../src/features/trend/queryKeys";

import { AxiosError } from "axios";
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
  test("restart 시 기존 Pages와 Cursor를 버리고 첫 페이지부터 재조회한다", async () => {
    const firstPage: TrendListData = {
      items: [],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const secondPage: TrendListData = {
      items: [],
      next_cursor: null,
      has_next: false,
    };

    const refreshedFirstPage: TrendListData = {
      items: [],
      next_cursor: "NEW_CURSOR",
      has_next: true,
    };

    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(secondPage)
      .mockResolvedValueOnce(refreshedFirstPage);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(
      () => usePersonalizedTrends({ limit: 5 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // 기존 Cursor로 두 번째 페이지까지 조회
    // 첫 페이지에서 다음 페이지가 존재하는지 확인
    expect(result.current.hasNextPage).toBe(true);

    // 기존 Cursor로 두 번째 페이지 요청
    await act(async () => {
      await result.current.fetchNextPage();
    });

    // 서버의 다음 페이지 요청이 실제로 발생했는지 검증
    await waitFor(() => {
      expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(2);
    });

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      2,
      {
        cursor: "OLD_CURSOR",
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    // React Hook에 두 번째 페이지가 반영될 때까지 대기
    await waitFor(() => {
      expect(result.current.data?.pages).toEqual([firstPage, secondPage]);

      expect(result.current.data?.pageParams).toEqual([
        undefined,
        "OLD_CURSOR",
      ]);
    });

    // Cursor Chain 폐기 후 첫 페이지 재시작
    await act(async () => {
      await result.current.restart();
    });

    await waitFor(() => {
      expect(result.current.data?.pages).toEqual([refreshedFirstPage]);
    });

    expect(result.current.data?.pageParams).toEqual([undefined]);

    // 세 번째 요청에는 이전 Cursor가 없어야 함
    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      3,
      {
        cursor: undefined,
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    // 모든 과거 페이지를 다시 조회하지 않았는지 확인
    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(3);

    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(5)),
    ).toMatchObject({
      pages: [refreshedFirstPage],
      pageParams: [undefined],
    });
  });

  test("추가 페이지 INVALID_CURSOR 발생 시 첫 페이지부터 자동 재시작한다", async () => {
    const firstPage: TrendListData = {
      items: [],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const refreshedFirstPage: TrendListData = {
      items: [],
      next_cursor: "NEW_CURSOR",
      has_next: true,
    };

    const invalidCursorError = Object.assign(
      new Error("페이지 정보가 올바르지 않습니다."),
      {
        isAxiosError: true,
        response: {
          status: 400,
          data: {
            success: false,
            statusCode: 400,
            message: "페이지 정보가 올바르지 않습니다.",
            data: {
              reason: "INVALID_CURSOR",
            },
          },
        },
      },
    ) as AxiosError;

    // 첫 페이지 성공 → 추가 페이지 오류 → 복구 성공
    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockRejectedValueOnce(invalidCursorError)
      .mockResolvedValueOnce(refreshedFirstPage);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(
      () => usePersonalizedTrends({ limit: 5 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    // 1. 첫 페이지 성공
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.hasNextPage).toBe(true);

    // 2. OLD_CURSOR를 사용하는 추가 페이지 요청
    await act(async () => {
      await result.current.fetchNextPage();
    });

    // 3. INVALID_CURSOR 자동 복구 후 새 첫 페이지 확인
    await waitFor(() => {
      expect(result.current.data?.pages).toEqual([refreshedFirstPage]);
    });

    // 4. API 요청 순서 검증
    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      1,
      {
        cursor: undefined,
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      2,
      {
        cursor: "OLD_CURSOR",
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      3,
      {
        cursor: undefined,
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    // 5. 복구 요청은 한 번만 발생
    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(3);

    // 6. 기존 Cursor Chain 폐기
    expect(result.current.data?.pageParams).toEqual([undefined]);

    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(5)),
    ).toMatchObject({
      pages: [refreshedFirstPage],
      pageParams: [undefined],
    });
  });

  test("추가 페이지 409 오류에서는 자동 재시작하지 않는다", async () => {
    const firstPage: TrendListData = {
      items: [],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const conflictError = Object.assign(
      new Error("현재 관심사로 조회할 수 없습니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "현재 관심사로 조회할 수 없습니다.",
            data: {
              reason: "INTERESTS_NOT_AVAILABLE",
            },
          },
        },
      },
    );

    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockRejectedValueOnce(conflictError);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(
      () => usePersonalizedTrends({ limit: 5 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    // 첫 페이지 조회
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // 추가 페이지에서 409 발생
    await act(async () => {
      await result.current.fetchNextPage();
    });

    // 오류 상태 확인
    await waitFor(() => {
      expect(result.current.isFetchNextPageError).toBe(true);
    });

    // 409에서는 자동 재시작하지 않는다.
    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(2);

    // 기존 첫 페이지와 Cursor 유지
    expect(result.current.data?.pages).toEqual([firstPage]);

    expect(result.current.data?.pageParams).toEqual([undefined]);

    // 오류 발생 후 기존 Cursor로 추가 페이지를
    // 재시도할 수 있는 상태가 유지된다.
    expect(result.current.hasNextPage).toBe(true);
  });

  test.each([
    {
      label: "400 OTHER_ERROR",
      status: 400,
      reason: "OTHER_ERROR",
    },
    {
      label: "401 Unauthorized",
      status: 401,
      reason: undefined,
    },
  ])("$label 오류에서는 자동 재시작하지 않는다", async ({ status, reason }) => {
    const firstPage: TrendListData = {
      items: [],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const apiError = Object.assign(new Error("API 요청 실패"), {
      isAxiosError: true,
      response: {
        status,
        data: {
          success: false,
          statusCode: status,
          message: "API 요청 실패",
          data: reason ? { reason } : null,
        },
      },
    });

    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockRejectedValueOnce(apiError);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(
      () => usePersonalizedTrends({ limit: 5 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    // 1. 첫 페이지 정상 조회
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.hasNextPage).toBe(true);

    // 2. 다음 페이지에서 API 오류 발생
    await act(async () => {
      await result.current.fetchNextPage();
    });

    // 3. 추가 페이지 오류 상태 확인
    await waitFor(() => {
      expect(result.current.isFetchNextPageError).toBe(true);
    });

    // 4. 요청은 최초 조회 + 실패한 추가 조회만 발생
    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(2);

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      2,
      {
        cursor: "OLD_CURSOR",
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    // 5. 자동 재시작 없이 기존 페이지 유지
    expect(result.current.data?.pages).toEqual([firstPage]);

    expect(result.current.data?.pageParams).toEqual([undefined]);

    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(5)),
    ).toMatchObject({
      pages: [firstPage],
      pageParams: [undefined],
    });
  });

  test("INVALID_CURSOR 복구 첫 페이지가 실패하면 재시작을 반복하지 않는다", async () => {
    const firstPage: TrendListData = {
      items: [],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    // 추가 페이지에서 발생한 INVALID_CURSOR
    const invalidCursorError = Object.assign(
      new Error("페이지 정보가 올바르지 않습니다."),
      {
        isAxiosError: true,
        response: {
          status: 400,
          data: {
            success: false,
            statusCode: 400,
            message: "페이지 정보가 올바르지 않습니다.",
            data: {
              reason: "INVALID_CURSOR",
            },
          },
        },
      },
    );

    // 복구 첫 페이지에서 발생한 409
    const recoveryError = Object.assign(
      new Error("현재 관심사로 조회할 수 없습니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "현재 관심사로 조회할 수 없습니다.",
            data: {
              reason: "INTERESTS_NOT_AVAILABLE",
            },
          },
        },
      },
    );

    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockRejectedValueOnce(invalidCursorError)
      .mockRejectedValueOnce(recoveryError);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(
      () => usePersonalizedTrends({ limit: 5 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    // 1. 최초 첫 페이지 정상 조회
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.hasNextPage).toBe(true);

    // 2. 추가 페이지 INVALID_CURSOR 발생
    await act(async () => {
      await result.current.fetchNextPage();
    });

    // 3. 복구 첫 페이지 요청도 실패
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    // 4. 최종 오류는 복구 첫 페이지의 409
    expect(result.current.error).toBe(recoveryError);

    // 5. 최초 조회 + 추가 페이지 실패 + 복구 실패
    // 정확히 세 번만 요청해야 한다.
    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(3);

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      2,
      {
        cursor: "OLD_CURSOR",
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      3,
      {
        cursor: undefined,
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    // 6. 기존 추가 페이지 Cursor는 폐기
    expect(result.current.data?.pageParams).toEqual([undefined]);

    expect(result.current.data?.pages).toEqual([firstPage]);
  });

  test("INVALID_CURSOR 복구 중 추가 페이지와 재시작의 중복 실행을 차단한다", async () => {
    const firstPage: TrendListData = {
      items: [],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const recoveredFirstPage: TrendListData = {
      items: [],
      next_cursor: "NEW_CURSOR",
      has_next: true,
    };

    const invalidCursorError = Object.assign(
      new Error("페이지 정보가 올바르지 않습니다."),
      {
        isAxiosError: true,
        response: {
          status: 400,
          data: {
            success: false,
            statusCode: 400,
            message: "페이지 정보가 올바르지 않습니다.",
            data: {
              reason: "INVALID_CURSOR",
            },
          },
        },
      },
    );

    // 복구 첫 페이지의 응답을 직접 제어한다.
    let resolveRecovery!: (value: TrendListData) => void;

    const recoveryPromise = new Promise<TrendListData>((resolve) => {
      resolveRecovery = resolve;
    });

    let recoverySignal: AbortSignal | undefined;

    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockRejectedValueOnce(invalidCursorError)
      .mockImplementationOnce((_params, signal) => {
        recoverySignal = signal;
        return recoveryPromise;
      })
      // 중복 요청이 발생하더라도 undefined를 반환하지 않도록 설정
      .mockResolvedValue(recoveredFirstPage);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(
      () => usePersonalizedTrends({ limit: 5 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    // 1. 최초 첫 페이지 조회
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.hasNextPage).toBe(true);

    // 2. 다음 페이지에서 INVALID_CURSOR 발생
    await act(async () => {
      void result.current.fetchNextPage();
    });

    // 3. 자동 복구 요청이 시작될 때까지 기다린다.
    await waitFor(() => {
      expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(3);
    });

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      3,
      {
        cursor: undefined,
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    expect(recoverySignal?.aborted).toBe(false);

    // 4. 복구 요청이 아직 완료되지 않은 상태
    // 추가 페이지 요청과 restart를 동시에 시도한다.
    await act(async () => {
      void result.current.fetchNextPage();
      void result.current.restart();
    });

    // 응답을 완료시키기 전에 실제 상태를 기록한다.
    const callCountDuringRecovery =
      mockedGetPersonalizedTrends.mock.calls.length;

    const wasRecoveryAborted = recoverySignal?.aborted;

    // 5. 대기 중이던 복구 응답을 완료한다.
    await act(async () => {
      resolveRecovery(recoveredFirstPage);
      await recoveryPromise;
    });

    // 6. 복구 중 새로운 API 요청이 발생하지 않았어야 한다.
    expect(callCountDuringRecovery).toBe(3);

    // 기존 복구 요청도 취소되지 않았어야 한다.
    expect(wasRecoveryAborted).toBe(false);

    // 7. 복구된 첫 페이지가 반영되어야 한다.
    await waitFor(() => {
      expect(result.current.data?.pages).toEqual([recoveredFirstPage]);
    });

    expect(result.current.data?.pageParams).toEqual([undefined]);

    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(3);
  });

  test("INVALID_CURSOR 복구 완료 후 새로운 Cursor로 다음 페이지를 조회한다", async () => {
    const firstPage: TrendListData = {
      items: [],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const recoveredFirstPage: TrendListData = {
      items: [],
      next_cursor: "NEW_CURSOR",
      has_next: true,
    };

    const recoveredSecondPage: TrendListData = {
      items: [],
      next_cursor: null,
      has_next: false,
    };

    const invalidCursorError = Object.assign(
      new Error("페이지 정보가 올바르지 않습니다."),
      {
        isAxiosError: true,
        response: {
          status: 400,
          data: {
            success: false,
            statusCode: 400,
            message: "페이지 정보가 올바르지 않습니다.",
            data: {
              reason: "INVALID_CURSOR",
            },
          },
        },
      },
    );

    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockRejectedValueOnce(invalidCursorError)
      .mockResolvedValueOnce(recoveredFirstPage)
      .mockResolvedValueOnce(recoveredSecondPage);

    const queryClient = createTestQueryClient();

    const { result } = await renderHook(
      () => usePersonalizedTrends({ limit: 5 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    // 1. 최초 첫 페이지 조회
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // 2. OLD_CURSOR 오류로 자동 복구
    await act(async () => {
      await result.current.fetchNextPage();
    });

    await waitFor(() => {
      expect(result.current.data?.pages).toEqual([recoveredFirstPage]);
    });

    expect(result.current.hasNextPage).toBe(true);

    // 3. 복구 완료 이후 다음 페이지 요청
    await act(async () => {
      await result.current.fetchNextPage();
    });

    // 4. NEW_CURSOR로 요청했는지 확인
    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      4,
      {
        cursor: "NEW_CURSOR",
        limit: 5,
      },
      expect.any(AbortSignal),
    );

    // 5. 복구 이후 두 페이지 누적
    await waitFor(() => {
      expect(result.current.data?.pages).toEqual([
        recoveredFirstPage,
        recoveredSecondPage,
      ]);
    });

    expect(result.current.data?.pageParams).toEqual([undefined, "NEW_CURSOR"]);

    expect(result.current.hasNextPage).toBe(false);

    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(4);
  });
});
