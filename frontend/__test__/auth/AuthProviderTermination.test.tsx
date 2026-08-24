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

import { Alert } from "react-native";
import {
    AuthProvider,
    useAuth,
} from "../../src/app/providers/AuthProvider";
import {
    getAuthSession,
} from "../../src/features/auth/api/getAuthSession";
import type {
    LoginResponse,
    SessionResponse,
} from "../../src/features/auth/types/auth";
import {
    registerAuthFailureHandler,
    type AuthFailureHandler,
} from "../../src/shared/handler/authFailureHandler";
import {
    allowAuthenticatedRequests,
    blockAuthenticatedRequests,
} from "../../src/shared/handler/authRequestGate";
import {
    deleteAccessToken,
    getAccessToken,
    saveAccessToken,
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
    registerAuthFailureHandler:
      jest.fn(),
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

const mockedSaveAccessToken =
  jest.mocked(saveAccessToken);

const mockedDeleteAccessToken =
  jest.mocked(deleteAccessToken);

const mockedRegisterAuthFailureHandler =
  jest.mocked(
    registerAuthFailureHandler,
  );

const mockedAllowAuthenticatedRequests =
  jest.mocked(
    allowAuthenticatedRequests,
  );

const mockedBlockAuthenticatedRequests =
  jest.mocked(
    blockAuthenticatedRequests,
  );

const MAIN_SESSION: SessionResponse = {
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

let registeredAuthFailureHandler:
  AuthFailureHandler | null = null;

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

function createDeferredVoid() {
  let resolve:
    (() => void) | null = null;

  const promise =
    new Promise<void>(
      (resolvePromise) => {
        resolve = () => {
          resolvePromise();
        };
      },
    );

  return {
    promise,
    resolve(): void {
      if (!resolve) {
        throw new Error(
          "Deferred Promise가 초기화되지 않았습니다.",
        );
      }

      resolve();
    },
  };
}

async function renderAuthenticatedProvider(
  queryClient: QueryClient,
) {
  const rendered =
    await renderHook(
      () => useAuth(),
      {
        wrapper:
          createWrapper(queryClient),
      },
    );

  await waitFor(() => {
    expect(
      rendered.result.current.authState,
    ).toEqual({
      status: "AUTHENTICATED",
      session: MAIN_SESSION,
    });
  });

  await waitFor(() => {
    expect(
      registeredAuthFailureHandler,
    ).not.toBeNull();
  });

  return rendered;
}

function clearTerminationMockCalls(): void {
  mockedSaveAccessToken.mockClear();
  mockedDeleteAccessToken.mockClear();

  mockedAllowAuthenticatedRequests
    .mockClear();

  mockedBlockAuthenticatedRequests
    .mockClear();
}

describe(
  "AuthProvider session termination",
  () => {
    beforeEach(() => {
      jest.clearAllMocks();

      registeredAuthFailureHandler =
        null;

      mockedGetAccessToken
        .mockResolvedValue(
          "TOKEN_A",
        );

      mockedGetAuthSession
        .mockResolvedValue(
          MAIN_SESSION,
        );

      mockedSaveAccessToken
        .mockResolvedValue(
          undefined,
        );

      mockedDeleteAccessToken
        .mockResolvedValue(
          undefined,
        );

      mockedRegisterAuthFailureHandler
        .mockImplementation(
          (handler) => {
            registeredAuthFailureHandler =
              handler;

            return () => {
              if (
                registeredAuthFailureHandler ===
                handler
              ) {
                registeredAuthFailureHandler =
                  null;
              }
            };
          },
        );
    });

    test(
      "수동 Logout은 Token과 Query Cache를 삭제하고 UNAUTHENTICATED가 된다",
      async () => {
        const queryClient =
          createTestQueryClient();

        const sensitiveQueryKey = [
          "user",
          "profile",
        ] as const;

        queryClient.setQueryData(
          sensitiveQueryKey,
          {
            userId: 1,
          },
        );

        const cancelQueriesSpy =
          jest.spyOn(
            queryClient,
            "cancelQueries",
          );

        const {
          result,
        } =
          await renderAuthenticatedProvider(
            queryClient,
          );

        clearTerminationMockCalls();

        cancelQueriesSpy.mockClear();

        await act(async () => {
          await result.current.logout();
        });

        expect(
          mockedBlockAuthenticatedRequests,
        ).toHaveBeenCalledTimes(1);

        expect(
          cancelQueriesSpy,
        ).toHaveBeenCalledTimes(1);

        expect(
          mockedDeleteAccessToken,
        ).toHaveBeenCalledTimes(1);

        expect(
          queryClient.getQueryData(
            sensitiveQueryKey,
          ),
        ).toBeUndefined();

        expect(
          result.current.authState.status,
        ).toBe("UNAUTHENTICATED");

        expect(
          mockedAllowAuthenticatedRequests,
        ).not.toHaveBeenCalled();
      },
    );

    test(
      "동시에 두 Auth Failure가 발생해도 Session Cleanup은 한 번만 실행한다",
      async () => {
        const queryClient =
          createTestQueryClient();

        const {
          result,
        } =
          await renderAuthenticatedProvider(
            queryClient,
          );

        clearTerminationMockCalls();

        const deferredDelete =
          createDeferredVoid();

        mockedDeleteAccessToken
          .mockImplementation(
            () =>
              deferredDelete.promise,
          );

        const handler =
          registeredAuthFailureHandler;

        if (!handler) {
          throw new Error(
            "Auth Failure Handler가 등록되지 않았습니다.",
          );
        }

        const firstTermination =
          handler();

        const secondTermination =
          handler();

        await waitFor(() => {
          expect(
            mockedDeleteAccessToken,
          ).toHaveBeenCalledTimes(1);
        });

        expect(
          mockedBlockAuthenticatedRequests,
        ).toHaveBeenCalledTimes(1);

        await act(async () => {
          deferredDelete.resolve();

          await Promise.all([
            firstTermination,
            secondTermination,
          ]);
        });

        expect(
          mockedDeleteAccessToken,
        ).toHaveBeenCalledTimes(1);

        expect(
          result.current.authState.status,
        ).toBe("UNAUTHENTICATED");
      },
    );

    test(
        "401 강제 종료 중 Token 삭제 실패 시 안내를 한 번만 표시하고 재시도할 수 있다",
        async () => {
            const queryClient =
            createTestQueryClient();

            const {
            result,
            } =
            await renderAuthenticatedProvider(
                queryClient,
            );

            clearTerminationMockCalls();

            const alertSpy =
            jest.spyOn(
                Alert,
                "alert",
            ).mockImplementation(
                () => undefined,
            );

            mockedDeleteAccessToken
            .mockRejectedValueOnce(
                new Error(
                "SecureStore deletion failed",
                ),
            )
            .mockResolvedValueOnce(
                undefined,
            );

            const handler =
            registeredAuthFailureHandler;

            if (!handler) {
            throw new Error(
                "Auth Failure Handler가 등록되지 않았습니다.",
            );
            }

            await act(async () => {
            await Promise.all([
                handler(),
                handler(),
            ]);
            });

            expect(
            mockedDeleteAccessToken,
            ).toHaveBeenCalledTimes(1);

            expect(
            mockedAllowAuthenticatedRequests,
            ).toHaveBeenCalledTimes(1);

            expect(
            alertSpy,
            ).toHaveBeenCalledTimes(1);

            expect(
            result.current.authState.status,
            ).toBe("AUTHENTICATED");

            const buttons =
            alertSpy.mock.calls[0]?.[2];

            const retryButton =
            buttons?.find(
                (button) =>
                button.text === "다시 시도",
            );

            if (!retryButton?.onPress) {
            throw new Error(
                "재시도 버튼을 찾을 수 없습니다.",
            );
            }

            retryButton.onPress();

            await waitFor(() => {
            expect(
                result.current.authState.status,
            ).toBe("UNAUTHENTICATED");
            });

            expect(
            mockedDeleteAccessToken,
            ).toHaveBeenCalledTimes(2);

            alertSpy.mockRestore();
        },
    );

    test(
      "SecureStore Token 삭제가 실패하면 Session과 Cache를 유지하고 요청 Gate를 다시 연다",
      async () => {
        const queryClient =
          createTestQueryClient();

        const sensitiveQueryKey = [
          "user",
          "profile",
        ] as const;

        const cachedUser = {
          userId: 1,
        };

        queryClient.setQueryData(
          sensitiveQueryKey,
          cachedUser,
        );

        const {
          result,
        } =
          await renderAuthenticatedProvider(
            queryClient,
          );

        clearTerminationMockCalls();

        const deletionError =
          new Error(
            "SecureStore deletion failed",
          );

        mockedDeleteAccessToken
          .mockRejectedValue(
            deletionError,
          );

        let logoutError:
          unknown = null;

        await act(async () => {
          try {
            await result.current.logout();
          } catch (error) {
            logoutError = error;
          }
        });

        expect(logoutError).toBe(
          deletionError,
        );

        expect(
          mockedBlockAuthenticatedRequests,
        ).toHaveBeenCalledTimes(1);

        expect(
          mockedAllowAuthenticatedRequests,
        ).toHaveBeenCalledTimes(1);

        expect(
          queryClient.getQueryData(
            sensitiveQueryKey,
          ),
        ).toEqual(cachedUser);

        expect(
          result.current.authState,
        ).toEqual({
          status: "AUTHENTICATED",
          session: MAIN_SESSION,
        });
      },
    );

    test(
      "기존 Session Cleanup 중 새 로그인에 성공하면 Cleanup 완료 후 새 Token을 저장한다",
      async () => {
        const queryClient =
          createTestQueryClient();

        const {
          result,
        } =
          await renderAuthenticatedProvider(
            queryClient,
          );

        clearTerminationMockCalls();

        const deferredDelete =
          createDeferredVoid();

        mockedDeleteAccessToken
          .mockImplementation(
            () =>
              deferredDelete.promise,
          );

        const handler =
          registeredAuthFailureHandler;

        if (!handler) {
          throw new Error(
            "Auth Failure Handler가 등록되지 않았습니다.",
          );
        }

        const terminationPromise =
          handler();

        await waitFor(() => {
          expect(
            mockedDeleteAccessToken,
          ).toHaveBeenCalledTimes(1);
        });

        const establishPromise =
          result.current.establishSession(
            LOGIN_B_RESPONSE,
          );

        expect(
          mockedSaveAccessToken,
        ).not.toHaveBeenCalled();

        await act(async () => {
          deferredDelete.resolve();

          await Promise.all([
            terminationPromise,
            establishPromise,
          ]);
        });

        expect(
          mockedSaveAccessToken,
        ).toHaveBeenCalledTimes(1);

        expect(
          mockedSaveAccessToken,
        ).toHaveBeenCalledWith(
          "TOKEN_B",
        );

        expect(
          mockedAllowAuthenticatedRequests,
        ).toHaveBeenCalledTimes(1);

        expect(
          result.current.authState,
        ).toEqual({
          status: "AUTHENTICATED",
          session: {
            user:
              LOGIN_B_RESPONSE.user,
            has_selected_interests:
              true,
            next_step: "MAIN",
          },
        });
      },
    );
  },
);
