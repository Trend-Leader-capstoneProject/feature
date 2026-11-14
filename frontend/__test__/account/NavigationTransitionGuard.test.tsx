import { act, renderHook } from "@testing-library/react-native";
import { BackHandler } from "react-native";
import { useNavigationTransitionGuard, type TransitionNavigation } from "../../src/features/account/hooks/useNavigationTransitionGuard";
import { useScreenReturn } from "../../src/features/account/hooks/useScreenReturn";

jest.mock("@react-navigation/native", () => ({
  ...jest.requireActual("@react-navigation/native"),
  useFocusEffect: (callback: () => (() => void)) => require("react").useEffect(callback, [callback]),
}));

function navigationHarness() {
  const callbacks = new Map<string, Set<(event: { data: { closing: boolean } }) => void>>();
  const isFocused = jest.fn(() => true);
  const goBack = jest.fn();
  const addListener = (name: string, callback: (event: { data: { closing: boolean } }) => void) => {
    if (!callbacks.has(name)) callbacks.set(name, new Set());
    callbacks.get(name)!.add(callback);
    return () => callbacks.get(name)!.delete(callback);
  };
  return {
    navigation: { addListener, goBack, isFocused } as unknown as TransitionNavigation,
    goBack, isFocused, callbacks,
    emit: async (name: string, closing = false) => {
      await act(() => { callbacks.get(name)?.forEach(callback => callback({ data: { closing } })); });
    },
  };
}

test("진입 완료 전 복귀와 같은 회차의 연속 전환을 막는다", async () => {
  const h = navigationHarness();
  const { result } = await renderHook(() => useNavigationTransitionGuard(h.navigation));
  const action = jest.fn();
  await act(() => result.current.run(action));
  expect(action).not.toHaveBeenCalled();
  await h.emit("transitionEnd", true);
  expect(result.current.disabled).toBe(true);
  await h.emit("transitionEnd");
  expect(result.current.disabled).toBe(false);
  await act(() => { result.current.run(action); result.current.run(action); });
  expect(action).toHaveBeenCalledTimes(1);
  expect(result.current.disabled).toBe(true);
});

test("내 정보 재진입도 focus만으로는 잠금을 풀지 않고 native 완료를 기다린다", async () => {
  const h = navigationHarness();
  const { result } = await renderHook(() => useNavigationTransitionGuard(h.navigation));
  const action = jest.fn();
  await h.emit("transitionEnd");
  await act(() => result.current.run(action));
  await h.emit("transitionStart", true);
  await h.emit("focus");
  await act(() => result.current.run(action));
  expect(action).toHaveBeenCalledTimes(1);
  await h.emit("transitionEnd");
  await act(() => result.current.run(action));
  expect(action).toHaveBeenCalledTimes(2);
});

test("포커스가 없는 이전 화면과 늦은 완료 이벤트는 전환하지 못한다", async () => {
  const h = navigationHarness();
  const { result } = await renderHook(() => useNavigationTransitionGuard(h.navigation));
  const action = jest.fn();
  h.isFocused.mockReturnValue(false);
  await h.emit("transitionEnd");
  await act(() => result.current.run(action));
  expect(action).not.toHaveBeenCalled();
  expect(result.current.disabled).toBe(true);
});

test("열리는 중 기기 뒤로가기도 소비하고 완료 후에는 한 번만 돌아간다", async () => {
  const listener = jest.spyOn(BackHandler, "addEventListener");
  const h = navigationHarness();
  const view = await renderHook(() => useScreenReturn(h.navigation));
  const back = listener.mock.calls.find(([name]) => name === "hardwareBackPress")![1];
  await act(() => { expect(back({ type: "hardwareBackPress", timeStamp: 0 })).toBe(true); });
  expect(h.goBack).not.toHaveBeenCalled();
  await h.emit("transitionEnd");
  await act(() => {
    back({ type: "hardwareBackPress", timeStamp: 1 });
    view.result.current.goBack();
  });
  expect(h.goBack).toHaveBeenCalledTimes(1);
  await view.unmount();
  expect([...h.callbacks.values()].every(callbacks => callbacks.size === 0)).toBe(true);
  listener.mockRestore();
});
