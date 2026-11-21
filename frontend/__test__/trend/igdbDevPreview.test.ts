import {
  fetchIgdbDevPreview,
  IGDB_DEV_PREVIEW_URL,
  parseIgdbDevPreview,
} from "../../src/features/trend/dev/igdbDevPreview";

const VALID = {
  status: "VERIFIED_PREVIEW",
  publication_status: "NOT_FOR_PUBLICATION",
  title: "Free Fire",
  summary: "IGDB Visits 관측 5위",
  rank: 5,
  observed_at_utc: "2026-11-21T00:25:00+00:00",
  calculated_at_utc: "2026-11-21T00:20:35+00:00",
  parent_code: "GAME",
  child_name: "모바일 게임",
  source_url: "https://www.igdb.com/games/free-fire",
};

describe("IGDB local dev preview", () => {
  test("검증된 JSON을 DB 식별자 없는 TrendCard 데이터로 변환한다", () => {
    const result = parseIgdbDevPreview(VALID);

    expect(result.kind).toBe("ready");
    if (result.kind !== "ready") {
      throw new Error("EXPECTED_CARD");
    }
    expect(result.trend).toMatchObject({
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
    });
    expect("trend_id" in result.trend).toBe(false);
    expect("category_id" in result.trend.categories[0]).toBe(false);
    expect("source_id" in result.trend.latest_source!).toBe(false);
  });

  test("후보 없음은 카드와 구별한다", () => {
    expect(parseIgdbDevPreview({
      status: "NO_ELIGIBLE_CANDIDATE",
      publication_status: "NOT_FOR_PUBLICATION",
    })).toEqual({ kind: "empty" });
  });

  test.each([
    { ...VALID, publication_status: "ACTIVE" },
    { ...VALID, rank: 0 },
    { ...VALID, rank: true },
    { ...VALID, title: "" },
    { ...VALID, parent_code: "IT_DIGITAL" },
    { ...VALID, child_name: "알 수 없음" },
    { ...VALID, observed_at_utc: "2026-11-21T09:25:00" },
    { ...VALID, source_url: "javascript:alert(1)" },
    { ...VALID, source_url: "https://www.igdb.com.evil.test/games/free-fire" },
    { ...VALID, source_url: "https://www.igdb.com/games/free-fire?x=1" },
    { status: "NO_ELIGIBLE_CANDIDATE", publication_status: "NOT_FOR_PUBLICATION",
      title: "injected" },
  ])("변조되거나 잘못된 응답은 거부한다 %#", (payload) => {
    expect(() => parseIgdbDevPreview(payload)).toThrow("INVALID_PREVIEW");
  });

  test("로컬 서버의 JSON만 조회하며 게시 API를 호출하지 않는다", async () => {
    const originalFetch = globalThis.fetch;
    const mockFetch = jest.fn(async () => ({
      ok: true,
      json: async () => VALID,
    }));
    globalThis.fetch = mockFetch as typeof globalThis.fetch;
    try {
      const result = await fetchIgdbDevPreview();
      expect(result.kind).toBe("ready");
      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith(
        IGDB_DEV_PREVIEW_URL, { headers: { Accept: "application/json" } },
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test("503과 기타 HTTP 오류는 적격 후보 없음으로 위장하지 않는다", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = jest.fn(async () => ({
      ok: false,
      status: 503,
    })) as typeof globalThis.fetch;
    try {
      await expect(fetchIgdbDevPreview()).rejects.toThrow(
        "PREVIEW_UNAVAILABLE",
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
