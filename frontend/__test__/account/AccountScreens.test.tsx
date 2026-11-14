import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { Alert, BackHandler } from "react-native";
import { useAuth } from "../../src/app/providers/AuthProvider";
import { AccountHeader } from "../../src/features/account/components/AccountHeader";
import { ProfileEditorModal } from "../../src/features/account/components/ProfileEditorModal";
import { MyInfoScreen } from "../../src/features/account/screens/MyInfoScreen";
import { MyCommentsScreen, MyPostsScreen, AppSettingsScreen } from "../../src/features/account/screens/AccountPlaceholderScreens";
import { useMyProfile } from "../../src/features/account/hooks/useMyProfile";
import * as api from "../../src/features/account/api/accountApi";
import * as ImagePicker from "expo-image-picker";
import { advanceAuthEpoch, allowAuthenticatedRequests } from "../../src/shared/handler/authRequestGate";
import type { Profile } from "../../src/features/account/types/account";

const mockNavigation = {
  navigate: jest.fn(), goBack: jest.fn(), popTo: jest.fn(),
  isFocused: jest.fn(), addListener: jest.fn(),
};
jest.mock("@react-navigation/native", () => ({
  useNavigation: () => mockNavigation,
  useFocusEffect: (callback: () => (() => void)) => require("react").useEffect(callback, [callback]),
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("../../src/app/providers/AuthProvider", () => ({ useAuth: jest.fn() }));
jest.mock("../../src/features/account/hooks/useMyProfile", () => ({
  useMyProfile: jest.fn(),
  profileKey: (id: number, epoch: number) => ["my-profile", epoch, id],
}));
jest.mock("../../src/features/account/components/ProtectedAvatar", () => ({
  ProtectedAvatar: () => require("react").createElement(require("react-native").View, { testID: "avatar" }),
}));
jest.mock("../../src/features/account/api/accountApi", () => ({
  getProfile: jest.fn(), checkNickname: jest.fn(), saveNickname: jest.fn(),
  savePhoto: jest.fn(), resetPhoto: jest.fn(),
}));
jest.mock("expo-image-picker", () => ({ launchImageLibraryAsync: jest.fn() }));
jest.mock("../../src/app/config/apiConfig", () => ({ API_BASE_URL: "http://127.0.0.1:8000/api" }));

const profile: Profile = { user_id: 1, nickname: "테스트회원", profile_image_url: null };
const logout = jest.fn(async () => undefined);
let client: QueryClient;
let alert: jest.SpyInstance;
beforeEach(() => {
  jest.resetAllMocks();
  mockNavigation.isFocused.mockReturnValue(true);
  mockNavigation.addListener.mockReturnValue(() => undefined);
  logout.mockResolvedValue(undefined);
  advanceAuthEpoch(); allowAuthenticatedRequests();
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } } });
  alert = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
  jest.mocked(useAuth).mockReturnValue({
    authState: { status: "AUTHENTICATED", session: {
      user: { user_id: 1, login_id: "test", name: "공개하지않을이름", status: "ACTIVE" },
      has_selected_interests: true, next_step: "MAIN",
    } },
    logout, clearLocalSession: jest.fn(), establishSession: jest.fn(), restoreSession: jest.fn(),
    revalidateSession: jest.fn(), completeInterestSelection: jest.fn(),
  });
  jest.mocked(useMyProfile).mockReturnValue({ data: profile, isPending: false, isError: false } as ReturnType<typeof useMyProfile>);
  jest.mocked(api.checkNickname).mockImplementation(async nickname => ({ nickname, is_available: true, reason: null }));
  jest.mocked(api.getProfile).mockResolvedValue(profile);
  jest.mocked(api.saveNickname).mockImplementation(async nickname => ({ ...profile, nickname }));
  jest.mocked(api.savePhoto).mockResolvedValue({ ...profile, profile_image_url: "/api/users/1/profile-image/new.png" });
  jest.mocked(api.resetPhoto).mockResolvedValue(profile);
});
afterEach(() => { alert.mockRestore(); client.clear(); });
function wrapper({ children }: React.PropsWithChildren) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
async function checkNickname(view: Awaited<ReturnType<typeof render>>) {
  await fireEvent.changeText(view.getByLabelText("새 닉네임"), "새닉네임");
  await fireEvent.press(view.getByRole("button", { name: "중복 확인" }));
  await waitFor(() => expect(view.getByText("사용 가능한 닉네임입니다.")).toBeTruthy());
}
test("사이드바는 이름 대신 닉네임과 두 메뉴를 표시하고 내 정보·설정으로 이동한다", async () => {
  const view = await render(<AccountHeader />);
  await fireEvent.press(view.getByRole("button", { name: "사이드바 열기" }));
  expect(view.getByText(profile.nickname)).toBeTruthy();
  expect(view.queryByText("공개하지않을이름")).toBeNull();
  expect(view.queryByText("알림")).toBeNull();
  await fireEvent.press(view.getByRole("button", { name: "내 정보" }));
  expect(mockNavigation.navigate).toHaveBeenCalledWith("MyInfo");
  await fireEvent.press(view.getByRole("button", { name: "앱 설정" }));
  expect(mockNavigation.navigate).toHaveBeenCalledWith("AppSettings");
});
test("사이드바 로그아웃은 최종 확인 후 실행한다", async () => {
  const view = await render(<AccountHeader />);
  await fireEvent.press(view.getByRole("button", { name: "사이드바 열기" }));
  await fireEvent.press(view.getByRole("button", { name: "로그아웃" }));
  expect(logout).not.toHaveBeenCalled();
  expect(alert.mock.calls[0][0]).toBe("로그아웃할까요?");
  await act(async () => alert.mock.calls[0][2][1].onPress());
  expect(logout).toHaveBeenCalledTimes(1);
});
test("내 정보의 메뉴와 기기 뒤로가기를 연결한다", async () => {
  const listener = jest.spyOn(BackHandler, "addEventListener");
  const view = await render(<MyInfoScreen navigation={mockNavigation as never} route={{} as never} />, { wrapper });
  const emit = async (event: string, data = { closing: false }) => {
    const callback = mockNavigation.addListener.mock.calls.find(([name]) => name === event)![1];
    await act(() => callback({ data }));
  };
  await emit("transitionEnd");
  for (const [label, route] of [
    ["내 글 목록", "MyPosts"], ["내 댓글 목록", "MyComments"],
    ["비밀번호 변경", "PasswordChange"], ["관심사 재설정", "InterestEdit"],
  ]) {
    await fireEvent.press(view.getByRole("button", { name: label }));
    expect(mockNavigation.navigate).toHaveBeenCalledWith(route);
    await emit("focus");
    await emit("transitionEnd");
  }
  const callback = listener.mock.calls.find(([name]) => name === "hardwareBackPress")![1];
  expect(callback({ type: "hardwareBackPress", timeStamp: 0 })).toBe(true);
  expect(mockNavigation.popTo).toHaveBeenCalledWith("Main");
  listener.mockRestore();
});
test.each([MyPostsScreen, MyCommentsScreen])("목록은 조회 0건으로 오인되지 않게 준비 상태를 표시한다", async Component => {
  const view = await render(<Component navigation={mockNavigation as never} route={{} as never} />);
  expect(view.getByText("목록 기능을 준비 중입니다")).toBeTruthy();
  expect(view.queryByText("내역이 없습니다")).toBeNull();
  expect(view.getByRole("button", { name: "돌아가기" })).toBeDisabled();
  const transitionEnd = mockNavigation.addListener.mock.calls.find(([event]) => event === "transitionEnd")![1];
  await act(() => transitionEnd({ data: { closing: false } }));
  await fireEvent.press(view.getByRole("button", { name: "돌아가기" }));
  expect(mockNavigation.goBack).toHaveBeenCalledTimes(1);
});
test("앱 설정 내용은 준비 화면이다", async () => {
  const view = await render(<AppSettingsScreen navigation={mockNavigation as never} route={{} as never} />);
  expect(view.getByText("설정 기능을 준비 중입니다")).toBeTruthy();
});
test("닉네임 처리 중에는 닫기·중복 저장을 막고 따로 저장한다", async () => {
  const onClose = jest.fn();
  let resolve!: (value: Profile) => void;
  jest.mocked(api.saveNickname).mockReturnValueOnce(new Promise(yes => { resolve = yes; }));
  const view = await render(<ProfileEditorModal type="NICKNAME" profile={profile} onClose={onClose} />, { wrapper });
  await checkNickname(view);
  await fireEvent.press(view.getByRole("button", { name: "저장" }));
  await waitFor(() => expect(api.saveNickname).toHaveBeenCalledTimes(1));
  await fireEvent.press(view.getByRole("button", { name: "취소" }));
  await fireEvent.press(view.getByRole("button", { name: "처리 중…" }));
  expect(onClose).not.toHaveBeenCalled();
  await fireEvent(view.getByText("닉네임 변경"), "requestClose");
  expect(alert).not.toHaveBeenCalled();
  expect(api.saveNickname).toHaveBeenCalledTimes(1);
  await act(async () => resolve({ ...profile, nickname: "새닉네임" }));
  await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  expect(api.savePhoto).not.toHaveBeenCalled();
});
test("다른 입력에는 이전 닉네임 중복 확인을 사용하지 않는다", async () => {
  const view = await render(<ProfileEditorModal type="NICKNAME" profile={profile} onClose={jest.fn()} />, { wrapper });
  await checkNickname(view);
  await fireEvent.changeText(view.getByLabelText("새 닉네임"), "다른닉네임");
  await fireEvent.press(view.getByRole("button", { name: "저장" }));
  expect(api.saveNickname).not.toHaveBeenCalled();
});
test("미저장 창 닫기는 폐기 확인을 거친다", async () => {
  const onClose = jest.fn();
  const view = await render(<ProfileEditorModal type="NICKNAME" profile={profile} onClose={onClose} />, { wrapper });
  await fireEvent.changeText(view.getByLabelText("새 닉네임"), "새닉네임");
  await fireEvent.press(view.getByRole("button", { name: "취소" }));
  expect(onClose).not.toHaveBeenCalled();
  expect(alert.mock.calls[0][0]).toBe("변경 내용을 버릴까요?");
  await act(() => alert.mock.calls[0][2][1].onPress());
  expect(onClose).toHaveBeenCalledTimes(1);
});
test("결과 불명확 시 입력을 보존하고 자동 재저장 없이 1회 조회한다", async () => {
  const onClose = jest.fn();
  jest.mocked(api.saveNickname).mockRejectedValueOnce(new Error("response lost"));
  const view = await render(<ProfileEditorModal type="NICKNAME" profile={profile} onClose={onClose} />, { wrapper });
  await checkNickname(view);
  await fireEvent.press(view.getByRole("button", { name: "저장" }));
  await waitFor(() => expect(api.getProfile).toHaveBeenCalledTimes(1));
  expect(api.saveNickname).toHaveBeenCalledTimes(1);
  expect(onClose).not.toHaveBeenCalled();
  expect(view.getByLabelText("새 닉네임").props.value).toBe("새닉네임");
  expect(view.getByText("저장 결과를 확인하지 못했습니다. 현재 서버 정보를 확인해 주세요.")).toBeTruthy();
});
test("갤러리 선택은 별도 저장 버튼 전까지 서버에 반영하지 않는다", async () => {
  jest.mocked(ImagePicker.launchImageLibraryAsync).mockResolvedValueOnce({
    canceled: false, assets: [{ uri: "file:///picked.png", fileName: "picked.png", mimeType: "image/png", fileSize: 100, width: 20, height: 20 }],
  });
  const view = await render(<ProfileEditorModal type="PHOTO" profile={profile} onClose={jest.fn()} />, { wrapper });
  await fireEvent.press(view.getByRole("button", { name: "갤러리에서 사진 선택" }));
  expect(api.savePhoto).not.toHaveBeenCalled();
  await fireEvent.press(view.getByRole("button", { name: "저장" }));
  await waitFor(() => expect(api.savePhoto).toHaveBeenCalledTimes(1));
  expect(api.saveNickname).not.toHaveBeenCalled();
});
