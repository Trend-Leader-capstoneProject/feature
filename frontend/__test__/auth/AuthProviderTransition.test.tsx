import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react-native";
import type { PropsWithChildren } from "react";

import { AuthProvider, useAuth } from "../../src/app/providers/AuthProvider";
import { getAuthSession } from "../../src/features/auth/api/getAuthSession";
import type {
    LoginResponse,
    SessionResponse,
} from "../../src/features/auth/types/auth";
import { registerAuthFailureHandler } from "../../src/shared/handler/authFailureHandler";
import {
    allowAuthenticatedRequests,
    blockAuthenticatedRequests,
} from "../../src/shared/handler/authRequestGate";
import {
    deleteAccessToken,
    getAccessToken,
    saveAccessToken,
} from "../../src/shared/storage/tokenStorage";

jest.mock("../../src/features/auth/api/getAuthSession", () => ({
  getAuthSession: jest.fn(),
}));

jest.mock("../../src/shared/storage/tokenStorage", () => ({
  saveAccessToken: jest.fn(),
  getAccessToken: jest.fn(),
  deleteAccessToken: jest.fn(),
}));

jest.mock("../../src/shared/handler/authFailureHandler", () => ({
  registerAuthFailureHandler: jest.fn(),
}));

jest.mock("../../src/shared/handler/authRequestGate", () => ({
  allowAuthenticatedRequests: jest.fn(),
  blockAuthenticatedRequests: jest.fn(),
}));

const mockedGetAuthSession = jest.mocked(getAuthSession);

const mockedGetAccessToken = jest.mocked(getAccessToken);

const mockedSaveAccessToken = jest.mocked(saveAccessToken);

const mockedDeleteAccessToken = jest.mocked(deleteAccessToken);

const mockedRegisterAuthFailureHandler = jest.mocked(
  registerAuthFailureHandler,
);

const INTEREST_SELECTION_SESSION: SessionResponse = {
  user: {
    user_id: 1,
    login_id: "user_a",
    name: "사용자 A",
    status: "ACTIVE",
  },
  has_selected_interests: false,
  next_step: "INTEREST_SELECTION",
};

const MAIN_SESSION_A: SessionResponse = {
  user: {
    user_id: 1,
    login_id: "user_a",
    name: "사용자 A",
    status: "ACTIVE",
  },
  has_selected_interests: true,
  next_step: "MAIN",
};

const LOGIN_B_RESPONSE: LoginResponse = {
  access_token: "TOKEN_B",
  token_type: "Bearer",
  user: {
    user_id: 2,
    login_id: "user_b",
    name: "사용자 B",
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

function createWrapper(queryClient: QueryClient) {
  return function TestWrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
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

function createDeferredVoid() {
  const deferred = createDeferred<void>();

  return {
    promise: deferred.promise,
    resolve(): void {
      deferred.resolve(undefined);
    },
  };
}

async function renderAuthenticatedProvider(initialSession: SessionResponse) {
  const queryClient = createTestQueryClient();

  mockedGetAuthSession.mockResolvedValueOnce(initialSession);

  const rendered = await renderHook(() => useAuth(), {
    wrapper: createWrapper(queryClient),
  });

  await waitFor(() => {
    expect(rendered.result.current.authState).toEqual({
      status: "AUTHENTICATED",
      session: initialSession,
    });
  });

  return rendered;
}

describe("AuthProvider session transition", () => {
  let storedAccessToken: string | null;

  beforeEach(() => {
    jest.resetAllMocks();

    storedAccessToken = "TOKEN_A";

    mockedGetAccessToken.mockImplementation(async () => storedAccessToken);

    mockedSaveAccessToken.mockImplementation(async (accessToken) => {
      storedAccessToken = accessToken;
    });

    mockedDeleteAccessToken.mockImplementation(async () => {
      storedAccessToken = null;
    });

    mockedRegisterAuthFailureHandler.mockImplementation(() => () => undefined);

    jest.mocked(allowAuthenticatedRequests).mockImplementation(() => undefined);

    jest.mocked(blockAuthenticatedRequests).mockImplementation(() => undefined);
  });

  test("관심사 선택 완료 시 현재 Session을 MAIN으로 변경한다", async () => {
    const { result } = await renderAuthenticatedProvider(
      INTEREST_SELECTION_SESSION,
    );

    await act(() => {
      result.current.completeInterestSelection();
    });

    expect(result.current.authState).toEqual({
      status: "AUTHENTICATED",
      session: {
        ...INTEREST_SELECTION_SESSION,
        has_selected_interests: true,
        next_step: "MAIN",
      },
    });
  });

  test("동일 Token의 Session 재검증 결과는 현재 Session에 반영한다", async () => {
    const { result } = await renderAuthenticatedProvider(
      INTEREST_SELECTION_SESSION,
    );

    mockedGetAuthSession.mockResolvedValueOnce(MAIN_SESSION_A);

    await act(async () => {
      await result.current.revalidateSession();
    });

    expect(result.current.authState).toEqual({
      status: "AUTHENTICATED",
      session: MAIN_SESSION_A,
    });
  });

  test("TOKEN_A 재검증 중 TOKEN_B가 생성되면 TOKEN_A의 늦은 응답을 무시한다", async () => {
    const { result } = await renderAuthenticatedProvider(
      INTEREST_SELECTION_SESSION,
    );

    const deferredSession = createDeferred<SessionResponse>();

    mockedGetAuthSession.mockImplementationOnce(() => deferredSession.promise);

    const revalidationPromise = result.current.revalidateSession();

    await waitFor(() => {
      expect(mockedGetAuthSession).toHaveBeenCalledTimes(2);
    });

    await act(async () => {
      await result.current.establishSession(LOGIN_B_RESPONSE);
    });

    expect(storedAccessToken).toBe("TOKEN_B");

    expect(result.current.authState).toEqual({
      status: "AUTHENTICATED",
      session: {
        user: LOGIN_B_RESPONSE.user,
        has_selected_interests: true,
        next_step: "MAIN",
      },
    });

    await act(async () => {
      deferredSession.resolve(MAIN_SESSION_A);

      await revalidationPromise;
    });

    expect(result.current.authState).toEqual({
      status: "AUTHENTICATED",
      session: {
        user: LOGIN_B_RESPONSE.user,
        has_selected_interests: true,
        next_step: "MAIN",
      },
    });
  });

  test("Session 종료 중 도착한 재검증 응답은 종료 중인 Session을 갱신하지 않는다", async () => {
    const { result } = await renderAuthenticatedProvider(
      INTEREST_SELECTION_SESSION,
    );

    const deferredSession = createDeferred<SessionResponse>();

    const deferredDelete = createDeferredVoid();

    mockedGetAuthSession.mockImplementationOnce(() => deferredSession.promise);

    mockedDeleteAccessToken.mockImplementationOnce(async () => {
      await deferredDelete.promise;

      storedAccessToken = null;
    });

    const revalidationPromise = result.current.revalidateSession();

    await waitFor(() => {
      expect(mockedGetAuthSession).toHaveBeenCalledTimes(2);
    });

    const logoutPromise = result.current.logout();

    await waitFor(() => {
      expect(mockedDeleteAccessToken).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      deferredSession.resolve(MAIN_SESSION_A);

      await revalidationPromise;
    });

    expect(result.current.authState).toEqual({
      status: "AUTHENTICATED",
      session: INTEREST_SELECTION_SESSION,
    });

    await act(async () => {
      deferredDelete.resolve();

      await logoutPromise;
    });

    expect(result.current.authState.status).toBe("UNAUTHENTICATED");

    expect(storedAccessToken).toBeNull();
  });
});
