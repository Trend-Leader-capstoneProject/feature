import {
  fireEvent,
  render,
  screen,
} from "@testing-library/react-native";

import {
  TrendListFeedback,
} from "../../src/features/trend/components/TrendListFeedback";


describe("TrendListFeedback", () => {
  test(
    "초기 로딩 메시지를 표시한다",
    async () => {
      await render(
        <TrendListFeedback
          state="loading"
        />,
      );

      expect(
        screen.getByText(
          "최신 트렌드를 불러오고 있습니다.",
        ),
      ).toBeTruthy();
    },
  );

  test(
    "전체 필터의 빈 목록 메시지를 표시한다",
    async () => {
      await render(
        <TrendListFeedback
          filtered={false}
          state="empty"
        />,
      );

      expect(
        screen.getByText(
          "표시할 트렌드가 없습니다.",
        ),
      ).toBeTruthy();
    },
  );

  test(
    "Category 필터의 빈 목록은 필터 전용 메시지를 표시한다",
    async () => {
      await render(
        <TrendListFeedback
          filtered
          state="empty"
        />,
      );

      expect(
        screen.getByText(
          "이 분야에 표시할 트렌드가 없습니다.",
        ),
      ).toBeTruthy();
    },
  );

  test(
    "초기 오류에서 다시 시도를 전달한다",
    async () => {
      const onRetry = jest.fn();

      await render(
        <TrendListFeedback
          onRetry={onRetry}
          retrying={false}
          state="error"
        />,
      );

      expect(
        screen.getByText(
          "최신 트렌드를 불러오지 못했습니다.",
        ),
      ).toBeTruthy();

      await fireEvent.press(
        screen.getByRole(
          "button",
          {
            name: "다시 시도",
          },
        ),
      );

      expect(
        onRetry,
      ).toHaveBeenCalledTimes(1);
    },
  );
});
