import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { Appearance, Pressable, Text } from "react-native";
import * as SecureStore from "expo-secure-store";
import { ThemeProvider, THEME_STORAGE_KEY, useAppTheme } from "../../src/shared/theme/ThemeProvider";
import { ScreenContainer, PrimaryButton } from "../../src/shared/components";
import { colors, darkColors } from "../../src/shared/constants/colors";

let mockDeviceScheme = "light";
jest.mock("react-native/Libraries/Utilities/useColorScheme", () => ({
  __esModule: true, default: () => mockDeviceScheme,
}));
jest.mock("expo-secure-store", () => ({ getItemAsync: jest.fn(), setItemAsync: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  ...require("react-native-safe-area-context/jest/mock").default,
}));
function Probe() {
  const theme = useAppTheme();
  return <ScreenContainer>
    <Text testID="state">{theme.preference + ":" + theme.scheme + ":" + theme.ready}</Text>
    <Text>{theme.error}</Text>
    <PrimaryButton label="공통 버튼" />
    <Pressable accessibilityRole="button" accessibilityLabel="dark" disabled={theme.saving} onPress={() => void theme.setPreference("DARK")}><Text>dark</Text></Pressable>
    <Pressable accessibilityRole="button" accessibilityLabel="light" disabled={theme.saving} onPress={() => void theme.setPreference("LIGHT")}><Text>light</Text></Pressable>
    <Pressable accessibilityRole="button" accessibilityLabel="system" onPress={() => void theme.setPreference("SYSTEM")}><Text>system</Text></Pressable>
    <Pressable accessibilityRole="button" accessibilityLabel="retry" onPress={theme.retryRestore}><Text>retry</Text></Pressable>
  </ScreenContainer>;
}
beforeEach(() => {
  jest.clearAllMocks(); mockDeviceScheme = "light";
  jest.spyOn(Appearance, "setColorScheme").mockImplementation(() => undefined);
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue(null);
  jest.mocked(SecureStore.setItemAsync).mockResolvedValue(undefined);
});
afterEach(() => jest.restoreAllMocks());
async function mount() {
  const view = await render(<ThemeProvider><Probe /></ThemeProvider>);
  await waitFor(() => expect(view.getByTestId("state")).toHaveTextContent(/true/));
  return view;
}
test("기본값은 기기 테마이며 시스템 변경을 따라간다", async () => {
  const view = await mount();
  expect(view.getByTestId("state")).toHaveTextContent("SYSTEM:light:true");
  mockDeviceScheme = "dark";
  await view.rerender(<ThemeProvider><Probe /></ThemeProvider>);
  expect(view.getByTestId("state")).toHaveTextContent("SYSTEM:dark:true");
  expect(view.getByText("공통 버튼")).toHaveStyle({ color: darkColors.actionPrimaryText });
});
test("선택을 저장하고 재실행하면 같은 테마를 복구한다", async () => {
  const view = await mount();
  await fireEvent.press(view.getByRole("button", { name: "dark" }));
  await waitFor(() => expect(view.getByTestId("state")).toHaveTextContent("DARK:dark:true"));
  expect(SecureStore.setItemAsync).toHaveBeenCalledWith(THEME_STORAGE_KEY, "DARK");
  expect(Appearance.setColorScheme).toHaveBeenLastCalledWith("dark");
  expect(view.getByRole("button", { name: "공통 버튼" })).toHaveStyle({ backgroundColor: darkColors.actionPrimary });
  await view.unmount();
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue("DARK");
  const reopened = await mount();
  expect(reopened.getByTestId("state")).toHaveTextContent("DARK:dark:true");
  expect(SecureStore.getItemAsync).toHaveBeenLastCalledWith(THEME_STORAGE_KEY);
});
test("명시적인 라이트 선택은 시스템 다크보다 우선한다", async () => {
  mockDeviceScheme = "dark";
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue("LIGHT");
  const view = await mount();
  expect(view.getByTestId("state")).toHaveTextContent("LIGHT:light:true");
  expect(view.getByRole("button", { name: "공통 버튼" })).toHaveStyle({ backgroundColor: colors.actionPrimary });
  await fireEvent.press(view.getByRole("button", { name: "system" }));
  await waitFor(() => expect(view.getByTestId("state")).toHaveTextContent("SYSTEM:dark:true"));
  expect(Appearance.setColorScheme).toHaveBeenLastCalledWith("unspecified");
});
test("저장 실패는 이전 테마를 유지하고 재선택으로 복구한다", async () => {
  const view = await mount();
  jest.mocked(SecureStore.setItemAsync).mockRejectedValueOnce(new Error("storage"));
  await fireEvent.press(view.getByRole("button", { name: "dark" }));
  await waitFor(() => expect(view.getByText("테마 설정을 저장하지 못했습니다. 다시 선택해 주세요.")).toBeTruthy());
  expect(view.getByTestId("state")).toHaveTextContent("SYSTEM:light:true");
  await fireEvent.press(view.getByRole("button", { name: "dark" }));
  await waitFor(() => expect(view.getByTestId("state")).toHaveTextContent("DARK:dark:true"));
});
test("읽기 실패는 앱 접근을 막지 않고 다시 불러올 수 있다", async () => {
  jest.mocked(SecureStore.getItemAsync).mockRejectedValueOnce(new Error("read"));
  const view = await mount();
  expect(view.getByText("테마 설정을 불러오지 못했습니다. 다시 시도해 주세요.")).toBeTruthy();
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue("DARK");
  await fireEvent.press(view.getByRole("button", { name: "retry" }));
  await waitFor(() => expect(view.getByTestId("state")).toHaveTextContent("DARK:dark:true"));
});
test("오래된 복구 응답이 새로 저장한 선택을 덮어쓰지 않는다", async () => {
  let resolve!: (value: string | null) => void;
  jest.mocked(SecureStore.getItemAsync).mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  const view = await render(<ThemeProvider><Probe /></ThemeProvider>);
  await fireEvent.press(view.getByRole("button", { name: "dark" }));
  await waitFor(() => expect(SecureStore.setItemAsync).toHaveBeenCalled());
  await act(async () => resolve("LIGHT"));
  expect(view.getByTestId("state")).toHaveTextContent("DARK:dark:true");
});
test("저장 중 중복 요청은 보내지 않고 다른 저장소 키를 건드리지 않는다", async () => {
  let resolve!: () => void;
  const view = await mount();
  jest.mocked(SecureStore.setItemAsync).mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  await fireEvent.press(view.getByRole("button", { name: "dark" }));
  await fireEvent.press(view.getByRole("button", { name: "light" }));
  expect(SecureStore.setItemAsync).toHaveBeenCalledTimes(1);
  await act(async () => resolve());
  expect(view.getByTestId("state")).toHaveTextContent("DARK:dark:true");
});
test("알 수 없는 저장 값은 기기 설정으로 안전하게 복구한다", async () => {
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue("UNKNOWN");
  const view = await mount();
  expect(view.getByTestId("state")).toHaveTextContent("SYSTEM:light:true");
});
