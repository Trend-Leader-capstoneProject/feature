import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { Linking } from "react-native";
import * as SecureStore from "expo-secure-store";
import { AppSettingsScreen, AppInfoScreen, HelpSupportScreen } from "../../src/features/settings/screens/SettingsScreens";
import { APP_VERSION, CONTACT_URL, PROJECT_URL } from "../../src/features/settings/appDetails";
import { ThemeProvider } from "../../src/shared/theme/ThemeProvider";

const mockNavigation = { goBack: jest.fn(), navigate: jest.fn() };
jest.mock("../../src/features/account/hooks/useScreenReturn", () => ({
  useScreenReturn: () => ({ goBack: mockNavigation.goBack, disabled: false, run: (action: () => void) => action() }),
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  ...require("react-native-safe-area-context/jest/mock").default,
}));
jest.mock("expo-secure-store", () => ({ getItemAsync: jest.fn(), setItemAsync: jest.fn() }));
beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue(null);
  jest.mocked(SecureStore.setItemAsync).mockResolvedValue(undefined);
});
afterEach(() => jest.restoreAllMocks());

test("설정은 세 범위만 제공하고 선택 저장·각 화면 이동·뒤로가기가 동작한다", async () => {
  const view = await render(<ThemeProvider><AppSettingsScreen navigation={mockNavigation as never} route={{} as never} /></ThemeProvider>);
  await waitFor(() => expect(view.getByRole("radio", { name: "다크 모드" })).not.toBeDisabled());
  await fireEvent.press(view.getByRole("radio", { name: "다크 모드" }));
  await waitFor(() => expect(view.getByRole("radio", { name: "다크 모드" })).toBeChecked());
  expect(view.getAllByRole("radio")).toHaveLength(3);
  await fireEvent.press(view.getByRole("button", { name: "앱 정보" }));
  expect(mockNavigation.navigate).toHaveBeenCalledWith("AppInfo");
  await fireEvent.press(view.getByRole("button", { name: "도움말 / 문의" }));
  expect(mockNavigation.navigate).toHaveBeenCalledWith("HelpSupport");
  await fireEvent.press(view.getByRole("button", { name: "돌아가기" }));
  expect(mockNavigation.goBack).toHaveBeenCalledTimes(1);
  expect(view.queryByText("알림 설정")).toBeNull();
});
test("앱 정보는 프로젝트 버전과 라이선스를 보여주고 실제 프로젝트 페이지를 연다", async () => {
  const open = jest.spyOn(Linking, "openURL").mockResolvedValue(undefined);
  const view = await render(<AppInfoScreen navigation={mockNavigation as never} route={{} as never} />);
  expect(view.getByText("버전 " + APP_VERSION)).toBeTruthy();
  expect(view.getByRole("link", { name: "Lucide 아이콘 라이선스 열기" })).toBeTruthy();
  await fireEvent.press(view.getByRole("button", { name: "프로젝트 페이지 열기" }));
  expect(open).toHaveBeenCalledWith(PROJECT_URL);
});
test("FAQ는 펼치고 닫을 수 있다", async () => {
  const view = await render(<HelpSupportScreen navigation={mockNavigation as never} route={{} as never} />);
  const question = view.getByRole("button", { name: "테마 설정은 어디에 저장되나요?" });
  await fireEvent.press(question);
  expect(view.getByText(/현재 기기에 저장되며/)).toBeTruthy();
  await fireEvent.press(question);
  expect(view.queryByText(/현재 기기에 저장되며/)).toBeNull();
});
test("문의는 공개 게시판임을 알리고 기기 개인정보 없이 사용자가 작성할 화면만 연다", async () => {
  const open = jest.spyOn(Linking, "openURL").mockResolvedValue(undefined);
  const view = await render(<HelpSupportScreen navigation={mockNavigation as never} route={{} as never} />);
  expect(view.getByText(/GitHub 공개 문의 게시판/)).toBeTruthy();
  await fireEvent.press(view.getByRole("button", { name: "GitHub에서 문의 작성" }));
  expect(open).toHaveBeenCalledWith(CONTACT_URL);
  expect(CONTACT_URL).toContain("/issues/new?");
  expect(decodeURIComponent(CONTACT_URL)).not.toContain("user_id");
  expect(decodeURIComponent(CONTACT_URL)).not.toContain("access_token");
});
test("외부 링크 실행 실패를 표시하고 다시 누르면 재시도한다", async () => {
  const open = jest.spyOn(Linking, "openURL").mockRejectedValueOnce(new Error("no browser")).mockResolvedValue(undefined);
  const view = await render(<HelpSupportScreen navigation={mockNavigation as never} route={{} as never} />);
  await fireEvent.press(view.getByRole("button", { name: "GitHub에서 문의 작성" }));
  await waitFor(() => expect(view.getByRole("alert")).toHaveTextContent(/링크를 열지 못했습니다/));
  await fireEvent.press(view.getByRole("button", { name: "GitHub에서 문의 작성" }));
  expect(open).toHaveBeenCalledTimes(2);
  await waitFor(() => expect(view.queryByRole("alert")).toBeNull());
});
