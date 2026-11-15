import {
  AxiosError, AxiosHeaders, type AxiosAdapter, type InternalAxiosRequestConfig,
} from "axios";
import * as SecureStore from "expo-secure-store";
import { authenticatedApiClient } from "../../src/shared/api/authenticatedApiClient";
import { publicApiClient } from "../../src/shared/api/publicApiClient";
import { login } from "../../src/features/auth/api/login";
import { notifyAuthFailure } from "../../src/shared/handler/authFailureHandler";
import {
  advanceAuthEpoch, allowAuthenticatedRequests, areAuthenticatedRequestsBlocked,
  StaleAuthOperationError,
} from "../../src/shared/handler/authRequestGate";
import { AUTH_STORAGE_KEY, saveTokenPair } from "../../src/shared/storage/tokenStorage";
import type { TokenPair } from "../../src/features/auth/types/auth";

const mockStorage = new Map<string, string>();
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(async (key: string) => mockStorage.get(key) ?? null),
  setItemAsync: jest.fn(async (key: string, value: string) => { mockStorage.set(key, value); }),
  deleteItemAsync: jest.fn(async (key: string) => { mockStorage.delete(key); }),
}));
jest.mock("../../src/app/config/apiConfig", () => ({ API_BASE_URL: "http://127.0.0.1:8000/api" }));
jest.mock("../../src/shared/handler/authFailureHandler", () => ({ notifyAuthFailure: jest.fn() }));
const pairA: TokenPair = {
  access_token: "A", refresh_token: "refresh-A", token_type: "Bearer",
  access_expires_at: "2030-01-01T00:15:00Z", refresh_expires_at: "2030-01-31T00:00:00Z",
};
const pairB = { ...pairA, access_token: "B", refresh_token: "refresh-B" };
const originalAuth = authenticatedApiClient.defaults.adapter;
const originalPublic = publicApiClient.defaults.adapter;
const storageGet = jest.mocked(SecureStore.getItemAsync);
const storageSet = jest.mocked(SecureStore.setItemAsync);
const failure = jest.mocked(notifyAuthFailure);

function response(config: InternalAxiosRequestConfig, data: unknown = null, status = 200) {
  return { data, status, statusText: String(status), config, headers: new AxiosHeaders() };
}
function reject(config: InternalAxiosRequestConfig, status: number, reason: string): never {
  throw new AxiosError(reason, undefined, config, undefined,
    response(config, { success: false, statusCode: status, data: { reason } }, status));
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const authAdapter = jest.fn<ReturnType<AxiosAdapter>, Parameters<AxiosAdapter>>();
const publicAdapter = jest.fn<ReturnType<AxiosAdapter>, Parameters<AxiosAdapter>>();
beforeEach(async () => {
  jest.resetAllMocks();
  advanceAuthEpoch();
  mockStorage.clear();
  storageGet.mockImplementation(async key => mockStorage.get(key) ?? null);
  storageSet.mockImplementation(async (key, value) => { mockStorage.set(key, value); });
  jest.mocked(SecureStore.deleteItemAsync).mockImplementation(async key => { mockStorage.delete(key); });
  await saveTokenPair(pairA);
  allowAuthenticatedRequests();
  authenticatedApiClient.defaults.adapter = authAdapter;
  publicApiClient.defaults.adapter = publicAdapter;
  authAdapter.mockImplementation(async config => response(config));
  publicAdapter.mockImplementation(async config => response(config, { data: pairB }));
});
afterAll(() => {
  authenticatedApiClient.defaults.adapter = originalAuth;
  publicApiClient.defaults.adapter = originalPublic;
});
function expireA() {
  authAdapter.mockImplementation(async config => config.headers.get("Authorization") === "Bearer A"
    ? reject(config, 401, "ACCESS_TOKEN_EXPIRED") : response(config, "success"));
}

test("보호 요청에는 현재 묶음의 Access만 보낸다", async () => {
  await authenticatedApiClient.get("/protected");
  expect(authAdapter.mock.calls[0][0].headers.get("Authorization")).toBe("Bearer A");
  expect(publicAdapter).not.toHaveBeenCalled();
});
test("유효 기간 만료만 공유 갱신하고 토큰 저장 후 원래 요청을 한 번 재시도한다", async () => {
  expireA();
  publicAdapter.mockImplementationOnce(async config => {
    expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!).phase).toBe("REFRESHING");
    expect(JSON.parse(config.data)).toEqual({ refresh_token: "refresh-A" });
    return response(config, { data: pairB });
  });
  expect((await authenticatedApiClient.get("/protected")).data).toBe("success");
  expect(authAdapter).toHaveBeenCalledTimes(2);
  expect(publicAdapter).toHaveBeenCalledTimes(1);
  expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!).access_token).toBe("B");
});
test("동시에 만료된 요청들은 하나의 Refresh 전송을 공유한다", async () => {
  expireA();
  await Promise.all([authenticatedApiClient.get("/one"), authenticatedApiClient.get("/two")]);
  expect(publicAdapter).toHaveBeenCalledTimes(1);
  expect(authAdapter).toHaveBeenCalledTimes(4);
});
test.each([401, 403, 500])("일반 %i 오류는 자동 갱신하지 않는다", async status => {
  authAdapter.mockImplementation(async config => reject(config, status, status === 401 ? "SESSION_REVOKED" : "OTHER"));
  await expect(authenticatedApiClient.get("/protected")).rejects.toThrow();
  expect(publicAdapter).not.toHaveBeenCalled();
  expect(failure).toHaveBeenCalledTimes(status === 401 ? 1 : 0);
});
test("재시도된 요청도 만료되면 갱신을 반복하지 않는다", async () => {
  authAdapter.mockImplementation(async config => reject(config, 401, "ACCESS_TOKEN_EXPIRED"));
  await expect(authenticatedApiClient.get("/protected")).rejects.toThrow();
  expect(authAdapter).toHaveBeenCalledTimes(2);
  expect(publicAdapter).toHaveBeenCalledTimes(1);
  expect(failure).toHaveBeenCalledTimes(1);
});
test("이전 토큰의 늦은 401은 새 토큰을 종료하지 않는다", async () => {
  const sent = deferred<void>(), release = deferred<void>();
  authAdapter.mockImplementationOnce(async config => { sent.resolve(); await release.promise; return reject(config, 401, "SESSION_REVOKED"); });
  const request = authenticatedApiClient.get("/protected").catch(error => error);
  await sent.promise;
  await saveTokenPair(pairB);
  release.resolve();
  await request;
  expect(failure).not.toHaveBeenCalled();
  expect(areAuthenticatedRequestsBlocked()).toBe(false);
});
test("갱신 완료 뒤 늦게 도착한 이전 만료 오류는 새 토큰으로만 한 번 재시도한다", async () => {
  const sent = deferred<void>(), release = deferred<void>();
  authAdapter.mockImplementationOnce(async config => { sent.resolve(); await release.promise; return reject(config, 401, "ACCESS_TOKEN_EXPIRED"); });
  const request = authenticatedApiClient.get("/protected");
  await sent.promise; await saveTokenPair(pairB); release.resolve();
  await request;
  expect(publicAdapter).not.toHaveBeenCalled();
  expect(authAdapter).toHaveBeenCalledTimes(2);
  expect(authAdapter.mock.calls[1][0].headers.get("Authorization")).toBe("Bearer B");
});
test("갱신 전 표시 저장에 실패하면 Refresh를 전송하지 않는다", async () => {
  expireA(); storageSet.mockRejectedValueOnce(new Error("keystore write failed"));
  await expect(authenticatedApiClient.get("/protected")).rejects.toThrow();
  expect(publicAdapter).not.toHaveBeenCalled();
  expect(areAuthenticatedRequestsBlocked()).toBe(true);
});
test("교체 응답을 잃으면 이전 Refresh를 자동 재전송하지 않는다", async () => {
  expireA();
  publicAdapter.mockImplementation(async config => { throw new AxiosError("response lost", "ERR_NETWORK", config); });
  await expect(authenticatedApiClient.get("/protected")).rejects.toThrow();
  await expect(authenticatedApiClient.get("/protected")).rejects.toThrow();
  expect(publicAdapter).toHaveBeenCalledTimes(1);
  expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!).phase).toBe("REFRESHING");
  expect(failure).toHaveBeenCalledTimes(1);
});
test("서버가 미적용을 확인한 503이면 READY를 복구하고 사용자 재시도를 기다린다", async () => {
  expireA();
  publicAdapter.mockImplementationOnce(async config => reject(config, 503, "REFRESH_NOT_APPLIED"));
  await expect(authenticatedApiClient.get("/protected")).rejects.toThrow();
  expect(publicAdapter).toHaveBeenCalledTimes(1);
  expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!).phase).toBe("READY");
  expect(areAuthenticatedRequestsBlocked()).toBe(false);
  expect(failure).not.toHaveBeenCalled();
});
test("새 토큰을 보관하지 못하면 원래 요청을 다시 보내지 않는다", async () => {
  expireA();
  storageSet.mockImplementation(async (key, value) => {
    if (JSON.parse(value).access_token === "B") throw new Error("new tokens lost");
    mockStorage.set(key, value);
  });
  await expect(authenticatedApiClient.get("/protected")).rejects.toThrow();
  expect(authAdapter).toHaveBeenCalledTimes(1);
  expect(publicAdapter).toHaveBeenCalledTimes(1);
  expect(failure).toHaveBeenCalledTimes(1);
});
test("저장소 읽기 실패는 HTTP 전송 전에 보호 접근을 차단한다", async () => {
  storageGet.mockRejectedValueOnce(new Error("keystore unavailable"));
  await expect(authenticatedApiClient.get("/protected")).rejects.toThrow();
  expect(authAdapter).not.toHaveBeenCalled();
  expect(areAuthenticatedRequestsBlocked()).toBe(true);
});
test.each(["get", "call"] as const)("요청 생성 직후 계정이 바뀌면 새 계정으로 전송하지 않는다: %s", async method => {
  const request = (method === "get" ? authenticatedApiClient.get("/protected") : authenticatedApiClient({ url: "/protected" })).catch(error => error);
  advanceAuthEpoch();
  await saveTokenPair(pairB); allowAuthenticatedRequests();
  expect(await request).toBeInstanceOf(StaleAuthOperationError);
  expect(authAdapter).not.toHaveBeenCalled();
});
test("이전 읽기의 늦은 실패도 새 인증을 차단하지 않는다", async () => {
  const started = deferred<void>(), finish = deferred<string | null>();
  storageGet.mockImplementationOnce(async () => { started.resolve(); return finish.promise; });
  const oldRequest = authenticatedApiClient.get("/protected").catch(error => error);
  await started.promise;
  advanceAuthEpoch();
  const saving = saveTokenPair(pairB);
  finish.reject(new Error("old keystore failure"));
  await saving; allowAuthenticatedRequests();
  expect(await oldRequest).toBeInstanceOf(StaleAuthOperationError);
  expect(areAuthenticatedRequestsBlocked()).toBe(false);
  expect(failure).not.toHaveBeenCalled();
});
test.each([
  ["http://other.example/protected", undefined],
  ["/protected", "http://other.example/api"],
  ["http://name:password@127.0.0.1:8000/api/protected", undefined],
])("다른 원점·URL 자격증명에는 토큰을 보내지 않는다: %s", async (url, baseURL) => {
  await expect(authenticatedApiClient.get(url!, { baseURL })).rejects.toThrow();
  expect(authAdapter).not.toHaveBeenCalled();
});
test.each(["get", "request", "call"] as const)("인증 interceptor 앞에서 대기한 이전 요청도 새 계정으로 보내지 않는다: %s", async method => {
  const entered = deferred<void>(), release = deferred<void>();
  const handle = authenticatedApiClient.interceptors.request.use(async config => {
    entered.resolve(); await release.promise; return config;
  });
  try {
    const request = (method === "get" ? authenticatedApiClient.get("/protected") :
      method === "request" ? authenticatedApiClient.request({ url: "/protected" }) :
      authenticatedApiClient({ url: "/protected" })).catch(error => error);
    await entered.promise;
    advanceAuthEpoch(); await saveTokenPair(pairB); allowAuthenticatedRequests();
    release.resolve();
    expect(await request).toBeInstanceOf(StaleAuthOperationError);
    expect(authAdapter).not.toHaveBeenCalled();
  } finally { release.resolve(); authenticatedApiClient.interceptors.request.eject(handle); }
});

test("공개 로그인 401은 현재 보호 인증을 종료하지 않는다", async () => {
  publicAdapter.mockImplementation(async config => reject(config, 401, "INVALID_LOGIN"));
  await expect(login({ login_id: "user", password: "wrong password" })).rejects.toThrow();
  expect(failure).not.toHaveBeenCalled();
  expect(areAuthenticatedRequestsBlocked()).toBe(false);
});
