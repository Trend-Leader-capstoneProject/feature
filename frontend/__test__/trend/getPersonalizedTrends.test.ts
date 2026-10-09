import type { AxiosResponse } from "axios";

import {
    getPersonalizedTrends,
} from "../../src/features/trend/api/getPersonalizedTrends";

import type {
    TrendListData,
} from "../../src/features/trend/types/trend";

import {
    authenticatedApiClient,
} from "../../src/shared/api/authenticatedApiClient";

import type {
    CommonResponse,
} from "../../src/shared/types/api";

jest.mock(
  "../../src/shared/api/authenticatedApiClient",
  () => ({
    authenticatedApiClient: {
      get: jest.fn(),
    },
  }),
);

const mockedGet = jest.mocked(
  authenticatedApiClient.get,
);

describe("getPersonalizedTrends", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  test(
    "인증 Client에 Cursor, limit, AbortSignal을 전달하고 data를 반환한다",
    async () => {
      const controller = new AbortController();

      const trendData: TrendListData = {
        items: [],
        next_cursor: null,
        has_next: false,
      };

      mockedGet.mockResolvedValueOnce({
        data: {
          success: true,
          statusCode: 200,
          message: "조회 성공",
          data: trendData,
        },
      } as AxiosResponse<
        CommonResponse<TrendListData>
      >);

      const result =
        await getPersonalizedTrends(
          {
            cursor: "CURSOR_A",
            limit: 20,
          },
          controller.signal,
        );

      expect(mockedGet).toHaveBeenCalledTimes(1);

      expect(mockedGet).toHaveBeenCalledWith(
        "/trends/personalized",
        {
          params: {
            cursor: "CURSOR_A",
            limit: 20,
          },
          signal: controller.signal,
        },
      );

      expect(result).toEqual(trendData);
    },
  );
});
