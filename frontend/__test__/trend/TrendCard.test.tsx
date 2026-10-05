import {
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/react-native";

import { TrendCard } from "../../src/features/trend/components/TrendCard";
import type { TrendListItem } from "../../src/features/trend/types/trend";

function createTrend(overrides: Partial<TrendListItem> = {}): TrendListItem {
  return {
    trend_id: 999,
    title: "AI 스마트폰 신제품 공개",
    summary: "새로운 온디바이스 AI 기능이 공개되었습니다.",
    thumbnail_url: null,
    last_collected_at: "2026-10-01T09:00:00Z",
    categories: [
      {
        category_id: 11,
        category_name: "PC 게임",
        parent: {
          category_id: 1,
          category_code: "GAME",
          category_name: "게임",
        },
      },
      {
        category_id: 21,
        category_name: "인공지능",
        parent: {
          category_id: 2,
          category_code: "IT_DIGITAL",
          category_name: "IT/디지털",
        },
      },
    ],
    latest_source: null,
    ...overrides,
  };
}

describe("TrendCard", () => {
  test("화면 순번과 제목, 요약, Category 문맥을 표시한다", async () => {
    await render(
      <TrendCard
        displayNumber={3}
        onOpenSource={jest.fn()}
        trend={createTrend()}
      />,
    );

    expect(screen.getByText("#3")).toBeTruthy();

    expect(screen.getByText("AI 스마트폰 신제품 공개")).toBeTruthy();

    expect(
      screen.getByText("새로운 온디바이스 AI 기능이 공개되었습니다."),
    ).toBeTruthy();

    expect(screen.getByText("게임 · PC 게임")).toBeTruthy();

    expect(screen.getByText("IT/디지털 · 인공지능")).toBeTruthy();

    expect(screen.getByText(/^최근 업데이트 /)).toBeTruthy();
  });

  test("화면 순번은 trend_id가 아니라 displayNumber를 사용한다", async () => {
    await render(
      <TrendCard
        displayNumber={7}
        onOpenSource={jest.fn()}
        trend={createTrend({
          trend_id: 999,
        })}
      />,
    );

    expect(screen.getByText("#7")).toBeTruthy();

    expect(screen.queryByText("#999")).toBeNull();
  });

  test("nullable Summary와 빈 Category를 Placeholder 없이 처리한다", async () => {
    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={jest.fn()}
        trend={createTrend({
          summary: null,
          categories: [],
        })}
      />,
    );

    expect(
      screen.queryByText("새로운 온디바이스 AI 기능이 공개되었습니다."),
    ).toBeNull();

    expect(screen.queryByText("게임 · PC 게임")).toBeNull();

    expect(screen.queryByText("IT/디지털 · 인공지능")).toBeNull();

    expect(screen.getByText("AI 스마트폰 신제품 공개")).toBeTruthy();
  });

  test("Card Category는 선택 버튼이 아닌 표시 전용 정보다", async () => {
    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={jest.fn()}
        trend={createTrend()}
      />,
    );

    expect(
      screen.queryByRole("button", {
        name: "게임 · PC 게임",
      }),
    ).toBeNull();

    expect(
      screen.queryByRole("button", {
        name: "IT/디지털 · 인공지능",
      }),
    ).toBeNull();
  });

  test("Latest Source의 Platform과 제목, 원문 보기 버튼을 표시한다", async () => {
    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={jest.fn()}
        trend={createTrend({
          latest_source: {
            source_id: 501,
            platform: "YOUTUBE",
            source_title: "AI 신제품 공개 영상",
            source_url: "https://example.com/source",
          },
        })}
      />,
    );

    expect(screen.getByText("YouTube")).toBeTruthy();

    expect(screen.getByText("AI 신제품 공개 영상")).toBeTruthy();

    expect(
      screen.getByRole("button", {
        name: "원문 보기",
      }),
    ).toBeTruthy();
  });

  test("원문 보기를 누르면 Source URL을 전달한다", async () => {
    const onOpenSource = jest.fn();

    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={onOpenSource}
        trend={createTrend({
          latest_source: {
            source_id: 501,
            platform: "GOOGLE",
            source_title: "관련 기사",
            source_url: "https://example.com/article",
          },
        })}
      />,
    );

    await fireEvent.press(
      screen.getByRole("button", {
        name: "원문 보기",
      }),
    );

    expect(onOpenSource).toHaveBeenCalledWith("https://example.com/article");

    expect(onOpenSource).toHaveBeenCalledTimes(1);
  });

  test("Source 제목이 null이어도 Platform과 원문 보기는 유지한다", async () => {
    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={jest.fn()}
        trend={createTrend({
          latest_source: {
            source_id: 501,
            platform: "SNS",
            source_title: null,
            source_url: "https://example.com/post",
          },
        })}
      />,
    );

    expect(screen.getByText("SNS")).toBeTruthy();

    expect(
      screen.getByRole("button", {
        name: "원문 보기",
      }),
    ).toBeTruthy();
  });

  test("Latest Source가 없으면 안내만 표시하고 원문 버튼은 만들지 않는다", async () => {
    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={jest.fn()}
        trend={createTrend({
          latest_source: null,
        })}
      />,
    );

    expect(screen.getByText("출처 정보가 없습니다.")).toBeTruthy();

    expect(
      screen.queryByRole("button", {
        name: "원문 보기",
      }),
    ).toBeNull();
  });
  test("thumbnail_url이 있으면 Thumbnail을 표시한다", async () => {
    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={jest.fn()}
        trend={createTrend({
          thumbnail_url: "https://example.com/thumbnail.jpg",
        })}
      />,
    );

    expect(screen.getByLabelText("AI 스마트폰 신제품 공개 썸네일")).toHaveProp(
      "source",
      {
        uri: "https://example.com/thumbnail.jpg",
      },
    );
  });

  test("thumbnail_url이 null이면 Thumbnail 영역을 만들지 않는다", async () => {
    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={jest.fn()}
        trend={createTrend({
          thumbnail_url: null,
        })}
      />,
    );

    expect(
      screen.queryByLabelText("AI 스마트폰 신제품 공개 썸네일"),
    ).toBeNull();
  });

  test("Thumbnail 로딩에 실패하면 이미지 영역을 제거한다", async () => {
    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={jest.fn()}
        trend={createTrend({
          thumbnail_url: "https://example.com/broken.jpg",
        })}
      />,
    );

    const thumbnail = screen.getByLabelText("AI 스마트폰 신제품 공개 썸네일");

    fireEvent(thumbnail, "error");

    await waitFor(() => {
      expect(
        screen.queryByLabelText("AI 스마트폰 신제품 공개 썸네일"),
      ).toBeNull();
    });
  });
});
