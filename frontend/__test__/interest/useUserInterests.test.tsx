import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import {
  renderHook,
  waitFor,
} from "@testing-library/react-native";
import type { AxiosError } from "axios";
import type { PropsWithChildren } from "react";

import { getUserInterests } from "../../src/features/interest/api/getUserInterests";
import {
  useUserInterests,
} from "../../src/features/interest/hooks/useUserInterests";
import {
  userInterestQueryKeys,
} from "../../src/features/interest/queryKeys";
import type {
  InterestReadErrorResponse,
  InterestReadResponse,
} from "../../src/features/interest/types/interest";

jest.mock(
  "../../src/features/interest/api/getUserInterests",
  () => ({
    getUserInterests: jest.fn(),
  }),
);

const mockedGetUserInterests =
  jest.mocked(getUserInterests);

const INTEREST_DATA: InterestReadResponse = {
  selected_category_ids: [1, 3],
  selected_count: 2,
};

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
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

function createUnauthorizedError():
  AxiosError<InterestReadErrorResponse> {
  return {
    isAxiosError: true,
    response: {
      status: 401,
      data: {
        success: false,
        statusCode: 401,
        message: "로그인이 필요합니다.",
        data: null,
      },
    },
  } as AxiosError<InterestReadErrorResponse>;
}

describe("useUserInterests", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test(
    "현재 사용자 관심사를 조회하고 me Query Cache에 저장한다",
    async () => {
      const queryClient =
        createTestQueryClient();

      mockedGetUserInterests.mockResolvedValue(
        INTEREST_DATA,
      );

      const rendered = await renderHook(
        () => useUserInterests(),
        {
          wrapper: createWrapper(
            queryClient,
          ),
        },
      );

      await waitFor(() => {
        expect(
          rendered.result.current.isSuccess,
        ).toBe(true);
      });

      expect(
        mockedGetUserInterests,
      ).toHaveBeenCalledTimes(1);

      expect(
        rendered.result.current.data,
      ).toEqual(INTEREST_DATA);

      expect(
        queryClient.getQueryData(
          userInterestQueryKeys.me,
        ),
      ).toEqual(INTEREST_DATA);
    },
  );

  test(
    "401 오류는 자동 재시도하지 않는다",
    async () => {
      const queryClient =
        createTestQueryClient();

      mockedGetUserInterests.mockRejectedValue(
        createUnauthorizedError(),
      );

      const rendered = await renderHook(
        () => useUserInterests(),
        {
          wrapper: createWrapper(
            queryClient,
          ),
        },
      );

      await waitFor(() => {
        expect(
          rendered.result.current.isError,
        ).toBe(true);
      });

      expect(
        mockedGetUserInterests,
      ).toHaveBeenCalledTimes(1);
    },
  );
});
