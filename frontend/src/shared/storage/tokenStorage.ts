import * as SecureStore from "expo-secure-store";
import type { TokenPair } from "../../features/auth/types/auth";
import { assertAuthEpoch, getAuthEpoch, StaleAuthOperationError } from "../handler/authRequestGate";

export const AUTH_STORAGE_KEY = "trend-leader.auth-session.v1";
export const LEGACY_ACCESS_TOKEN_KEY = "trend-leader.access-token";
export type AuthPhase = "READY" | "REFRESHING" | "TERMINATING";
export interface AuthBundle extends TokenPair { schema_version: 1; phase: AuthPhase; }
export class AuthStorageError extends Error {
  constructor(public readonly kind: "IO" | "CORRUPT") {
    super(kind === "IO" ? "기기의 로그인 정보를 읽거나 저장하지 못했습니다." : "로그인 저장 정보가 손상됐습니다.");
  }
}
let queue: Promise<unknown> = Promise.resolve();
function serial<T>(epoch: number, action: () => Promise<T>): Promise<T> {
  const operation = queue.then(async () => {
    assertAuthEpoch(epoch);
    let result: T;
    try { result = await action(); }
    catch (error) {
      // 늦은 저장소 오류도 이전 인증의 작업으로 끝내 새 계정을 막지 않는다.
      assertAuthEpoch(epoch);
      throw error;
    }
    assertAuthEpoch(epoch);
    return result;
  });
  queue = operation.catch(() => undefined);
  return operation;
}
function parse(raw: string): AuthBundle {
  let value: unknown;
  try { value = JSON.parse(raw); } catch { throw new AuthStorageError("CORRUPT"); }
  const bundle = value as Partial<AuthBundle> | null;
  if (!bundle || bundle.schema_version !== 1 ||
    !["READY", "REFRESHING", "TERMINATING"].includes(bundle.phase ?? "") ||
    typeof bundle.access_token !== "string" || !bundle.access_token ||
    typeof bundle.refresh_token !== "string" || !bundle.refresh_token ||
    typeof bundle.access_expires_at !== "string" || !Number.isFinite(Date.parse(bundle.access_expires_at)) ||
    typeof bundle.refresh_expires_at !== "string" || !Number.isFinite(Date.parse(bundle.refresh_expires_at)) ||
    bundle.token_type !== "Bearer") throw new AuthStorageError("CORRUPT");
  return bundle as AuthBundle;
}
async function rawRead(): Promise<AuthBundle | null> {
  let raw: string | null;
  try { raw = await SecureStore.getItemAsync(AUTH_STORAGE_KEY); }
  catch { throw new AuthStorageError("IO"); }
  return raw === null ? null : parse(raw);
}
async function rawWrite(bundle: AuthBundle): Promise<void> {
  parse(JSON.stringify(bundle));
  try { await SecureStore.setItemAsync(AUTH_STORAGE_KEY, JSON.stringify(bundle)); }
  catch { throw new AuthStorageError("IO"); }
}
export function readAuthBundle(epoch = getAuthEpoch()): Promise<AuthBundle | null> {
  return serial(epoch, rawRead);
}
export function saveTokenPair(pair: TokenPair, epoch = getAuthEpoch()): Promise<void> {
  const bundle: AuthBundle = {
    schema_version: 1, phase: "READY", token_type: "Bearer",
    access_token: pair.access_token, refresh_token: pair.refresh_token,
    access_expires_at: pair.access_expires_at, refresh_expires_at: pair.refresh_expires_at,
  };
  return serial(epoch, () => rawWrite(bundle));
}
export function markAuthPhase(phase: AuthPhase, epoch = getAuthEpoch()): Promise<void> {
  return serial(epoch, async () => {
    const bundle = await rawRead();
    if (bundle) await rawWrite({ ...bundle, phase });
  });
}
export function cleanLegacyAccessToken(epoch = getAuthEpoch()): Promise<void> {
  return serial(epoch, async () => {
    try { await SecureStore.deleteItemAsync(LEGACY_ACCESS_TOKEN_KEY); }
    catch { throw new AuthStorageError("IO"); }
  });
}
export function clearAuthBundle(epoch = getAuthEpoch()): Promise<void> {
  return serial(epoch, async () => {
    try {
      const bundle = await rawRead();
      if (bundle) await rawWrite({ ...bundle, phase: "TERMINATING" });
    } catch (error) {
      if (error instanceof StaleAuthOperationError) throw error;
    }
    let failed = false;
    for (const key of [AUTH_STORAGE_KEY, LEGACY_ACCESS_TOKEN_KEY]) {
      try { await SecureStore.deleteItemAsync(key); } catch { failed = true; }
    }
    if (failed) throw new AuthStorageError("IO");
  });
}
export async function getAccessToken(): Promise<string | null> {
  const bundle = await readAuthBundle();
  if (bundle && bundle.phase !== "READY") throw new AuthStorageError("CORRUPT");
  return bundle?.access_token ?? null;
}
export const deleteAccessToken = clearAuthBundle;
