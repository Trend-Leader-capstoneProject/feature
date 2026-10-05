import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react-native";

import { useCategories } from "../../src/features/interest/hooks/useCategories";
import type { CategoryListData } from "../../src/features/interest/types/category";
import { useTrends } from "../../src/features/trend/hooks/useTrends";
import { LatestTrendScreen } from "../../src/features/trend/screens/LatestTrendScreen";
import type {
  TrendListData,
  TrendListItem,
} from "../../src/features/trend/types/trend";
import { openTrendSourceUrl } from "../../src/features/trend/utils/openTrendSourceUrl";

jest.mock("../../src/features/interest/hooks/useCategories", () => ({
  useCategories: jest.fn(),
}));

jest.mock("../../src/features/trend/hooks/useTrends", () => ({
  useTrends: jest.fn(),
}));

jest.mock("../../src/features/trend/utils/openTrendSourceUrl", () => ({
  openTrendSourceUrl: jest.fn(),
}));

jest.setTimeout(20_000);

const mockedUseCategories = jest.mocked(useCategories);

const mockedUseTrends = jest.mocked(useTrends);

const mockedOpenTrendSourceUrl = jest.mocked(openTrendSourceUrl);

const refetchMock = jest.fn();
const restartMock = jest.fn(async (): Promise<void> => undefined);
const fetchNextPageMock = jest.fn();

const CATEGORY_DATA: CategoryListData = {
  categories: [
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
          category_name: "PC 게임",
          parent_id: 1,
          sort_order: 1,
          children: [],
        },
      ],
    },
  ],
};

function createTrend(
  trendId: number,
  overrides: Partial<TrendListItem> = {},
): TrendListItem {
  return {
    trend_id: trendId,
    title: `Trend ${trendId}`,
    summary: null,
    thumbnail_url: null,
    last_collected_at: "2026-10-01T09:00:00Z",
    categories: [],
    latest_source: null,
    ...overrides,
  };
}

function createPage(
  items: TrendListItem[],
  {
    nextCursor = null,
    hasNext = false,
  }: {
    nextCursor?: string | null;
    hasNext?: boolean;
  } = {},
): TrendListData {
  return {
    items,
    next_cursor: nextCursor,
    has_next: hasNext,
  };
}

function createTrendQueryResult({
  pages,
  isPending = false,
  isError = false,
  isFetching = false,
  hasNextPage = false,
  isFetchingNextPage = false,
  isFetchNextPageError = false,
}: {
  pages?: TrendListData[];
  isPending?: boolean;
  isError?: boolean;
  isFetching?: boolean;
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
  isFetchNextPageError?: boolean;
}) {
  return {
    data:
      pages === undefined
        ? undefined
        : {
            pages,
            pageParams: pages.map((_, index) =>
              index === 0 ? undefined : `CURSOR_${index}`,
            ),
          },

    isPending,
    isError,
    isFetching,

    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,

    refetch: refetchMock,
    restart: restartMock,
    fetchNextPage: fetchNextPageMock,
  } as unknown as ReturnType<typeof useTrends>;
}

function mockCategories(): void {
  mockedUseCategories.mockReturnValue({
    data: CATEGORY_DATA,
    isPending: false,
    isError: false,
    isFetching: false,
    refetch: jest.fn(),
  } as unknown as ReturnType<typeof useCategories>);
}

function createDeferred<T>() {
  let resolvePromise: ((value: T) => void) | null = null;

  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });

  return {
    promise,

    resolve(value: T): void {
      if (!resolvePromise) {
        throw new Error("Deferred Promise가 초기화되지 않았습니다.");
      }

      resolvePromise(value);
    },
  };
}

describe("LatestTrendScreen", () => {

  beforeEach(() => {
    jest.clearAllMocks();

    mockedUseCategories.mockReset();
    mockedUseTrends.mockReset();
    mockedOpenTrendSourceUrl.mockReset();

    refetchMock.mockReset();
    restartMock.mockReset();
    fetchNextPageMock.mockReset();

    refetchMock.mockResolvedValue(
      undefined,
    );

    restartMock.mockResolvedValue(
      undefined,
    );

    fetchNextPageMock.mockResolvedValue(
      undefined,
    );

    mockCategories();

    mockedOpenTrendSourceUrl
      .mockResolvedValue(undefined);
  });

  test("화면 기본 정보와 여러 Page의 Trend를 연속 순번으로 표시한다", async () => {
    mockedUseTrends.mockReturnValue(
      createTrendQueryResult({
        pages: [
          createPage(
            [
              createTrend(101, {
                latest_source: {
                  source_id: 501,
                  platform: "GOOGLE",
                  source_title: "관련 기사",
                  source_url: "https://example.com/article",
                },
              }),
              createTrend(102),
            ],
            {
              nextCursor: "CURSOR_1",
              hasNext: true,
            },
          ),
          createPage([createTrend(103)]),
        ],
      }),
    );

    await render(<LatestTrendScreen />);

    expect(screen.getByText("T&L")).toBeTruthy();

    expect(screen.getByText("최신 트렌드")).toBeTruthy();

    expect(
      screen.getByText("최근 업데이트된 다양한 트렌드를 확인해 보세요."),
    ).toBeTruthy();

    expect(
      screen.getByRole("button", {
        name: "전체",
      }),
    ).toBeTruthy();

    expect(
      screen.getByRole("button", {
        name: "게임",
      }),
    ).toBeTruthy();

    expect(screen.getByText("Trend 101")).toBeTruthy();

    expect(screen.getByText("Trend 102")).toBeTruthy();

    expect(screen.getByText("Trend 103")).toBeTruthy();

    expect(screen.getByText("#1")).toBeTruthy();

    expect(screen.getByText("#2")).toBeTruthy();

    expect(screen.getByText("#3")).toBeTruthy();

    await fireEvent.press(
      screen.getByRole("button", {
        name: "원문 보기",
      }),
    );

    expect(mockedOpenTrendSourceUrl).toHaveBeenCalledWith(
      "https://example.com/article",
    );
  });

  test("초기 Trend 조회 중에는 Loading Feedback을 표시한다", async () => {
    mockedUseTrends.mockReturnValue(
      createTrendQueryResult({
        isPending: true,
      }),
    );

    await render(<LatestTrendScreen />);

    expect(screen.getByText("최신 트렌드를 불러오고 있습니다.")).toBeTruthy();
  });

  test("초기 Trend 조회 실패 시 다시 시도할 수 있다", async () => {
    mockedUseTrends.mockReturnValue(
      createTrendQueryResult({
        isError: true,
      }),
    );

    await render(<LatestTrendScreen />);

    expect(screen.getByText("최신 트렌드를 불러오지 못했습니다.")).toBeTruthy();

    await fireEvent.press(
      screen.getByRole("button", {
        name: "다시 시도",
      }),
    );

    expect(refetchMock).toHaveBeenCalledTimes(1);
  });

  test("전체 목록이 비어 있으면 전체 Empty Feedback을 표시한다", async () => {
    mockedUseTrends.mockReturnValue(
      createTrendQueryResult({
        pages: [createPage([])],
      }),
    );

    await render(<LatestTrendScreen />);

    expect(screen.getByText("표시할 트렌드가 없습니다.")).toBeTruthy();
  });

  test("Category를 선택하면 해당 Category Query로 전환하고 Filtered Empty를 표시한다", async () => {
    mockedUseTrends.mockImplementation(({ categoryId }) =>
      createTrendQueryResult({
        pages: [createPage(categoryId === null ? [createTrend(101)] : [])],
      }),
    );

    await render(<LatestTrendScreen />);

    expect(screen.getByText("Trend 101")).toBeTruthy();

    await fireEvent.press(
      screen.getByRole("button", {
        name: "게임",
      }),
    );

    await waitFor(() => {
      expect(mockedUseTrends).toHaveBeenLastCalledWith({
        categoryId: 1,
      });
    });

    expect(
      screen.getByText("이 분야에 표시할 트렌드가 없습니다."),
    ).toBeTruthy();

    expect(
      screen.getByRole("button", {
        name: "게임 전체",
      }),
    ).toBeTruthy();
  });

  test("목록 끝에 도달하면 다음 Page를 한 번만 요청하고 진행 중 중복 호출을 막는다", async () => {
    const nextPage = createDeferred<void>();

    fetchNextPageMock.mockImplementation(() => nextPage.promise);

    mockedUseTrends.mockReturnValue(
      createTrendQueryResult({
        pages: [
          createPage([createTrend(101)], {
            nextCursor: "CURSOR_1",
            hasNext: true,
          }),
        ],
        hasNextPage: true,
      }),
    );

    await render(<LatestTrendScreen />);

    const list = screen.getByTestId("trend-list");

    await fireEvent(list, "endReached");

    await fireEvent(list, "endReached");

    expect(fetchNextPageMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      nextPage.resolve(undefined);

      await nextPage.promise;
      await Promise.resolve();
    });
  });

  test("다음 Page가 없으면 목록 끝에서도 추가 요청하지 않는다", async () => {
    mockedUseTrends.mockReturnValue(
      createTrendQueryResult({
        pages: [createPage([createTrend(101)])],
        hasNextPage: false,
      }),
    );

    await render(<LatestTrendScreen />);

    await fireEvent(screen.getByTestId("trend-list"), "endReached");

    expect(fetchNextPageMock).not.toHaveBeenCalled();
  });

  test("다음 Page를 불러오는 동안 기존 목록과 하단 Loading을 함께 유지한다", async () => {
    mockedUseTrends.mockReturnValue(
      createTrendQueryResult({
        pages: [createPage([createTrend(101)])],
        hasNextPage: true,
        isFetchingNextPage: true,
      }),
    );

    await render(<LatestTrendScreen />);

    expect(screen.getByText("Trend 101")).toBeTruthy();

    expect(screen.getByRole("progressbar")).toBeTruthy();
  });

  test("다음 Page 조회 실패 시 기존 목록을 유지하고 Retry한다", async () => {
    mockedUseTrends.mockReturnValue(
      createTrendQueryResult({
        pages: [
          createPage([createTrend(101)], {
            nextCursor: "CURSOR_1",
            hasNext: true,
          }),
        ],
        hasNextPage: true,
        isFetchNextPageError: true,
      }),
    );

    await render(<LatestTrendScreen />);

    expect(screen.getByText("Trend 101")).toBeTruthy();

    expect(screen.getByText("다음 트렌드를 불러오지 못했습니다.")).toBeTruthy();

    /*
     * Error 상태에서 스크롤 끝 이벤트가
     * 자동 Retry를 일으키면 안 된다.
     */
    await fireEvent(screen.getByTestId("trend-list"), "endReached");

    expect(fetchNextPageMock).not.toHaveBeenCalled();

    await fireEvent.press(
      screen.getByRole("button", {
        name: "다시 시도",
      }),
    );

    expect(fetchNextPageMock).toHaveBeenCalledTimes(1);
  });
});
