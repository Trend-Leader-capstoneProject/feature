import {
    QueryClient,
    QueryClientProvider,
} from "@tanstack/react-query";
import {
    renderHook,
    waitFor,
} from "@testing-library/react-native";
import type {
    AxiosError,
} from "axios";
import type {
    PropsWithChildren,
} from "react";

import {
    AuthProvider,
    useAuth,
} from "../../src/app/providers/AuthProvider";
import {
    getAuthSession,
} from "../../src/features/auth/api/getAuthSession";
import type {
    SessionResponse,
} from "../../src/features/auth/types/auth";
import {
    deleteAccessToken,
    getAccessToken,
} from "../../src/shared/storage/tokenStorage";

jest.mock(
  "../../src/features/auth/api/getAuthSession",
  () => ({
    getAuthSession: jest.fn(),
  }),
);

jest.mock(
  "../../src/shared/storage/tokenStorage",
  () => ({
    saveAccessToken: jest.fn(),
    getAccessToken: jest.fn(),
    deleteAccessToken: jest.fn(),
  }),
);

jest.mock(
  "../../src/shared/handler/authFailureHandler",
  () => ({
    registerAuthFailureHandler: jest.fn(
      () => () => undefined,
    ),
  }),
);

jest.mock(
  "../../src/shared/handler/authRequestGate",
  () => ({
    allowAuthenticatedRequests:
      jest.fn(),
    blockAuthenticatedRequests:
      jest.fn(),
  }),
);

const mockedGetAuthSession =
  jest.mocked(getAuthSession);

const mockedGetAccessToken =
  jest.mocked(getAccessToken);

const mockedDeleteAccessToken =
  jest.mocked(deleteAccessToken);

const INTEREST_SELECTION_SESSION: SessionResponse = {
  user: {
    user_id: 1,
    login_id: "trend_user",
    name: "테스트 사용자",
    status: "ACTIVE",
  },
  has_selected_interests: false,
  next_step: "INTEREST_SELECTION",
};

const MAIN_SESSION: SessionResponse = {
  user: {
    user_id: 1,
    login_id: "trend_user",
    name: "테스트 사용자",
    status: "ACTIVE",
  },
  has_selected_interests: true,
  next_step: "MAIN",
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
      <QueryClientProvider
        client={queryClient}
      >
        <AuthProvider>
          {children}
        </AuthProvider>
      </QueryClientProvider>
    );
  };
}

function createUnauthorizedError(): AxiosError {
  return {
    isAxiosError: true,
    response: {
      status: 401,
    },
  } as AxiosError;
}

describe("AuthProvider session restore", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    mockedDeleteAccessToken.mockResolvedValue(
      undefined,
    );
  });

  test(
    "저장된 Access Token이 없으면 UNAUTHENTICATED가 된다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        null,
      );

      const queryClient =
        createTestQueryClient();

      const {
        result,
      } = await renderHook(
        () => useAuth(),
        {
          wrapper:
            createWrapper(queryClient),
        },
      );

      await waitFor(() => {
        expect(
          result.current.authState.status,
        ).toBe("UNAUTHENTICATED");
      });

      expect(
        mockedGetAuthSession,
      ).not.toHaveBeenCalled();

      expect(
        mockedDeleteAccessToken,
      ).not.toHaveBeenCalled();
    },
  );

  test(
    "관심사가 없는 Session을 복원하면 INTEREST_SELECTION 상태가 된다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        "valid-token",
      );

      mockedGetAuthSession.mockResolvedValue(
        INTEREST_SELECTION_SESSION,
      );

      const queryClient =
        createTestQueryClient();

      const {
        result,
      } = await renderHook(
        () => useAuth(),
        {
          wrapper:
            createWrapper(queryClient),
        },
      );

      await waitFor(() => {
        expect(
          result.current.authState,
        ).toEqual({
          status: "AUTHENTICATED",
          session:
            INTEREST_SELECTION_SESSION,
        });
      });

      expect(
        mockedGetAuthSession,
      ).toHaveBeenCalledTimes(1);

      expect(
        mockedDeleteAccessToken,
      ).not.toHaveBeenCalled();
    },
  );

  test(
    "관심사가 있는 Session을 복원하면 MAIN 상태가 된다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        "valid-token",
      );

      mockedGetAuthSession.mockResolvedValue(
        MAIN_SESSION,
      );

      const queryClient =
        createTestQueryClient();

      const {
        result,
      } = await renderHook(
        () => useAuth(),
        {
          wrapper:
            createWrapper(queryClient),
        },
      );

      await waitFor(() => {
        expect(
          result.current.authState,
        ).toEqual({
          status: "AUTHENTICATED",
          session: MAIN_SESSION,
        });
      });

      expect(
        mockedGetAuthSession,
      ).toHaveBeenCalledTimes(1);

      expect(
        mockedDeleteAccessToken,
      ).not.toHaveBeenCalled();
    },
  );

  test(
    "Session 복원 중 401이 발생하면 Token과 Query Cache를 삭제하고 UNAUTHENTICATED가 된다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        "expired-token",
      );

      mockedGetAuthSession.mockRejectedValue(
        createUnauthorizedError(),
      );

      const queryClient =
        createTestQueryClient();

      const sensitiveQueryKey = [
        "user",
        "me",
      ] as const;

      queryClient.setQueryData(
        sensitiveQueryKey,
        {
          name: "캐시 사용자",
        },
      );

      const {
        result,
      } = await renderHook(
        () => useAuth(),
        {
          wrapper:
            createWrapper(queryClient),
        },
      );

      await waitFor(() => {
        expect(
          result.current.authState.status,
        ).toBe("UNAUTHENTICATED");
      });

      expect(
        mockedDeleteAccessToken,
      ).toHaveBeenCalledTimes(1);

      expect(
        queryClient.getQueryData(
          sensitiveQueryKey,
        ),
      ).toBeUndefined();
    },
  );

  test(
    "Session 복원 중 네트워크 오류가 발생하면 Token을 유지하고 RESTORE_ERROR가 된다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        "valid-token",
      );

      mockedGetAuthSession.mockRejectedValue(
        new Error("Network Error"),
      );

      const queryClient =
        createTestQueryClient();

      const sensitiveQueryKey = [
        "user",
        "me",
      ] as const;

      const cachedUser = {
        name: "캐시 사용자",
      };

      queryClient.setQueryData(
        sensitiveQueryKey,
        cachedUser,
      );

      const {
        result,
      } = await renderHook(
        () => useAuth(),
        {
          wrapper:
            createWrapper(queryClient),
        },
      );

      await waitFor(() => {
        expect(
          result.current.authState.status,
        ).toBe("RESTORE_ERROR");
      });

      expect(
        mockedDeleteAccessToken,
      ).not.toHaveBeenCalled();

      expect(
        queryClient.getQueryData(
          sensitiveQueryKey,
        ),
      ).toEqual(cachedUser);
    },
  );
});
