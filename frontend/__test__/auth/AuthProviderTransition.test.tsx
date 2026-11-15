import {
  deferred, getSession, loginB, mockStorage, renderAuth, resetHarness,
  sessionA, sessionB, storageSet,
} from "../helpers/authHarness";
import { act, waitFor } from "@testing-library/react-native";
import { areAuthenticatedRequestsBlocked, getAuthEpoch } from "../../src/shared/handler/authRequestGate";
import { AUTH_STORAGE_KEY } from "../../src/shared/storage/tokenStorage";


beforeEach(resetHarness);

test("관심사 선택 완료와 같은 로그인 세션 재검증을 반영한다", async () => {
  getSession.mockResolvedValueOnce({ ...sessionA, has_selected_interests: false, next_step: "INTEREST_SELECTION" });
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  await act(() => result.current.completeInterestSelection());
  expect(result.current.authState).toEqual({ status: "AUTHENTICATED", session: sessionA });
  await act(async () => result.current.revalidateSession());
  expect(result.current.authState).toEqual({ status: "AUTHENTICATED", session: sessionA });
});
test("이전 계정의 늦은 재검증은 새 계정 상태를 바꾸지 않는다", async () => {
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  const previous = deferred<typeof sessionA>();
  getSession.mockReturnValueOnce(previous.promise);
  let revalidation!: Promise<unknown>;
  await act(() => { revalidation = result.current.revalidateSession().catch(error => error); });
  await act(async () => result.current.establishSession(loginB));
  await act(async () => { previous.resolve(sessionA); await revalidation; });
  expect(result.current.authState).toEqual({ status: "AUTHENTICATED", session: sessionB });
});
test("로그아웃 중 도착한 재검증이 인증을 되살리지 않는다", async () => {
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  const previous = deferred<typeof sessionA>();
  getSession.mockReturnValueOnce(previous.promise);
  let revalidation!: Promise<unknown>;
  await act(() => { revalidation = result.current.revalidateSession().catch(error => error); });
  await act(async () => result.current.clearLocalSession());
  await act(async () => { previous.resolve(sessionA); await revalidation; });
  expect(result.current.authState.status).toBe("UNAUTHENTICATED");
});
test("새 토큰 저장이 끝나기 전에는 인증 완료로 표시하지 않는다", async () => {
  const { result } = await renderAuth(null);
  await waitFor(() => expect(result.current.authState.status).toBe("UNAUTHENTICATED"));
  const stored = deferred<void>();
  storageSet.mockImplementationOnce(async (key, value) => { await stored.promise; mockStorage.set(key, value); });
  let login!: Promise<void>;
  await act(() => { login = result.current.establishSession(loginB); });
  await waitFor(() => expect(storageSet).toHaveBeenCalled());
  expect(result.current.authState.status).not.toBe("AUTHENTICATED");
  expect(areAuthenticatedRequestsBlocked()).toBe(true);
  await act(async () => { stored.resolve(); await login; });
  expect(result.current.authState).toEqual({ status: "AUTHENTICATED", session: sessionB });
});
test("과거 로그인 응답은 현재 계정 토큰을 덮어쓰지 못한다", async () => {
  const { result } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  const oldEpoch = getAuthEpoch();
  await act(async () => result.current.establishSession(loginB));
  await act(async () => {
    await expect(result.current.establishSession({ ...loginB, access_token: "old", _requestEpoch: oldEpoch })).rejects.toThrow();
  });
  expect(JSON.parse(mockStorage.get(AUTH_STORAGE_KEY)!).access_token).toBe("access-B");
  expect(result.current.authState).toEqual({ status: "AUTHENTICATED", session: sessionB });
});
test("취소된 A 조회의 늦은 결과가 B의 같은 Cache 키를 오염시키지 않는다", async () => {
  const { result, client } = await renderAuth();
  await waitFor(() => expect(result.current.authState.status).toBe("AUTHENTICATED"));
  const response = deferred<string>();
  const previous = client.fetchQuery({ queryKey: ["personalized"], queryFn: () => response.promise }).catch(error => error);
  await act(async () => result.current.establishSession(loginB));
  client.setQueryData(["personalized"], "B");
  response.resolve("A");
  await previous;
  expect(client.getQueryData(["personalized"])).toBe("B");
});
