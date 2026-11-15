import {
  getSession, mockStorage, readyA, renderAuth, resetHarness, serverPost,
  sessionA, storageGet,
} from "../helpers/authHarness";
import { act, waitFor } from "@testing-library/react-native";
import { AxiosError } from "axios";
import { areAuthenticatedRequestsBlocked } from "../../src/shared/handler/authRequestGate";
import { AUTH_STORAGE_KEY, LEGACY_ACCESS_TOKEN_KEY } from "../../src/shared/storage/tokenStorage";


beforeEach(resetHarness);


test("과거 Access만 있으면 재사용하지 않고 정리 후 재로그인한다", async () => {
  mockStorage.set(LEGACY_ACCESS_TOKEN_KEY, "legacy-access");
  const { result } = await renderAuth(null);
  await waitFor(() => expect(result.current.authState.status).toBe("UNAUTHENTICATED"));
  expect(mockStorage.has(LEGACY_ACCESS_TOKEN_KEY)).toBe(false);
  expect(getSession).not.toHaveBeenCalled();
});
test.each([true, false])("READY 세션을 서버 확인 후 복원한다: 관심사 %s", async selected => {
  const session = { ...sessionA, has_selected_interests: selected, next_step: selected ? "MAIN" as const : "INTEREST_SELECTION" as const };
  getSession.mockResolvedValue(session);
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState).toEqual({ status: "AUTHENTICATED", session }));
  expect(areAuthenticatedRequestsBlocked()).toBe(false);
});
test("일반 통신 장애는 READY 정보를 유지하고 재시도를 허용한다", async () => {
  getSession.mockRejectedValueOnce(new Error("offline"));
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState).toEqual({ status: "RESTORE_ERROR", kind: "NETWORK" }));
  expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!)).toEqual(readyA);
  expect(areAuthenticatedRequestsBlocked()).toBe(true);
  await act(async () => result.current.restoreSession());
  expect(result.current.authState.status).toBe("AUTHENTICATED");
});
test("확인된 인증 무효 401은 로컬 정리 후 재로그인한다", async () => {
  getSession.mockRejectedValueOnce(new AxiosError("invalid", undefined, undefined, undefined, {
    status: 401, data: { data: { reason: "SESSION_REVOKED" } },
  } as never));
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("UNAUTHENTICATED"));
  expect(mockStorage.has(AUTH_STORAGE_KEY)).toBe(false);
});
test.each(["REFRESHING", "TERMINATING"] as const)("%s 상태 재시작은 이전 Refresh를 전송하지 않는다", async phase => {
  const { result } = await renderAuth({ ...readyA, phase });
  await waitFor(() => expect(result.current.authState.status).toBe("UNAUTHENTICATED"));
  expect(serverPost).not.toHaveBeenCalled();
  expect(getSession).not.toHaveBeenCalled();
  expect(mockStorage.has(AUTH_STORAGE_KEY)).toBe(false);
});
test("읽기 실패는 보호 접근을 차단하고 저장 내용을 성공으로 처리하지 않는다", async () => {
  storageGet.mockRejectedValueOnce(new Error("keystore unavailable"));
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState).toEqual({ status: "RESTORE_ERROR", kind: "STORAGE" }));
  expect(areAuthenticatedRequestsBlocked()).toBe(true);
  expect(mockStorage.has(AUTH_STORAGE_KEY)).toBe(true);
});
test("손상된 묶음은 인증에 쓰지 않고 삭제 복구한다", async () => {
  mockStorage.set(AUTH_STORAGE_KEY, "{broken-json");
  const { result } = await renderAuth(null);
  await waitFor(() => expect(result.current.authState.status).toBe("UNAUTHENTICATED"));
  expect(getSession).not.toHaveBeenCalled();
  expect(mockStorage.has(AUTH_STORAGE_KEY)).toBe(false);
});
