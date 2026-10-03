import {
  fireEvent,
  render,
  screen,
} from "@testing-library/react-native";

import type {
  CategoryItem,
} from "../../src/features/interest/types/category";
import {
  TrendCategoryFilter,
} from "../../src/features/trend/components/TrendCategoryFilter";


const CATEGORIES: CategoryItem[] = [
  {
    category_id: 1,
    category_code: "GAME",
    category_name: "게임",
    parent_id: null,
    sort_order: 1,
    children: [
      {
        category_id: 11,
        category_code: null,
        category_name: "모바일 게임",
        parent_id: 1,
        sort_order: 1,
        children: [],
      },
      {
        category_id: 12,
        category_code: null,
        category_name: "PC 게임",
        parent_id: 1,
        sort_order: 2,
        children: [],
      },
    ],
  },
  {
    category_id: 2,
    category_code: "IT_DIGITAL",
    category_name: "IT/디지털",
    parent_id: null,
    sort_order: 2,
    children: [
      {
        category_id: 21,
        category_code: null,
        category_name: "인공지능",
        parent_id: 2,
        sort_order: 1,
        children: [],
      },
    ],
  },
];

describe("TrendCategoryFilter", () => {
  test(
    "전체 선택 상태에서는 대분류만 표시하고 세부분류 행은 숨긴다",
    async () => {
      const onSelectionChange =
        jest.fn();

      await render(
        <TrendCategoryFilter
          categories={CATEGORIES}
          selectedCategoryId={null}
          selectedRootCategoryId={null}
          onSelectionChange={
            onSelectionChange
          }
        />,
      );

      expect(
        screen.getByRole(
          "button",
          {
            name: "전체",
          },
        ),
      ).toHaveProp(
        "accessibilityState",
        expect.objectContaining({
          selected: true,
        }),
      );

      expect(
        screen.getByRole(
          "button",
          {
            name: "게임",
          },
        ),
      ).toBeTruthy();

      expect(
        screen.getByRole(
          "button",
          {
            name: "IT/디지털",
          },
        ),
      ).toBeTruthy();

      expect(
        screen.queryByRole(
          "button",
          {
            name: "게임 전체",
          },
        ),
      ).toBeNull();

      expect(
        screen.queryByRole(
          "button",
          {
            name: "모바일 게임",
          },
        ),
      ).toBeNull();
    },
  );

  test(
    "대분류가 선택되면 해당 세부분류 행을 표시하고 세부분류 선택을 전달한다",
    async () => {
      const onSelectionChange =
        jest.fn();

      await render(
        <TrendCategoryFilter
          categories={CATEGORIES}
          selectedCategoryId={1}
          selectedRootCategoryId={1}
          onSelectionChange={
            onSelectionChange
          }
        />,
      );

      expect(
        screen.getByRole(
          "button",
          {
            name: "게임 전체",
          },
        ),
      ).toHaveProp(
        "accessibilityState",
        expect.objectContaining({
          selected: true,
        }),
      );

      expect(
        screen.getByRole(
          "button",
          {
            name: "모바일 게임",
          },
        ),
      ).toBeTruthy();

      expect(
        screen.getByRole(
          "button",
          {
            name: "PC 게임",
          },
        ),
      ).toBeTruthy();

      await fireEvent.press(
        screen.getByRole(
          "button",
          {
            name: "PC 게임",
          },
        ),
      );

      expect(
        onSelectionChange,
      ).toHaveBeenCalledWith({
        rootCategoryId: 1,
        categoryId: 12,
      });
    },
  );

  test(
    "다른 대분류를 누르면 해당 대분류 전체 필터로 전환한다",
    async () => {
      const onSelectionChange =
        jest.fn();

      await render(
        <TrendCategoryFilter
          categories={CATEGORIES}
          selectedCategoryId={12}
          selectedRootCategoryId={1}
          onSelectionChange={
            onSelectionChange
          }
        />,
      );

      await fireEvent.press(
        screen.getByRole(
          "button",
          {
            name: "IT/디지털",
          },
        ),
      );

      expect(
        onSelectionChange,
      ).toHaveBeenCalledWith({
        rootCategoryId: 2,
        categoryId: 2,
      });
    },
  );

  test(
    "전체를 누르면 Category 필터를 해제한다",
    async () => {
      const onSelectionChange =
        jest.fn();

      await render(
        <TrendCategoryFilter
          categories={CATEGORIES}
          selectedCategoryId={12}
          selectedRootCategoryId={1}
          onSelectionChange={
            onSelectionChange
          }
        />,
      );

      await fireEvent.press(
        screen.getByRole(
          "button",
          {
            name: "전체",
          },
        ),
      );

      expect(
        onSelectionChange,
      ).toHaveBeenCalledWith({
        rootCategoryId: null,
        categoryId: null,
      });
    },
  );
    test(
    "대분류가 변경되면 이전 대분류의 세부분류를 표시하지 않는다",
    async () => {
      const onSelectionChange =
        jest.fn();

      const view = await render(
        <TrendCategoryFilter
          categories={CATEGORIES}
          selectedCategoryId={12}
          selectedRootCategoryId={1}
          onSelectionChange={
            onSelectionChange
          }
        />,
      );

      expect(
        screen.getByRole(
          "button",
          {
            name: "PC 게임",
          },
        ),
      ).toBeTruthy();

      await view.rerender(
        <TrendCategoryFilter
          categories={CATEGORIES}
          selectedCategoryId={2}
          selectedRootCategoryId={2}
          onSelectionChange={
            onSelectionChange
          }
        />,
      );

      expect(
        screen.queryByRole(
          "button",
          {
            name: "PC 게임",
          },
        ),
      ).toBeNull();

      expect(
        screen.getByRole(
          "button",
          {
            name: "IT/디지털 전체",
          },
        ),
      ).toBeTruthy();

      expect(
        screen.getByRole(
          "button",
          {
            name: "인공지능",
          },
        ),
      ).toBeTruthy();
    },
  );
});
