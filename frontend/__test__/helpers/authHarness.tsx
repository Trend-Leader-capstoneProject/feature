import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react-native";
import type { PropsWithChildren } from "react";
import * as SecureStore from "expo-secure-store";
import { AuthProvider, useAuth } from "../../src/app/providers/AuthProvider";
import { getAuthSession } from "../../src/features/auth/api/getAuthSession";
import type { AuthSuccessResponse, SessionResponse, TokenPair } from "../../src/features/auth/types/auth";
import { publicApiClient } from "../../src/shared/api/publicApiClient";
import { advanceAuthEpoch } from "../../src/shared/handler/authRequestGate";
import { AUTH_STORAGE_KEY, type AuthBundle } from "../../src/shared/storage/tokenStorage";

export const mockStorage = new Map<string, string>();
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(async (key: string) => mockStorage.get(key) ?? null),
  setItemAsync: jest.fn(async (key: string, value: string) => { mockStorage.set(key, value); }),
  deleteItemAsync: jest.fn(async (key: string) => { mockStorage.delete(key); }),
}));
jest.mock("../../src/features/auth/api/getAuthSession", () => ({ getAuthSession: jest.fn() }));
jest.mock("../../src/shared/api/publicApiClient", () => ({ publicApiClient: { post: jest.fn() } }));

export const pairA: TokenPair = {
  access_token: "access-A", refresh_token: "refresh-A", token_type: "Bearer",
  access_expires_at: "2030-01-01T00:15:00Z", refresh_expires_at: "2030-01-31T00:00:00Z",
};
export const pairB: TokenPair = { ...pairA, access_token: "access-B", refresh_token: "refresh-B" };
export const sessionA: SessionResponse = {
  user: { user_id: 1, login_id: "user_a", name: "private A", status: "ACTIVE" },
  has_selected_interests: true, next_step: "MAIN",
};
export const sessionB: SessionResponse = {
  ...sessionA, user: { ...sessionA.user, user_id: 2, login_id: "user_b", name: "private B" },
};
export const loginB: AuthSuccessResponse = { ...pairB, ...sessionB };
export const readyA: AuthBundle = { ...pairA, schema_version: 1, phase: "READY" };
export const storageGet = jest.mocked(SecureStore.getItemAsync);
export const storageSet = jest.mocked(SecureStore.setItemAsync);
export const storageDelete = jest.mocked(SecureStore.deleteItemAsync);
export const getSession = jest.mocked(getAuthSession);
export const serverPost = jest.mocked(publicApiClient.post);
export function resetHarness() {
  jest.resetAllMocks();
  advanceAuthEpoch();
  mockStorage.clear();
  storageGet.mockImplementation(async key => mockStorage.get(key) ?? null);
  storageSet.mockImplementation(async (key, value) => { mockStorage.set(key, value); });
  storageDelete.mockImplementation(async key => { mockStorage.delete(key); });
  getSession.mockResolvedValue(sessionA);
  serverPost.mockResolvedValue({ data: { data: null } });
}
export async function renderAuth(bundle: AuthBundle | null = readyA) {
  if (bundle) mockStorage.set(AUTH_STORAGE_KEY, JSON.stringify(bundle));
  const client = new QueryClient({ defaultOptions: {
    queries: { retry: false, gcTime: Infinity }, mutations: { retry: false },
  } });
  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}><AuthProvider>{children}</AuthProvider></QueryClientProvider>;
  }
  return { ...await renderHook(() => useAuth(), { wrapper: Wrapper }), client };
}
export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
