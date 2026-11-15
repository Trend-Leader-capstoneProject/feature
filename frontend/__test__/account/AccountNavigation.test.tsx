import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { createNavigationContainerRef, NavigationContainer } from "@react-navigation/native";
import { AppNavigator, type AppStackParamList } from "../../src/app/navigation/AppNavigator";

jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  ...require("react-native-safe-area-context/jest/mock").default,
}));
jest.mock("../../src/app/screens/PersonalizedMainScreen", () => ({
  PersonalizedMainScreen: () => require("react").createElement(require("react-native").Text, null, "홈 화면"),
}));
jest.mock("../../src/features/interest/screens/InterestEditScreen", () => ({ InterestEditScreen: () => null }));
jest.mock("../../src/features/trend/screens/LatestTrendScreen", () => ({ LatestTrendScreen: () => null }));
jest.mock("../../src/features/account/screens/PasswordChangeScreen", () => ({ PasswordChangeScreen: () => null }));
jest.mock("../../src/features/account/components/ProfileEditorModal", () => ({ ProfileEditorModal: () => null }));
jest.mock("../../src/features/account/components/WithdrawalModal", () => ({ WithdrawalModal: () => null }));
jest.mock("../../src/features/account/components/ProtectedAvatar", () => ({
  ProtectedAvatar: () => require("react").createElement(require("react-native").View),
}));
jest.mock("../../src/features/account/hooks/useMyProfile", () => ({
  useMyProfile: () => ({
    data: { user_id: 1, nickname: "돌아갈프로필", profile_image_url: null },
    isPending: false, isError: false,
  }),
}));
jest.mock("../../src/app/providers/AuthProvider", () => ({
  useAuth: () => ({ logout: jest.fn() }),
}));

test.each(["내 글 목록", "내 댓글 목록"])("%s 왕복을 반복해도 실제 Stack은 내 정보로 복귀한다", async label => {
  const navigation = createNavigationContainerRef<AppStackParamList>();
  const view = await render(<NavigationContainer ref={navigation}><AppNavigator /></NavigationContainer>);
  await waitFor(() => expect(navigation.isReady()).toBe(true));
  await act(() => navigation.navigate("MyInfo"));
  await fireEvent(view.getByText("돌아갈프로필"), "appear", { nativeEvent: {} });
  for (let i = 0; i < 5; i += 1) {
    await fireEvent.press(view.getByRole("button", { name: label }));
    expect(navigation.getCurrentRoute()?.name).toBe(label === "내 글 목록" ? "MyPosts" : "MyComments");
    expect(view.getByText("목록 기능을 준비 중입니다")).toBeTruthy();
    expect(view.getByRole("button", { name: "돌아가기" })).toBeDisabled();
    await fireEvent.press(view.getByRole("button", { name: "돌아가기" }));
    expect(navigation.getCurrentRoute()?.name).toBe(label === "내 글 목록" ? "MyPosts" : "MyComments");
    await fireEvent(view.getByText("목록 기능을 준비 중입니다"), "appear", { nativeEvent: {} });
    await fireEvent.press(view.getByRole("button", { name: "돌아가기" }));
    await waitFor(() => expect(navigation.getCurrentRoute()?.name).toBe("MyInfo"));
    expect(view.getByText("돌아갈프로필")).toBeTruthy();
    expect(navigation.getRootState().routes.map(route => route.name)).toEqual(["Main", "MyInfo"]);
    expect(view.getByRole("button", { name: label })).toBeDisabled();
    await fireEvent.press(view.getByRole("button", { name: label }));
    expect(navigation.getCurrentRoute()?.name).toBe("MyInfo");
    await fireEvent(view.getByText("돌아갈프로필"), "appear", { nativeEvent: {} });
  }
});
