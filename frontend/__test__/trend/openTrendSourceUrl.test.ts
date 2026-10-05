import {
    Alert,
    Linking,
} from "react-native";

import {
    openTrendSourceUrl,
} from "../../src/features/trend/utils/openTrendSourceUrl";


describe("openTrendSourceUrl", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  test(
    "Source URL을 OS 외부 링크로 연다",
    async () => {
      const openUrlSpy = jest
        .spyOn(Linking, "openURL")
        .mockResolvedValue(undefined);

      const alertSpy = jest
        .spyOn(Alert, "alert")
        .mockImplementation(
          () => undefined,
        );

      await openTrendSourceUrl(
        "https://example.com/article",
      );

      expect(
        openUrlSpy,
      ).toHaveBeenCalledWith(
        "https://example.com/article",
      );

      expect(
        openUrlSpy,
      ).toHaveBeenCalledTimes(1);

      expect(
        alertSpy,
      ).not.toHaveBeenCalled();
    },
  );

  test(
    "외부 URL을 열지 못하면 사용자에게 안내한다",
    async () => {
      const openUrlSpy = jest
        .spyOn(Linking, "openURL")
        .mockRejectedValue(
          new Error(
            "Cannot open URL",
          ),
        );

      const alertSpy = jest
        .spyOn(Alert, "alert")
        .mockImplementation(
          () => undefined,
        );

      await expect(
        openTrendSourceUrl(
          "https://example.com/article",
        ),
      ).resolves.toBeUndefined();

      expect(
        openUrlSpy,
      ).toHaveBeenCalledWith(
        "https://example.com/article",
      );

      expect(
        alertSpy,
      ).toHaveBeenCalledWith(
        "원문을 열 수 없습니다.",
        "잠시 후 다시 시도해 주세요.",
      );
    },
  );
});
