import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  createContext, type PropsWithChildren, useCallback, useContext,
  useEffect, useMemo, useRef, useState,
} from "react";
import { Alert } from "react-native";
import { getAuthSession } from "../../features/auth/api/getAuthSession";
import type { AuthSuccessResponse, SessionResponse } from "../../features/auth/types/auth";
import { registerAuthFailureHandler } from "../../shared/handler/authFailureHandler";
import {
  advanceAuthEpoch, allowAuthenticatedRequests, assertAuthEpoch,
  blockAuthenticatedRequests, getAuthEpoch, StaleAuthOperationError,
} from "../../shared/handler/authRequestGate";
import { registerAuthStorageFailureHandler } from "../../shared/handler/authStorageFailureHandler";
import {
  AuthStorageError, cleanLegacyAccessToken, clearAuthBundle, markAuthPhase,
  readAuthBundle, saveTokenPair,
} from "../../shared/storage/tokenStorage";
import { publicApiClient } from "../../shared/api/publicApiClient";

export type AuthState =
  | { status: "RESTORING" }
  | { status: "UNAUTHENTICATED" }
  | { status: "AUTHENTICATED"; session: SessionResponse }
  | { status: "RESTORE_ERROR"; kind?: "STORAGE" | "NETWORK" };
interface AuthContextValue {
  authState: AuthState;
  establishSession: (response: AuthSuccessResponse) => Promise<void>;
  restoreSession: () => Promise<void>;
  revalidateSession: () => Promise<void>;
  completeInterestSelection: () => void;
  logout: () => Promise<void>;
  clearLocalSession: () => Promise<void>;
}
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [authState, setAuthState] = useState<AuthState>({ status: "RESTORING" });
  const terminationRef = useRef<Promise<void> | null>(null);
  const mounted = useRef(true);
  const initialRestore = useRef(false);
  const recovery = useCallback(() => {
    blockAuthenticatedRequests();
    queryClient.clear();
    setAuthState({ status: "RESTORE_ERROR", kind: "STORAGE" });
  }, [queryClient]);

  const terminate = useCallback((server = false): Promise<void> => {
    if (terminationRef.current) return terminationRef.current;
    const epoch = advanceAuthEpoch();
    setAuthState({ status: "RESTORING" });
    const promise = (async () => {
      let confirmed = !server;
      try {
        if (server) {
          try {
            const bundle = await readAuthBundle(epoch);
            await markAuthPhase("TERMINATING", epoch);
            if (bundle) {
              await publicApiClient.post("/auth/logout", { refresh_token: bundle.refresh_token });
              confirmed = true;
            } else confirmed = true;
          } catch { /* 기기 정리 후 서버 종료 미확인을 별도로 안내한다. */ }
        }
        await queryClient.cancelQueries().catch(() => undefined);
        queryClient.clear();
        await clearAuthBundle(epoch);
        assertAuthEpoch(epoch);
        if (mounted.current) setAuthState({ status: "UNAUTHENTICATED" });
        if (!confirmed) Alert.alert("기기에서 로그아웃했습니다", "서버의 로그인 종료는 확인하지 못했습니다.");
      } catch (error) {
        if (!(error instanceof StaleAuthOperationError)) recovery();
        throw error;
      }
    })();
    terminationRef.current = promise;
    void promise.finally(() => {
      if (terminationRef.current === promise) terminationRef.current = null;
    }).catch(() => undefined);
    return promise;
  }, [queryClient, recovery]);

  const establishSession = useCallback(async (response: AuthSuccessResponse) => {
    if (response._requestEpoch !== undefined) assertAuthEpoch(response._requestEpoch);
    if (terminationRef.current) await terminationRef.current;
    if (response._requestEpoch !== undefined) assertAuthEpoch(response._requestEpoch);
    const epoch = advanceAuthEpoch();
    setAuthState({ status: "RESTORING" });
    await queryClient.cancelQueries().catch(() => undefined);
    queryClient.clear();
    try {
      await saveTokenPair(response, epoch);
      await cleanLegacyAccessToken(epoch);
      assertAuthEpoch(epoch);
      allowAuthenticatedRequests();
      setAuthState({ status: "AUTHENTICATED", session: {
        user: response.user, has_selected_interests: response.has_selected_interests,
        next_step: response.next_step,
      } });
    } catch (error) {
      if (error instanceof StaleAuthOperationError || epoch !== getAuthEpoch()) throw error;
      try { await clearAuthBundle(epoch); setAuthState({ status: "UNAUTHENTICATED" }); }
      catch (cleanupError) {
        if (!(cleanupError instanceof StaleAuthOperationError) && epoch === getAuthEpoch()) recovery();
      }
      throw error;
    }
  }, [queryClient, recovery]);

  const restoreSession = useCallback(async () => {
    if (terminationRef.current) { await terminationRef.current; return; }
    const epoch = advanceAuthEpoch();
    setAuthState({ status: "RESTORING" });
    try {
      const bundle = await readAuthBundle(epoch);
      await cleanLegacyAccessToken(epoch);
      assertAuthEpoch(epoch);
      if (!bundle) { setAuthState({ status: "UNAUTHENTICATED" }); return; }
      if (bundle.phase !== "READY") { await terminate(); return; }
      allowAuthenticatedRequests();
      const session = await getAuthSession();
      assertAuthEpoch(epoch);
      setAuthState({ status: "AUTHENTICATED", session });
    } catch (error) {
      if (error instanceof StaleAuthOperationError || epoch !== getAuthEpoch()) return;
      if ((error instanceof AuthStorageError && error.kind === "CORRUPT") ||
        (axios.isAxiosError(error) && error.response?.status === 401)) {
        await terminate().catch(() => undefined);
      } else {
        blockAuthenticatedRequests();
        setAuthState({ status: "RESTORE_ERROR", kind: error instanceof AuthStorageError ? "STORAGE" : "NETWORK" });
      }
    }
  }, [terminate]);

  const revalidateSession = useCallback(async () => {
    const epoch = getAuthEpoch();
    try {
      const session = await getAuthSession();
      assertAuthEpoch(epoch);
      setAuthState({ status: "AUTHENTICATED", session });
    } catch (error) {
      if (epoch !== getAuthEpoch() || error instanceof StaleAuthOperationError) return;
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        await terminate();
        return;
      }
      throw error;
    }
  }, [terminate]);
  const completeInterestSelection = useCallback(() => {
    setAuthState(current => current.status !== "AUTHENTICATED" ? current : {
      ...current, session: { ...current.session, has_selected_interests: true, next_step: "MAIN" },
    });
  }, []);

  useEffect(() => {
    mounted.current = true;
    const unregisterFailure = registerAuthFailureHandler(() => terminate());
    const unregisterStorage = registerAuthStorageFailureHandler(recovery);
    return () => { mounted.current = false; unregisterFailure(); unregisterStorage(); };
  }, [recovery, terminate]);
  useEffect(() => {
    if (!initialRestore.current) { initialRestore.current = true; void restoreSession(); }
  }, [restoreSession]);

  const logout = useCallback(() => terminate(true), [terminate]);
  const clearLocalSession = useCallback(() => terminate(), [terminate]);
  const value = useMemo(() => ({
    authState, establishSession, restoreSession, revalidateSession,
    completeInterestSelection, logout, clearLocalSession,
  }), [authState, establishSession, restoreSession, revalidateSession, completeInterestSelection, logout, clearLocalSession]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth는 AuthProvider 내부에서 사용해야 합니다.");
  return context;
}
