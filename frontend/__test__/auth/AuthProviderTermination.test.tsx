import {
  deferred, loginB, mockStorage, renderAuth, resetHarness, serverPost, sessionB, storageDelete,
} from "../helpers/authHarness";
import { act, waitFor } from "@testing-library/react-native";
import { Alert } from "react-native";
import { notifyAuthFailure } from "../../src/shared/handler/authFailureHandler";
import { areAuthenticatedRequestsBlocked } from "../../src/shared/handler/authRequestGate";
import { AUTH_STORAGE_KEY } from "../../src/shared/storage/tokenStorage";


beforeEach(resetHarness);

test("로그아웃 표시를 먼저 저장하고 서버 종료·기기/Cache 삭제를 완료한다", async () => {
  const { result, client } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  client.setQueryData(["personalized"], "private A");
  const mutation = client.getMutationCache().build(client, {
    mutationFn: async (_variables: { current_password: string }) => null, gcTime: Infinity,
  });
  await mutation.execute({ current_password: "sensitive-old-input" });
  expect(client.getMutationCache().getAll()).toHaveLength(1);
  serverPost.mockImplementationOnce(async () => {
    expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!).phase).toBe("TERMINATING");
    expect(areAuthenticatedRequestsBlocked()).toBe(true);
    return { data: { data: null } };
  });
  await act(async () => result.current.logout());
  expect(serverPost).toHaveBeenCalledWith("/auth/logout", { refresh_token: "refresh-A" });
  expect(result.current.authState.status).toBe("UNAUTHENTICATED");
  expect(mockStorage.has(AUTH_STORAGE_KEY)).toBe(false);
  expect(client.getQueryData(["personalized"])).toBeUndefined();
  expect(client.getMutationCache().getAll()).toHaveLength(0);
});
test("서버 통신 실패도 로컬 삭제 성공 후 로그아웃하고 미확인을 알린다", async () => {
  const alert = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  serverPost.mockRejectedValueOnce(new Error("offline"));
  await act(async () => result.current.logout());
  expect(result.current.authState.status).toBe("UNAUTHENTICATED");
  expect(mockStorage.has(AUTH_STORAGE_KEY)).toBe(false);
  expect(alert).toHaveBeenCalledWith("기기에서 로그아웃했습니다", "서버의 로그인 종료는 확인하지 못했습니다.");
  alert.mockRestore();
});
test("기기 삭제 실패는 보호 화면과 Gate를 차단하고 재시작 복구가 가능하다", async () => {
  const { result, client } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  client.setQueryData(["private"], "old account");
  storageDelete.mockRejectedValueOnce(new Error("delete failed"));
  await act(async () => { await expect(result.current.clearLocalSession()).rejects.toThrow(); });
  expect(result.current.authState).toEqual({ status: "RESTORE_ERROR", kind: "STORAGE" });
  expect(areAuthenticatedRequestsBlocked()).toBe(true);
  expect(client.getQueryData(["private"])).toBeUndefined();
  expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!).phase).toBe("TERMINATING");
  await act(async () => result.current.restoreSession());
  expect(result.current.authState.status).toBe("UNAUTHENTICATED");
});
test("동시 인증 실패 두 개는 하나의 로컬 정리 작업을 공유한다", async () => {
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  await act(async () => { notifyAuthFailure(); notifyAuthFailure(); });
  await waitFor(() => expect(result.current.authState.status).toBe("UNAUTHENTICATED"));
  expect(storageDelete.mock.calls.filter(([key]) => key === AUTH_STORAGE_KEY)).toHaveLength(1);
});
test("기존 종료가 끝난 뒤 새 계정 토큰을 저장한다", async () => {
  const { result, client } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  const stopped = deferred<{ data: { data: null } }>();
  serverPost.mockReturnValueOnce(stopped.promise);
  client.setQueryData(["private"], "A");
  let logout!: Promise<void>;
  let login!: Promise<void>;
  await act(() => { logout = result.current.logout(); });
  await waitFor(() => expect(serverPost).toHaveBeenCalled());
  await act(() => { login = result.current.establishSession(loginB); });
  await act(async () => { stopped.resolve({ data: { data: null } }); await logout; await login; });
  expect(result.current.authState).toEqual({ status: "AUTHENTICATED", session: sessionB });
  expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!).access_token).toBe("access-B");
  expect(client.getQueryData(["private"])).toBeUndefined();
});
