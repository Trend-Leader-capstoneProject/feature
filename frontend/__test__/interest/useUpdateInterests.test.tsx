import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import {
  act,
  renderHook,
  waitFor,
} from "@testing-library/react-native";
import type { AxiosError } from "axios";
import type { PropsWithChildren } from "react";

import { updateUserInterests } from "../../src/features/interest/api/updateUserInterests";
import {
  useUpdateInterests,
} from "../../src/features/interest/hooks/useUpdateInterests";
import {
  categoryQueryKeys,
  userInterestQueryKeys,
} from "../../src/features/interest/queryKeys";
import type {
  CategoryListData,
} from "../../src/features/interest/types/category";
import type {
  InterestUpdateErrorResponse,
  InterestUpdateResponse,
} from "../../src/features/interest/types/interest";

jest.mock(
  "../../src/features/interest/api/updateUserInterests",
  () => ({
    updateUserInterests: jest.fn(),
  }),
);

const mockedUpdateUserInterests =
  jest.mocked(updateUserInterests);

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

function createConflictError():
  AxiosError<InterestUpdateErrorResponse> {
  return {
    isAxiosError: true,
    response: {
      status: 409,
      data: {
        success: false,
        statusCode: 409,
        message:
          "수정할 기존 관심사가 없습니다.",
        data: {
          reason:
            "INTERESTS_NOT_INITIALIZED",
        },
      },
    },
  } as AxiosError<InterestUpdateErrorResponse>;
}

describe("useUpdateInterests", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test(
    "PUT 성공 전에는 기존 Cache를 유지하고 성공 후 응답값으로 교체한다",
    async () => {
      const queryClient =
        createTestQueryClient();

      queryClient.setQueryData(
        userInterestQueryKeys.me,
        CURRENT_INTERESTS,
      );

      queryClient.setQueryData(
        categoryQueryKeys.all,
        CATEGORY_DATA,
      );

      const invalidateQueriesSpy =
        jest.spyOn(
          queryClient,
          "invalidateQueries",
        );

      const deferred =
        createDeferred<InterestUpdateResponse>();

      mockedUpdateUserInterests.mockReturnValue(
        deferred.promise,
      );

      const rendered = await renderHook(
        () => useUpdateInterests(),
        {
          wrapper: createWrapper(
            queryClient,
          ),
        },
      );

      act(() => {
        rendered.result.current.mutate({
          category_ids: [1, 3],
        });
      });

      await waitFor(() => {
        expect(
          rendered.result.current.isPending,
        ).toBe(true);
      });

      expect(
        queryClient.getQueryData(
          userInterestQueryKeys.me,
        ),
      ).toEqual(CURRENT_INTERESTS);

      await act(async () => {
        deferred.resolve(
          UPDATED_INTERESTS,
        );

        await deferred.promise;
      });

      await waitFor(() => {
        expect(
          rendered.result.current.isSuccess,
        ).toBe(true);
      });

      expect(
        mockedUpdateUserInterests,
      ).toHaveBeenCalledWith({
        category_ids: [1, 3],
      });

      expect(
        queryClient.getQueryData(
          userInterestQueryKeys.me,
        ),
      ).toEqual(UPDATED_INTERESTS);

      expect(
        queryClient.getQueryData(
          categoryQueryKeys.all,
        ),
      ).toEqual(CATEGORY_DATA);

      expect(
        invalidateQueriesSpy,
      ).not.toHaveBeenCalled();
    },
  );

  test(
    "PUT 409 실패 시 기존 관심사 Cache를 유지한다",
    async () => {
      const queryClient =
        createTestQueryClient();

      queryClient.setQueryData(
        userInterestQueryKeys.me,
        CURRENT_INTERESTS,
      );

      mockedUpdateUserInterests.mockRejectedValue(
        createConflictError(),
      );

      const rendered = await renderHook(
        () => useUpdateInterests(),
        {
          wrapper: createWrapper(
            queryClient,
          ),
        },
      );

      act(() => {
        rendered.result.current.mutate({
          category_ids: [1, 3],
        });
      });

      await waitFor(() => {
        expect(
          rendered.result.current.isError,
        ).toBe(true);
      });

      expect(
        mockedUpdateUserInterests,
      ).toHaveBeenCalledTimes(1);

      expect(
        queryClient.getQueryData(
          userInterestQueryKeys.me,
        ),
      ).toEqual(CURRENT_INTERESTS);

      expect(
        rendered.result.current.error
          ?.response?.data.statusCode,
      ).toBe(409);

      expect(
        rendered.result.current.error
          ?.response?.data.data,
      ).toEqual({
        reason:
          "INTERESTS_NOT_INITIALIZED",
      });
    },
  );
});
