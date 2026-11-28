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
    expect(screen.queryByLabelText("카테고리 썸네일: 게임")).toBeNull();
  });

  test("thumbnail_url이 null이면 첫 번째 표시 카테고리의 자체 썸네일을 사용한다", async () => {
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
    expect(screen.getByLabelText("카테고리 썸네일: 게임")).toBeTruthy();
  });

  test("Thumbnail 로딩에 실패하면 카테고리 썸네일로 대체한다", async () => {
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
      expect(screen.getByLabelText("카테고리 썸네일: 게임")).toBeTruthy();
    });
  });

  test.each([
    ["FASHION", "패션"],
    ["FOOD", "음식"],
    ["IT_DIGITAL", "IT/디지털"],
    ["ENTERTAINMENT", "엔터테인먼트"],
    ["BEAUTY", "뷰티"],
    ["GAME", "게임"],
  ] as const)("카테고리 코드 %s에 대응하는 자체 썸네일을 표시한다", async (code, label) => {
    const trend = createTrend();
    await render(<TrendCard onOpenSource={jest.fn()} trend={{
      ...trend,
      categories: [{
        ...trend.categories[0],
        parent: { ...trend.categories[0].parent, category_code: code },
      }],
    }} />);
    expect(screen.getByLabelText(`카테고리 썸네일: ${label}`)).toBeTruthy();
  });

  test("카테고리가 없으면 일반 트렌드 썸네일을 표시한다", async () => {
    await render(<TrendCard onOpenSource={jest.fn()} trend={createTrend({ categories: [] })} />);
    expect(screen.getByLabelText("카테고리 썸네일: 트렌드")).toBeTruthy();
  });

  test("코드 없는 카테고리는 건너뛰고 다음 표시 카테고리를 선택한다", async () => {
    const trend = createTrend();
    const [first, second] = trend.categories;
    await render(<TrendCard onOpenSource={jest.fn()} trend={{
      ...trend,
      categories: [
        { ...first, parent: { ...first.parent, category_code: null } },
        second,
      ],
    }} />);
    expect(screen.getByLabelText("카테고리 썸네일: IT/디지털")).toBeTruthy();
  });

  test("기존 이미지 URL이 변경되면 이전 로딩 실패와 무관하게 새 이미지를 표시한다", async () => {
    const onOpenSource = jest.fn();
    const trend = createTrend({ thumbnail_url: "https://example.com/broken.jpg" });
    const result = await render(<TrendCard onOpenSource={onOpenSource} trend={trend} />);
    await fireEvent(screen.getByLabelText(`${trend.title} 썸네일`), "error");
    expect(screen.getByLabelText("카테고리 썸네일: 게임")).toBeTruthy();

    const newUrl = "https://example.com/new.jpg";
    await result.rerender(<TrendCard onOpenSource={onOpenSource} trend={{
      ...trend, thumbnail_url: newUrl,
    }} />);
    expect(screen.getByLabelText(`${trend.title} 썸네일`)).toHaveProp("source", { uri: newUrl });
    expect(screen.queryByLabelText("카테고리 썸네일: 게임")).toBeNull();
  });

  test("SearchApi 기사형 데이터는 기존 카드의 카테고리·원문 버튼으로 표시한다", async () => {
    const onOpenSource = jest.fn();
    const articleUrl = "https://www.yna.co.kr/view/AKR20261123042700005";
    const trend = createTrend({
      // Isolated contract fixture: these IDs are not operational DB IDs.
      trend_id: 914,
      title: "'굿데이' 시즌2, 2027년 상반기 공개 계획 발표",
      summary: "제작사 TEO가 '굿데이' 시즌2의 2027년 상반기 공개 계획을 알렸습니다.",
      thumbnail_url: null,
      last_collected_at: "2026-11-23T09:00:00Z",
      categories: [{
        category_id: 92,
        category_name: "예능",
        parent: {
          category_id: 9,
          category_name: "엔터테인먼트",
          category_code: "ENTERTAINMENT",
        },
      }],
      latest_source: {
        source_id: 501,
        platform: "ETC",
        source_title: null,
        source_url: articleUrl,
      },
    });

    await render(
      <TrendCard
        displayNumber={1}
        onOpenSource={onOpenSource}
        trend={trend}
      />,
    );

    expect(screen.getByText(trend.title)).toBeTruthy();
    expect(screen.getByText(trend.summary!)).toBeTruthy();
    expect(screen.getByText("엔터테인먼트 · 예능")).toBeTruthy();
    expect(screen.getByText("기타")).toBeTruthy();

    await fireEvent.press(
      screen.getByRole("button", { name: "원문 보기" }),
    );
    expect(onOpenSource).toHaveBeenCalledTimes(1);
    expect(onOpenSource).toHaveBeenCalledWith(articleUrl);
  });

  test("관심도 카드는 관련 정보·뉴스 검색과 관측 출처를 별도로 제공한다", async () => {
    const onOpenSource = jest.fn();
    const sourceUrl = "https://trends.google.com/trending?geo=KR&hl=ko&hours=24";
    const title = "시그널2 & 드라마";
    await render(<TrendCard onOpenSource={onOpenSource} trend={createTrend({
      title,
      latest_source: { source_id: 1, platform: "ETC", source_title: null,
        source_url: sourceUrl },
    })} />);
    expect(screen.getByText("Google Trends")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "관련 정보 검색" }));
    await fireEvent.press(screen.getByRole("button", { name: "관련 뉴스 검색" }));
    await fireEvent.press(screen.getByRole("button", { name: "관측 출처 보기" }));
    expect(onOpenSource.mock.calls).toEqual([
      [`https://www.google.com/search?hl=ko&q=${encodeURIComponent(title)}`],
      [`https://news.google.com/search?hl=ko&gl=KR&ceid=KR%3Ako&q=${encodeURIComponent(title)}`],
      [sourceUrl],
    ]);
  });

  test.each([
    ["https://www.igdb.com/games/free-fire", "IGDB"],
    ["https://github.com/godotengine/godot-builds/releases/tag/4.6-stable", "GitHub"],
    ["https://trends.google.com.example.org/trending?geo=KR&hl=ko&hours=24", "기타"],
  ])("기존 출처 %s는 라벨과 원문 버튼을 유지한다", async (url, label) => {
    const onOpenSource = jest.fn();
    await render(<TrendCard onOpenSource={onOpenSource} trend={createTrend({
      latest_source: { source_id: 1, platform: "ETC", source_title: null,
        source_url: url },
    })} />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "관련 뉴스 검색" })).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "원문 보기" }));
    expect(onOpenSource).toHaveBeenCalledWith(url);
  });

  const interestSource = {
    source_id: 1,
    platform: "ETC" as const,
    source_title: null,
    source_url: "https://trends.google.com/trending?geo=KR&hl=ko&hours=24",
  };
  const reference = {
    publisher: "Fixture A",
    title: null,
    url: "https://example.com/article/1",
    published_at: "2026-11-26T01:00:00Z",
  };

  test("관련 기사 2개를 API 순서대로 표시하며 직접 URL을 연다", async () => {
    const onOpenSource = jest.fn();
    const second = {
      ...reference, publisher: "Fixture B", title: "허용된 제목",
      url: "https://example.org/article/2",
    };
    await render(<TrendCard onOpenSource={onOpenSource} trend={createTrend({
      latest_source: interestSource,
      related_articles: [reference, second],
    })} />);
    expect(screen.getByText("관련 뉴스")).toBeTruthy();
    expect(screen.getByText("허용된 제목")).toBeTruthy();
    expect(screen.getByText(/^Fixture A · /)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "관련 뉴스 검색" })).toBeNull();
    const buttons = screen.getAllByRole("button", { name: /기사 보기 [12]$/ });
    expect(buttons).toHaveLength(2);
    await fireEvent.press(buttons[0]);
    await fireEvent.press(buttons[1]);
    await fireEvent.press(screen.getByRole("button", { name: "관련 정보 검색" }));
    await fireEvent.press(screen.getByRole("button", { name: "관측 출처 보기" }));
    expect(onOpenSource.mock.calls).toEqual([
      [reference.url],
      [second.url],
      [`https://www.google.com/search?hl=ko&q=${encodeURIComponent(createTrend().title)}`],
      [interestSource.source_url],
    ]);
  });

  test.each([
    { articles: [] },
    { articles: [{ ...reference, url: "javascript:alert(1)" }] },
    { articles: [{ ...reference, url: "https://example.com@evil.test/article/1" }] },
    { articles: [{ ...reference, url: "https://127.0.0.1/article/1" }] },
    { articles: [{ ...reference, url: "https://example.com/article/1?redirect=1" }] },
    { articles: [{ ...reference, published_at: "invalid" }] },
  ])("기사 없음 또는 잘못된 기사 배열은 뉴스 검색으로 대체한다: %j", async ({ articles }) => {
    await render(<TrendCard onOpenSource={jest.fn()} trend={createTrend({
      latest_source: interestSource,
      related_articles: articles,
    })} />);
    expect(screen.getByRole("button", { name: "관련 뉴스 검색" })).toBeTruthy();
    expect(screen.queryByText("관련 뉴스")).toBeNull();
  });

  test("정상 기사 하나만 있어도 직접 링크를 제공하고 중복과 초과 건은 제외한다", async () => {
    await render(<TrendCard onOpenSource={jest.fn()} trend={createTrend({
      latest_source: interestSource,
      related_articles: [
        reference,
        { ...reference },
        { ...reference, url: "https://example.com/article/2" },
        { ...reference, url: "https://example.com/article/3" },
      ],
    })} />);
    expect(screen.getAllByRole("button", { name: /기사 보기 [12]$/ })).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "관련 뉴스 검색" })).toBeNull();
  });

  test("기사 1건은 뉴스 검색 없이 제목 없는 직접 링크를 제공한다", async () => {
    await render(<TrendCard onOpenSource={jest.fn()} trend={createTrend({
      latest_source: interestSource,
      related_articles: [reference],
    })} />);
    expect(screen.getByRole("button", { name: "Fixture A 기사 보기 1" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "관련 뉴스 검색" })).toBeNull();
  });

  test("다른 공급원의 관련 기사 필드는 무시하고 기존 원문 버튼을 유지한다", async () => {
    await render(<TrendCard onOpenSource={jest.fn()} trend={createTrend({
      latest_source: { ...interestSource, source_url: "https://www.igdb.com/games/free-fire" },
      related_articles: [reference],
    })} />);
    expect(screen.queryByText("관련 뉴스")).toBeNull();
    expect(screen.getByRole("button", { name: "원문 보기" })).toBeTruthy();
  });

  test("Personalized TrendCard는 순번 없이 기존 콘텐츠를 표시한다", async () => {
    await render(<TrendCard onOpenSource={jest.fn()} trend={createTrend()} />);

    // 맞춤 추천 목록에서는 순번을 표시하지 않는다.
    expect(screen.queryByText(/^#/)).toBeNull();

    // 순번 이외의 콘텐츠는 그대로 유지한다.
    expect(screen.getByText("AI 스마트폰 신제품 공개")).toBeTruthy();

    expect(
      screen.getByText("새로운 온디바이스 AI 기능이 공개되었습니다."),
    ).toBeTruthy();

    expect(screen.getByText("게임 · PC 게임")).toBeTruthy();

    expect(screen.getByText("IT/디지털 · 인공지능")).toBeTruthy();
  });
});
