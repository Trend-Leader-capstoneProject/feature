import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { getAuthSession } from "../../features/auth/api/getAuthSession";
import type {
  LoginResponse,
  SessionResponse,
} from "../../features/auth/types/auth";
import { registerAuthFailureHandler } from "../../shared/handler/authFailureHandler";
import {
  deleteAccessToken,
  getAccessToken,
  saveAccessToken,
} from "../../shared/storage/tokenStorage";


export type AuthState =
  | {
      status: "RESTORING";
    }
  | {
      status: "UNAUTHENTICATED";
    }
  | {
      status: "AUTHENTICATED";
      session: SessionResponse;
    }
  | {
      status: "RESTORE_ERROR";
    };

interface AuthContextValue {
  authState: AuthState;
  establishSession: (
    loginResponse: LoginResponse,
  ) => Promise<void>;
  restoreSession: () => Promise<void>;
  revalidateSession: () => Promise<void>;
  completeInterestSelection: () => void;
  logout: () => Promise<void>;
}

const AuthContext =
  createContext<AuthContextValue | null>(null);

function isUnauthorizedError(
  error: unknown,
): boolean {
  return (
    axios.isAxiosError(error) &&
    error.response?.status === 401
  );
}

function toSessionResponse(
  loginResponse: LoginResponse,
): SessionResponse {
  return {
    user: loginResponse.user,
    has_selected_interests:
      loginResponse.has_selected_interests,
    next_step: loginResponse.next_step,
  };
}

export function AuthProvider({
  children,
}: PropsWithChildren) {
  const queryClient = useQueryClient();

  const [authState, setAuthState] =
    useState<AuthState>({
      status: "RESTORING",
    });

  const sessionTerminationPromiseRef =
    useRef<Promise<void> | null>(null);

  const sessionTerminationCompletedRef =
    useRef(false);

  const initialRestoreStartedRef =
    useRef(false);

  const terminateSession =
    useCallback(async (): Promise<void> => {
      if (
        sessionTerminationCompletedRef.current
      ) {
        return;
      }

      if (
        sessionTerminationPromiseRef.current
      ) {
        await sessionTerminationPromiseRef.current;
        return;
      }

      const terminationPromise =
        (async (): Promise<void> => {
          await queryClient.cancelQueries();

          await deleteAccessToken();

          queryClient.removeQueries();

          sessionTerminationCompletedRef.current =
            true;

          setAuthState({
            status: "UNAUTHENTICATED",
          });
        })();

      sessionTerminationPromiseRef.current =
        terminationPromise;

      try {
        await terminationPromise;
      } finally {
        if (
          sessionTerminationPromiseRef.current ===
          terminationPromise
        ) {
          sessionTerminationPromiseRef.current =
            null;
        }
      }
    }, [queryClient]);

  const establishSession =
    useCallback(
      async (
        loginResponse: LoginResponse,
      ): Promise<void> => {
        const activeTermination =
          sessionTerminationPromiseRef.current;

        if (activeTermination) {
          await activeTermination;
        }

        await saveAccessToken(
          loginResponse.access_token,
        );

        sessionTerminationCompletedRef.current =
          false;

        setAuthState({
          status: "AUTHENTICATED",
          session:
            toSessionResponse(loginResponse),
        });
      },
      [],
    );

  const restoreSession =
    useCallback(async (): Promise<void> => {
      setAuthState({
        status: "RESTORING",
      });

      try {
        const accessToken =
          await getAccessToken();

        if (!accessToken) {
          setAuthState({
            status: "UNAUTHENTICATED",
          });
          return;
        }

        try {
          const session =
            await getAuthSession();

          setAuthState({
            status: "AUTHENTICATED",
            session,
          });
        } catch (error) {
          if (
            isUnauthorizedError(error)
          ) {
            try {
              await terminateSession();
            } catch {
              setAuthState({
                status: "RESTORE_ERROR",
              });
            }

            return;
          }

          setAuthState({
            status: "RESTORE_ERROR",
          });
        }
      } catch {
        setAuthState({
          status: "RESTORE_ERROR",
        });
      }
    }, [terminateSession]);

  const revalidateSession =
    useCallback(async (): Promise<void> => {
      const accessToken =
        await getAccessToken();

      if (!accessToken) {
        await terminateSession();
        return;
      }

      try {
        const session =
          await getAuthSession();

        setAuthState({
          status: "AUTHENTICATED",
          session,
        });
      } catch (error) {
        if (
          isUnauthorizedError(error)
        ) {
          await terminateSession();
          return;
        }

        throw error;
      }
    }, [terminateSession]);

  const completeInterestSelection =
    useCallback((): void => {
      setAuthState((currentState) => {
        if (
          currentState.status !==
          "AUTHENTICATED"
        ) {
          return currentState;
        }

        return {
          status: "AUTHENTICATED",
          session: {
            ...currentState.session,
            has_selected_interests: true,
            next_step: "MAIN",
          },
        };
      });
    }, []);

  const logout =
    useCallback(async (): Promise<void> => {
      await terminateSession();
    }, [terminateSession]);

  useEffect(() => {
    return registerAuthFailureHandler(
      terminateSession,
    );
  }, [terminateSession]);

  useEffect(() => {
    if (
      initialRestoreStartedRef.current
    ) {
      return;
    }

    initialRestoreStartedRef.current =
      true;

    void restoreSession();
  }, [restoreSession]);

  const contextValue =
    useMemo<AuthContextValue>(
      () => ({
        authState,
        establishSession,
        restoreSession,
        revalidateSession,
        completeInterestSelection,
        logout,
      }),
      [
        authState,
        establishSession,
        restoreSession,
        revalidateSession,
        completeInterestSelection,
        logout,
      ],
    );

  return (
    <AuthContext.Provider
      value={contextValue}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context =
    useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth는 AuthProvider 내부에서 사용해야 합니다.",
    );
  }

  return context;
}
