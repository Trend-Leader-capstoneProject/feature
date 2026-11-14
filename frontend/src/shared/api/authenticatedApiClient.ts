import axios, { type InternalAxiosRequestConfig } from "axios";
import type { TokenPair } from "../../features/auth/types/auth";
import type { CommonResponse } from "../types/api";
import { API_BASE_URL } from "../../app/config/apiConfig";
import { notifyAuthFailure } from "../handler/authFailureHandler";
import {
  assertActiveAuthEpoch, getAuthEpoch, blockAuthenticatedRequests,
  StaleAuthOperationError,
} from "../handler/authRequestGate";
import { notifyAuthStorageFailure } from "../handler/authStorageFailureHandler";
import { markAuthPhase, readAuthBundle, saveTokenPair } from "../storage/tokenStorage";
import { createApiClient } from "./createApiClient";
import { publicApiClient } from "./publicApiClient";

interface AuthConfig extends InternalAxiosRequestConfig {
  authEpoch?: number;
  authAccessToken?: string;
  authRetried?: boolean;
}
const transport = createApiClient();
type EpochConfig = import("axios").AxiosRequestConfig & { authEpoch?: number };
function captureEpoch(config: EpochConfig = {}): EpochConfig {
  return { ...config, authEpoch: config.authEpoch ?? getAuthEpoch() };
}
const dispatch = new Map<PropertyKey, (...args: unknown[]) => unknown>();
for (const method of ["get", "delete", "head", "options"] as const) {
  const original = transport[method].bind(transport);
  dispatch.set(method, (url, config) => original(url as string, captureEpoch(config as EpochConfig)));
}
for (const method of ["post", "put", "patch", "postForm", "putForm", "patchForm"] as const) {
  const original = transport[method].bind(transport);
  dispatch.set(method, (url, data, config) => original(url as string, data, captureEpoch(config as EpochConfig)));
}
dispatch.set("request", config => transport.request(captureEpoch(config as EpochConfig)));
/** 메서드·함수 호출 모두 비동기 interceptor 실행 전에 인증 회차를 고정한다. */
export const authenticatedApiClient = new Proxy(transport, {
  get(target, property, receiver) {
    return dispatch.get(property) ?? Reflect.get(target, property, receiver);
  },
  apply(target, _thisArg, args) {
    return typeof args[0] === "string"
      ? target(args[0], captureEpoch(args[1] as EpochConfig))
      : target(captureEpoch(args[0] as EpochConfig));
  },
});
let activeRefresh: { epoch: number; promise: Promise<void> } | null = null;

function invalidate(): void {
  blockAuthenticatedRequests();
  notifyAuthFailure();
}
export function getErrorReason(error: unknown): string | undefined {
  if (!axios.isAxiosError(error)) return undefined;
  let body = error.response?.data;
  if (body instanceof ArrayBuffer && body.byteLength < 16_384) {
    try { body = JSON.parse(String.fromCharCode(...new Uint8Array(body))); } catch { return undefined; }
  }
  return body?.data?.reason;
}
async function refresh(epoch: number): Promise<void> {
  let bundle;
  try { bundle = await readAuthBundle(epoch); }
  catch (error) {
    if (!(error instanceof StaleAuthOperationError)) notifyAuthStorageFailure();
    throw error;
  }
  assertActiveAuthEpoch(epoch);
  if (!bundle || bundle.phase !== "READY") { invalidate(); throw new Error("다시 로그인해 주세요."); }
  try { await markAuthPhase("REFRESHING", epoch); }
  catch (error) {
    if (!(error instanceof StaleAuthOperationError)) notifyAuthStorageFailure();
    throw error;
  }
  try {
    const result = await publicApiClient.post<CommonResponse<TokenPair>>(
      "/auth/refresh", { refresh_token: bundle.refresh_token },
    );
    assertActiveAuthEpoch(epoch);
    await saveTokenPair(result.data.data, epoch);
  } catch (error) {
    if (error instanceof StaleAuthOperationError || epoch !== getAuthEpoch()) throw error;
    if (axios.isAxiosError(error) && error.response?.status === 503 &&
      getErrorReason(error) === "REFRESH_NOT_APPLIED") {
      try { await saveTokenPair(bundle, epoch); }
      catch (storageError) { notifyAuthStorageFailure(); throw storageError; }
      throw error;
    }
    invalidate(); // 교체 여부 불명확·새 토큰 보관 실패: 이전 Refresh 재전송 금지.
    throw error;
  }
}
function sharedRefresh(epoch: number): Promise<void> {
  if (activeRefresh?.epoch === epoch) return activeRefresh.promise;
  const promise = refresh(epoch);
  const active = { epoch, promise };
  activeRefresh = active;
  void promise.finally(() => { if (activeRefresh === active) activeRefresh = null; }).catch(() => undefined);
  return promise;
}

authenticatedApiClient.interceptors.request.use(async (input) => {
  const config = input as AuthConfig;
  const epoch = config.authEpoch ?? getAuthEpoch();
  assertActiveAuthEpoch(epoch);
  const allowedOrigin = new URL(API_BASE_URL).origin;
  const base = new URL(config.baseURL ?? API_BASE_URL);
  const destination = new URL(config.url ?? "", base.toString());
  if (base.origin !== allowedOrigin || destination.origin !== allowedOrigin ||
      base.username || base.password || destination.username || destination.password || config.auth) {
    throw new Error("허용되지 않은 API 주소입니다.");
  }
  let bundle;
  try { bundle = await readAuthBundle(epoch); }
  catch (error) {
    if (!(error instanceof StaleAuthOperationError)) notifyAuthStorageFailure();
    throw error;
  }
  assertActiveAuthEpoch(epoch);
  if (!bundle) { invalidate(); throw new Error("로그인이 필요합니다."); }
  if (bundle.phase !== "READY") {
    if (activeRefresh?.epoch === epoch) {
      await activeRefresh.promise;
      bundle = await readAuthBundle(epoch);
      assertActiveAuthEpoch(epoch);
    }
    if (!bundle || bundle.phase !== "READY") { invalidate(); throw new Error("다시 로그인해 주세요."); }
  }
  config.authEpoch = epoch;
  config.authAccessToken = bundle.access_token;
  config.headers.set("Authorization", `Bearer ${bundle.access_token}`);
  return config;
});

authenticatedApiClient.interceptors.response.use((response) => {
  const epoch = (response.config as AuthConfig).authEpoch;
  if (epoch !== undefined) assertActiveAuthEpoch(epoch);
  return response;
}, async (error: unknown) => {
  if (!axios.isAxiosError(error)) throw error;
  const config = error.config as AuthConfig | undefined;
  if (!config || config.authEpoch === undefined) throw error;
  assertActiveAuthEpoch(config.authEpoch);
  if (error.response?.status !== 401) throw error;
  let bundle;
  try { bundle = await readAuthBundle(config.authEpoch); }
  catch (storageError) {
    if (!(storageError instanceof StaleAuthOperationError)) notifyAuthStorageFailure();
    throw storageError;
  }
  assertActiveAuthEpoch(config.authEpoch);
  const reason = getErrorReason(error);
  if (bundle?.access_token !== config.authAccessToken) {
    if (bundle?.phase === "READY" && reason === "ACCESS_TOKEN_EXPIRED" && !config.authRetried) {
      config.authRetried = true;
      return authenticatedApiClient.request(config);
    }
    throw error;
  }
  if (reason === "ACCESS_TOKEN_EXPIRED" && !config.authRetried) {
    await sharedRefresh(config.authEpoch);
    assertActiveAuthEpoch(config.authEpoch);
    config.authRetried = true;
    return authenticatedApiClient.request(config);
  }
  invalidate();
  throw error;
});
