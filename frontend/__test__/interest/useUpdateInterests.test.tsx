import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react-native";
import type { AxiosError } from "axios";
import type { PropsWithChildren } from "react";

import { updateUserInterests } from "../../src/features/interest/api/updateUserInterests";
import { useUpdateInterests } from "../../src/features/interest/hooks/useUpdateInterests";
import {
  categoryQueryKeys,
  userInterestQueryKeys,
} from "../../src/features/interest/queryKeys";
import type { CategoryListData } from "../../src/features/interest/types/category";
import type {
  InterestUpdateErrorResponse,
  InterestUpdateResponse,
} from "../../src/features/interest/types/interest";
import { getPersonalizedTrends } from "../../src/features/trend/api/getPersonalizedTrends";
import { usePersonalizedTrends } from "../../src/features/trend/hooks/usePersonalizedTrends";
import { trendQueryKeys } from "../../src/features/trend/queryKeys";
import { TrendListData } from "../../src/features/trend/types/trend";

jest.mock("../../src/features/interest/api/updateUserInterests", () => ({
  updateUserInterests: jest.fn(),
}));

jest.mock("../../src/features/trend/api/getPersonalizedTrends", () => ({
  getPersonalizedTrends: jest.fn(),
}));

const mockedGetPersonalizedTrends = jest.mocked(getPersonalizedTrends);

const mockedUpdateUserInterests = jest.mocked(updateUserInterests);

const CURRENT_INTERESTS: InterestUpdateResponse = {
  selected_category_ids: [1, 2],
  selected_count: 2,
};

const UPDATED_INTERESTS: InterestUpdateResponse = {
  selected_category_ids: [1, 3],
  selected_count: 2,
};

const CATEGORY_DATA: CategoryListData = {
  categories: [],
};

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
      mutations: {
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

function createDeferred<T>() {
  let resolvePromise: ((value: T) => void) | null = null;

  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });

  return {
    promise,

    resolve(value: T): void {
      if (!resolvePromise) {
        throw new Error("Deferred Promise가 초기화되지 않았습니다.");
      }

      resolvePromise(value);
    },
  };
}

function createConflictError(): AxiosError<InterestUpdateErrorResponse> {
  return {
    isAxiosError: true,
    response: {
      status: 409,
      data: {
        success: false,
        statusCode: 409,
        message: "수정할 기존 관심사가 없습니다.",
        data: {
          reason: "INTERESTS_NOT_INITIALIZED",
        },
      },
    },
  } as AxiosError<InterestUpdateErrorResponse>;
}

describe("useUpdateInterests", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("PUT 성공 전에는 기존 Cache를 유지하고 성공 후 응답값으로 교체한다", async () => {
    const queryClient = createTestQueryClient();

    queryClient.setQueryData(userInterestQueryKeys.me, CURRENT_INTERESTS);

    queryClient.setQueryData(categoryQueryKeys.all, CATEGORY_DATA);

    const invalidateQueriesSpy = jest.spyOn(queryClient, "invalidateQueries");

    const deferred = createDeferred<InterestUpdateResponse>();

    mockedUpdateUserInterests.mockReturnValue(deferred.promise);

    const rendered = await renderHook(() => useUpdateInterests(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      rendered.result.current.mutate({
        category_ids: [1, 3],
      });
    });

    await waitFor(() => {
      expect(rendered.result.current.isPending).toBe(true);
    });

    expect(queryClient.getQueryData(userInterestQueryKeys.me)).toEqual(
      CURRENT_INTERESTS,
    );

    await act(async () => {
      deferred.resolve(UPDATED_INTERESTS);

      await deferred.promise;
    });

    await waitFor(() => {
      expect(rendered.result.current.isSuccess).toBe(true);
    });

    expect(mockedUpdateUserInterests).toHaveBeenCalledTimes(1);

    expect(mockedUpdateUserInterests.mock.calls[0]?.[0]).toEqual({
      category_ids: [1, 3],
    });

    expect(queryClient.getQueryData(userInterestQueryKeys.me)).toEqual(
      UPDATED_INTERESTS,
    );

    expect(queryClient.getQueryData(categoryQueryKeys.all)).toEqual(
      CATEGORY_DATA,
    );

    expect(invalidateQueriesSpy).not.toHaveBeenCalled();
  });

  test("PUT 409 실패 시 기존 관심사 Cache를 유지한다", async () => {
    const queryClient = createTestQueryClient();

    queryClient.setQueryData(userInterestQueryKeys.me, CURRENT_INTERESTS);

    mockedUpdateUserInterests.mockRejectedValue(createConflictError());

    const rendered = await renderHook(() => useUpdateInterests(), {
      wrapper: createWrapper(queryClient),
    });

    await act(() => {
      rendered.result.current.mutate({
        category_ids: [1, 3],
      });
    });

    await waitFor(() => {
      expect(rendered.result.current.isError).toBe(true);
    });

    expect(mockedUpdateUserInterests).toHaveBeenCalledTimes(1);

    expect(queryClient.getQueryData(userInterestQueryKeys.me)).toEqual(
      CURRENT_INTERESTS,
    );

    expect(rendered.result.current.error?.response?.data.statusCode).toBe(409);

    expect(rendered.result.current.error?.response?.data.data).toEqual({
      reason: "INTERESTS_NOT_INITIALIZED",
    });
  });

  test("PUT 성공 시 Personalized Pages와 Cursor를 제거하고 Public Cache는 유지한다", async () => {
    const queryClient = createTestQueryClient();

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

    const oldPersonalizedData = {
      pages: [firstPage, secondPage],
      pageParams: [undefined, "OLD_CURSOR"],
    };

    const publicData = {
      pages: [firstPage],
      pageParams: [undefined],
    };

    // 기존 관심사와 목록 Cache 준비
    queryClient.setQueryData(userInterestQueryKeys.me, CURRENT_INTERESTS);

    queryClient.setQueryData(
      trendQueryKeys.personalizedList(20),
      oldPersonalizedData,
    );

    queryClient.setQueryData(
      trendQueryKeys.personalizedList(5),
      oldPersonalizedData,
    );

    queryClient.setQueryData(trendQueryKeys.list(null, 20), publicData);

    queryClient.setQueryData(categoryQueryKeys.all, CATEGORY_DATA);

    const cancelSpy = jest.spyOn(queryClient, "cancelQueries");

    const removeSpy = jest.spyOn(queryClient, "removeQueries");

    mockedUpdateUserInterests.mockResolvedValueOnce(UPDATED_INTERESTS);

    const { result } = await renderHook(() => useUpdateInterests(), {
      wrapper: createWrapper(queryClient),
    });

    // PUT 성공
    await act(async () => {
      await result.current.mutateAsync({
        category_ids: [1, 3],
      });
    });

    // 관심사 Cache는 서버 응답값으로 갱신
    expect(queryClient.getQueryData(userInterestQueryKeys.me)).toEqual(
      UPDATED_INTERESTS,
    );

    // 서로 다른 limit의 Personalized Cache가 모두 제거
    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(20)),
    ).toBeUndefined();

    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(5)),
    ).toBeUndefined();

    // Public 목록은 유지
    expect(queryClient.getQueryData(trendQueryKeys.list(null, 20))).toEqual(
      publicData,
    );

    // Category Master도 유지
    expect(queryClient.getQueryData(categoryQueryKeys.all)).toEqual(
      CATEGORY_DATA,
    );

    // Personalized Namespace만 취소하고 제거
    expect(cancelSpy).toHaveBeenCalledWith({
      queryKey: trendQueryKeys.personalizedAll,
    });

    expect(removeSpy).toHaveBeenCalledWith({
      queryKey: trendQueryKeys.personalizedAll,
    });

    // 반드시 취소 요청 후 Cache 제거
    expect(cancelSpy.mock.invocationCallOrder[0]).toBeLessThan(
      removeSpy.mock.invocationCallOrder[0],
    );
  });

  test("PUT 409 실패 시 Personalized Pages와 Cursor를 유지한다", async () => {
    const queryClient = createTestQueryClient();

    // 1. 변경 전 Personalized Pagination 상태
    const oldPersonalizedData = {
      pages: [
        {
          items: [],
          next_cursor: "OLD_CURSOR",
          has_next: true,
        },
        {
          items: [],
          next_cursor: null,
          has_next: false,
        },
      ],
      pageParams: [undefined, "OLD_CURSOR"],
    };

    const publicData = {
      pages: [
        {
          items: [],
          next_cursor: null,
          has_next: false,
        },
      ],
      pageParams: [undefined],
    };

    // 2. 기존 Cache 구성
    queryClient.setQueryData(userInterestQueryKeys.me, CURRENT_INTERESTS);

    queryClient.setQueryData(
      trendQueryKeys.personalizedList(20),
      oldPersonalizedData,
    );

    queryClient.setQueryData(trendQueryKeys.list(null, 20), publicData);

    queryClient.setQueryData(categoryQueryKeys.all, CATEGORY_DATA);

    const cancelSpy = jest.spyOn(queryClient, "cancelQueries");

    const removeSpy = jest.spyOn(queryClient, "removeQueries");

    // 3. PUT 요청에서 409 발생
    mockedUpdateUserInterests.mockRejectedValueOnce(createConflictError());

    const { result } = await renderHook(() => useUpdateInterests(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      result.current.mutate({
        category_ids: [1, 3],
      });
    });

    // 4. Mutation 실패 확인
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.response?.status).toBe(409);

    // 5. 관심사 Cache 유지
    expect(queryClient.getQueryData(userInterestQueryKeys.me)).toEqual(
      CURRENT_INTERESTS,
    );

    // 6. Personalized Pages와 Cursor 유지
    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(20)),
    ).toEqual(oldPersonalizedData);

    // 7. Public 및 Category Cache 유지
    expect(queryClient.getQueryData(trendQueryKeys.list(null, 20))).toEqual(
      publicData,
    );

    expect(queryClient.getQueryData(categoryQueryKeys.all)).toEqual(
      CATEGORY_DATA,
    );

    // 8. 실패 시 Personalized Query를
    // 취소하거나 제거해서는 안 된다.
    expect(cancelSpy).not.toHaveBeenCalled();
    expect(removeSpy).not.toHaveBeenCalled();
  });

  test("PUT 성공 후 이전 Pagination 응답이 늦게 도착해도 새 Cache를 덮어쓰지 않는다", async () => {
    const queryClient = createTestQueryClient();

    // 1. 테스트 데이터
    const firstPage: TrendListData = {
      items: [],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const staleSecondPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "이전 관심사 Trend",
          summary: null,
          thumbnail_url: null,
          last_collected_at: "2026-10-09T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    const freshPage: TrendListData = {
      items: [
        {
          trend_id: 202,
          title: "새로운 관심사 Trend",
          summary: null,
          thumbnail_url: null,
          last_collected_at: "2026-10-09T10:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    // 이전 요청의 완료 시점을 직접 제어
    const lateResponse = createDeferred<TrendListData>();

    let oldRequestSignal: AbortSignal | undefined;
    let firstPageDelivered = false;

    mockedGetPersonalizedTrends.mockReset();

    // 2. API Mock
    // 호출 순서가 아니라 요청 Cursor로 응답을 결정한다.
    mockedGetPersonalizedTrends.mockImplementation((params, signal) => {
      // 이전 관심사의 다음 페이지 요청
      if (params?.cursor === "OLD_CURSOR") {
        oldRequestSignal = signal;

        // AbortSignal을 무시하는 늦은 응답 재현
        return lateResponse.promise;
      }

      // 최초 첫 페이지 요청
      if (!firstPageDelivered) {
        firstPageDelivered = true;
        return Promise.resolve(firstPage);
      }

      // 이후 첫 페이지 요청은 새 관심사 결과 반환
      return Promise.resolve(freshPage);
    });

    mockedUpdateUserInterests.mockResolvedValueOnce(UPDATED_INTERESTS);

    // 3. 실제 Personalized Hook 및 PUT Hook 활성화
    const { result } = await renderHook(
      () => ({
        personalized: usePersonalizedTrends(),
        update: useUpdateInterests(),
      }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    await waitFor(() => {
      expect(result.current.personalized.isSuccess).toBe(true);
    });

    expect(result.current.personalized.hasNextPage).toBe(true);

    // 4. 이전 Cursor로 다음 페이지 요청 시작
    await act(async () => {
      void result.current.personalized.fetchNextPage();
    });

    await waitFor(() => {
      expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(2);
    });

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      2,
      {
        cursor: "OLD_CURSOR",
        limit: 20,
      },
      expect.any(AbortSignal),
    );

    expect(oldRequestSignal?.aborted).toBe(false);

    // PUT 이전 요청 수를 기록한다.
    const callCountBeforeUpdate = mockedGetPersonalizedTrends.mock.calls.length;

    // 5. 이전 요청이 대기 중인 상태에서 관심사 PUT 성공
    await act(async () => {
      await result.current.update.mutateAsync({
        category_ids: [1, 3],
      });
    });

    // 진행 중이던 이전 요청이 취소되었는지 확인
    expect(oldRequestSignal?.aborted).toBe(true);

    // 6. 새로운 Personalized Hook 구독
    const freshView = await renderHook(() => usePersonalizedTrends(), {
      wrapper: createWrapper(queryClient),
    });

    // PUT 이후 새로운 조회가 시작되었는지 확인
    await waitFor(() => {
      expect(mockedGetPersonalizedTrends.mock.calls.length).toBeGreaterThan(
        callCountBeforeUpdate,
      );
    });

    // 새로운 관심사 결과가 성공적으로 도착했는지 확인
    await waitFor(() => {
      expect(freshView.result.current.isSuccess).toBe(true);
    });

    // 7. PUT 이후 요청은 모두 첫 페이지 요청이어야 한다.
    const requestsAfterUpdate = mockedGetPersonalizedTrends.mock.calls.slice(
      callCountBeforeUpdate,
    );

    expect(requestsAfterUpdate.length).toBeGreaterThan(0);

    for (const [params, signal] of requestsAfterUpdate) {
      expect(params).toEqual({
        cursor: undefined,
        limit: 20,
      });

      expect(signal).toEqual(expect.any(AbortSignal));
    }

    expect(freshView.result.current.data?.pages).toEqual([freshPage]);

    // 8. 취소된 이전 요청의 늦은 응답 완료
    await act(async () => {
      lateResponse.resolve(staleSecondPage);

      await lateResponse.promise;
    });

    // 9. 이전 응답이 새로운 Cache를 오염시키지 않아야 한다.
    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(20)),
    ).toMatchObject({
      pages: [freshPage],
      pageParams: [undefined],
    });

    expect(freshView.result.current.data?.pages).toEqual([freshPage]);
  });
});
