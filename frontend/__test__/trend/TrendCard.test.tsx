import {
    render,
    screen,
} from "@testing-library/react-native";

import {
    TrendCard,
} from "../../src/features/trend/components/TrendCard";
import type {
    TrendListItem,
} from "../../src/features/trend/types/trend";


function createTrend(
  overrides: Partial<TrendListItem> = {},
): TrendListItem {
  return {
    trend_id: 999,
    title: "AI 스마트폰 신제품 공개",
    summary:
      "새로운 온디바이스 AI 기능이 공개되었습니다.",
    thumbnail_url: null,
    last_collected_at:
      "2026-10-01T09:00:00Z",
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
  test(
    "화면 순번과 제목, 요약, Category 문맥을 표시한다",
    async () => {
      await render(
        <TrendCard
          displayNumber={3}
          trend={createTrend()}
        />,
      );

      expect(
        screen.getByText("#3"),
      ).toBeTruthy();

      expect(
        screen.getByText(
          "AI 스마트폰 신제품 공개",
        ),
      ).toBeTruthy();

      expect(
        screen.getByText(
          "새로운 온디바이스 AI 기능이 공개되었습니다.",
        ),
      ).toBeTruthy();

      expect(
        screen.getByText(
          "게임 · PC 게임",
        ),
      ).toBeTruthy();

      expect(
        screen.getByText(
          "IT/디지털 · 인공지능",
        ),
      ).toBeTruthy();

      expect(
        screen.getByText(
          /^최근 업데이트 /,
        ),
      ).toBeTruthy();
    },
  );

  test(
    "화면 순번은 trend_id가 아니라 displayNumber를 사용한다",
    async () => {
      await render(
        <TrendCard
          displayNumber={7}
          trend={createTrend({
            trend_id: 999,
          })}
        />,
      );

      expect(
        screen.getByText("#7"),
      ).toBeTruthy();

      expect(
        screen.queryByText("#999"),
      ).toBeNull();
    },
  );

  test(
    "nullable Summary와 빈 Category를 Placeholder 없이 처리한다",
    async () => {
      await render(
        <TrendCard
          displayNumber={1}
          trend={createTrend({
            summary: null,
            categories: [],
          })}
        />,
      );

      expect(
        screen.queryByText(
          "새로운 온디바이스 AI 기능이 공개되었습니다.",
        ),
      ).toBeNull();

      expect(
        screen.queryByText(
          "게임 · PC 게임",
        ),
      ).toBeNull();

      expect(
        screen.queryByText(
          "IT/디지털 · 인공지능",
        ),
      ).toBeNull();

      expect(
        screen.getByText(
          "AI 스마트폰 신제품 공개",
        ),
      ).toBeTruthy();
    },
  );

  test(
    "Card Category는 선택 버튼이 아닌 표시 전용 정보다",
    async () => {
      await render(
        <TrendCard
          displayNumber={1}
          trend={createTrend()}
        />,
      );

      expect(
        screen.queryByRole(
          "button",
          {
            name: "게임 · PC 게임",
          },
        ),
      ).toBeNull();

      expect(
        screen.queryByRole(
          "button",
          {
            name: "IT/디지털 · 인공지능",
          },
        ),
      ).toBeNull();
    },
  );
});
