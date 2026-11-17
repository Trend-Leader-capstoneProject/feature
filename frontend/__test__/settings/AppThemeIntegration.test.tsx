import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import * as SecureStore from "expo-secure-store";
import AppEntry from "../../App";
const mockRootMount = jest.fn();
jest.mock("expo-secure-store", () => ({ getItemAsync: jest.fn(), setItemAsync: jest.fn() }));
jest.mock("expo-system-ui", () => ({ setBackgroundColorAsync: jest.fn(async () => undefined) }));
jest.mock("expo-status-bar", () => ({
  StatusBar: ({ style }: { style: string }) => require("react").createElement(require("react-native").Text, null, "status:" + style),
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  ...require("react-native-safe-area-context/jest/mock").default,
}));
jest.mock("../../src/app/providers/AuthProvider", () => ({
  AuthProvider: ({ children }: React.PropsWithChildren) => children,
}));
jest.mock("../../src/app/providers/QueryProvider", () => ({
  QueryProvider: ({ children }: React.PropsWithChildren) => children,
}));
jest.mock("../../src/app/navigation/RootNavigator", () => ({
  RootNavigator: function MockRoot() {
    const React = require("react");
    const { Text, Pressable, View } = require("react-native");
    const theme = require("../../src/shared/theme/ThemeProvider").useAppTheme();
    React.useEffect(() => { mockRootMount(); }, []);
    return <View><Text>현재 화면</Text><Pressable accessibilityRole="button" accessibilityLabel="설정 재조회" onPress={theme.retryRestore}><Text>재조회</Text></Pressable></View>;
  },
}));
test("시작 시 테마를 복구하고 이후 설정 재조회 중에는 현재 네비게이션을 유지한다", async () => {
  let resolve!: (value: string) => void;
  jest.mocked(SecureStore.getItemAsync).mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  const view = await render(<AppEntry />);
  expect(view.queryByText("현재 화면")).toBeNull();
  await act(async () => resolve("DARK"));
  await waitFor(() => expect(view.getByText("현재 화면")).toBeTruthy());
  expect(view.getByText("status:light")).toBeTruthy();
  expect(mockRootMount).toHaveBeenCalledTimes(1);
  jest.mocked(SecureStore.getItemAsync).mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  await fireEvent.press(view.getByRole("button", { name: "설정 재조회" }));
  expect(view.getByText("현재 화면")).toBeTruthy();
  expect(mockRootMount).toHaveBeenCalledTimes(1);
  await act(async () => resolve("LIGHT"));
  expect(view.getByText("status:dark")).toBeTruthy();
  expect(mockRootMount).toHaveBeenCalledTimes(1);
});
