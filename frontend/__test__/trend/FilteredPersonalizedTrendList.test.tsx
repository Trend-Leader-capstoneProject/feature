import { render, screen } from "@testing-library/react-native";

import { FilteredPersonalizedTrendList } from "../../src/features/trend/components/FilteredPersonalizedTrendList";
import { useTrends } from "../../src/features/trend/hooks/useTrends";

jest.mock("../../src/features/trend/hooks/useTrends", () => ({
  useTrends: jest.fn(),
}));

test("세부분류 선택은 기존 카테고리별 목록 조회를 사용한다", () => {
  jest.mocked(useTrends).mockReturnValue({
    data: {
      pages: [
        {
          items: [
            {
              trend_id: 4,
              title: "선택한 PC 게임 트렌드",
              summary: null,
              thumbnail_url: null,
              last_collected_at: "2026-10-01T09:00:00Z",
              categories: [],
              latest_source: null,
            },
          ],
          next_cursor: null,
          has_next: false,
        },
      ],
      pageParams: [undefined],
    },
    isPending: false,
    isError: false,
    isFetching: false,
    isFetchingNextPage: false,
    isFetchNextPageError: false,
    hasNextPage: false,
  } as ReturnType<typeof useTrends>);

  render(<FilteredPersonalizedTrendList categoryId={11} />);

  expect(useTrends).toHaveBeenCalledWith({ categoryId: 11 });
  expect(screen.getByText("선택한 PC 게임 트렌드")).toBeTruthy();
});
