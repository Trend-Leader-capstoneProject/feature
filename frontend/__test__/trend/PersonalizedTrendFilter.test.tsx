import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { useState } from "react";

import { PersonalizedTrendFilter } from "../../src/features/trend/components/PersonalizedTrendFilter";
import type { TrendCategorySelection } from "../../src/features/trend/components/TrendCategoryFilter";
import { useCategories } from "../../src/features/interest/hooks/useCategories";
import { useUserInterests } from "../../src/features/interest/hooks/useUserInterests";
import type { CategoryItem } from "../../src/features/interest/types/category";

jest.mock("../../src/features/interest/hooks/useCategories", () => ({
  useCategories: jest.fn(),
}));
jest.mock("../../src/features/interest/hooks/useUserInterests", () => ({
  useUserInterests: jest.fn(),
}));

const game: CategoryItem = {
  category_id: 1,
  category_code: "GAME",
  category_name: "게임",
  parent_id: null,
  sort_order: 1,
  children: [
    {
      category_id: 11,
      category_code: null,
      category_name: "PC 게임",
      parent_id: 1,
      sort_order: 1,
      children: [],
    },
  ],
};

const food: CategoryItem = {
  category_id: 2,
  category_code: "FOOD",
  category_name: "음식",
  parent_id: null,
  sort_order: 2,
  children: [],
};

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(useCategories).mockReturnValue({
    data: { categories: [game, food] },
    isPending: false,
    isError: false,
  } as ReturnType<typeof useCategories>);
  jest.mocked(useUserInterests).mockReturnValue({
    data: { selected_category_ids: [1], selected_count: 1 },
    isPending: false,
    isError: false,
  } as ReturnType<typeof useUserInterests>);
});

test("선택한 관심 대분류만 표시하고 해당 세부분류를 선택할 수 있다", async () => {
  const changes: TrendCategorySelection[] = [];

  function Harness() {
    const [selection, setSelection] = useState<TrendCategorySelection>({
      rootCategoryId: null,
      categoryId: null,
    });

    return (
      <PersonalizedTrendFilter
        selectedCategoryId={selection.categoryId}
        selectedRootCategoryId={selection.rootCategoryId}
        onSelectionChange={(next) => {
          changes.push(next);
          setSelection(next);
        }}
      />
    );
  }

  await render(<Harness />);

  expect(screen.getByRole("button", { name: "전체" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "게임" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "음식" })).toBeNull();

  fireEvent.press(screen.getByRole("button", { name: "게임" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "PC 게임" })).toBeTruthy(),
  );

  fireEvent.press(screen.getByRole("button", { name: "PC 게임" }));
  expect(changes.at(-1)).toEqual({ rootCategoryId: 1, categoryId: 11 });

  fireEvent.press(screen.getByRole("button", { name: "전체" }));
  expect(changes.at(-1)).toEqual({ rootCategoryId: null, categoryId: null });
});

test("저장된 관심사에서 제외된 대분류 선택은 전체로 복구한다", async () => {
  const onSelectionChange = jest.fn();
  await render(
    <PersonalizedTrendFilter
      selectedRootCategoryId={2}
      selectedCategoryId={2}
      onSelectionChange={onSelectionChange}
    />,
  );

  await waitFor(() =>
    expect(onSelectionChange).toHaveBeenCalledWith({
      rootCategoryId: null,
      categoryId: null,
    }),
  );
});
