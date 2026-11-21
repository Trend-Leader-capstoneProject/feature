import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { fetchIgdbDevPreview } from "../../src/features/trend/dev/igdbDevPreview";
import { IgdbDevPreviewScreen } from "../../src/features/trend/screens/IgdbDevPreviewScreen";
import { openTrendSourceUrl } from "../../src/features/trend/utils/openTrendSourceUrl";

jest.mock("../../src/features/trend/dev/igdbDevPreview", () => ({
  fetchIgdbDevPreview: jest.fn(),
}));
jest.mock("../../src/features/trend/utils/openTrendSourceUrl", () => ({
  openTrendSourceUrl: jest.fn(),
}));

const mockedFetch = jest.mocked(fetchIgdbDevPreview);
const mockedOpenSource = jest.mocked(openTrendSourceUrl);

const READY: Awaited<ReturnType<typeof fetchIgdbDevPreview>> = {
  kind: "ready",
  trend: {
    title: "Free Fire",
    summary: "IGDB Visits 관측 5위",
    thumbnail_url: null,
    last_collected_at: "2026-11-21T00:25:00+00:00",
    categories: [{
      category_name: "모바일 게임",
      parent: { category_name: "게임" },
    }],
    latest_source: {
      platform: "ETC",
      source_title: "IGDB Visits",
      source_url: "https://www.igdb.com/games/free-fire",
    },
  },
};

describe("IgdbDevPreviewScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedOpenSource.mockResolvedValue(undefined);
  });

  test("실제 TrendCard를 재사용하고 원문 버튼으로 공식 URL을 전달한다", async () => {
    mockedFetch.mockResolvedValue(READY);
    await render(<IgdbDevPreviewScreen />);

    await waitFor(() => {
      expect(screen.getByText("Free Fire")).toBeTruthy();
    });
    expect(screen.getByText("게임 · 모바일 게임")).toBeTruthy();
    expect(screen.getByText("IGDB Visits 관측 5위")).toBeTruthy();
    expect(screen.getByText("IGDB Visits")).toBeTruthy();
    expect(screen.getByText(/개발 전용 · 독립 검증 결과/)).toBeTruthy();

    await fireEvent.press(screen.getByRole("button", { name: "원문 보기" }));
    expect(mockedOpenSource).toHaveBeenCalledWith(
      "https://www.igdb.com/games/free-fire",
    );
  });

  test("후보 없음은 오류나 게시 성공으로 표시하지 않는다", async () => {
    mockedFetch.mockResolvedValue({ kind: "empty" });
    await render(<IgdbDevPreviewScreen />);

    await waitFor(() => {
      expect(screen.getByText("현재 적격 게임 후보가 없습니다.")).toBeTruthy();
    });
    expect(screen.queryByRole("button", { name: "원문 보기" })).toBeNull();
  });

  test("API 오류 후 다시 조회하면 정상 카드를 표시한다", async () => {
    mockedFetch.mockRejectedValueOnce(new Error("NO_CONNECTION"))
      .mockResolvedValueOnce(READY);
    await render(<IgdbDevPreviewScreen />);

    await waitFor(() => {
      expect(screen.getByText(
        "로컬 IGDB 검증 서버에 연결하지 못했습니다.",
      )).toBeTruthy();
    });
    await fireEvent.press(screen.getByRole("button", { name: "IGDB 다시 조회" }));
    await waitFor(() => {
      expect(screen.getByText("Free Fire")).toBeTruthy();
    });
    expect(mockedFetch).toHaveBeenCalledTimes(2);
  });

  test("돌아가기는 기존 내비게이션을 사용한다", async () => {
    const goBack = jest.fn();
    mockedFetch.mockResolvedValue({ kind: "empty" });
    await render(<IgdbDevPreviewScreen navigation={{ goBack }} />);

    await fireEvent.press(screen.getByRole("button", {
      name: "최신 트렌드로 돌아가기",
    }));
    expect(goBack).toHaveBeenCalledTimes(1);
  });
});
