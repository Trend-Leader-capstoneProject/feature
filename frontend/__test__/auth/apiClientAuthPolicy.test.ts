import {
    AxiosError,
    AxiosHeaders,
    type AxiosAdapter,
    type AxiosResponse,
    type InternalAxiosRequestConfig,
} from "axios";

import {
    login,
} from "../../src/features/auth/api/login";
import {
    authenticatedApiClient,
} from "../../src/shared/api/authenticatedApiClient";
import {
    publicApiClient,
} from "../../src/shared/api/publicApiClient";
import {
    notifyAuthFailure,
} from "../../src/shared/handler/authFailureHandler";
import {
    areAuthenticatedRequestsBlocked,
} from "../../src/shared/handler/authRequestGate";
import {
    getAccessToken,
} from "../../src/shared/storage/tokenStorage";

jest.mock(
  "../../src/app/config/apiConfig",
  () => ({
    API_BASE_URL:
      "http://127.0.0.1:8000/api",
  }),
);

jest.mock(
  "../../src/shared/handler/authFailureHandler",
  () => ({
    notifyAuthFailure: jest.fn(),
  }),
);

jest.mock(
  "../../src/shared/handler/authRequestGate",
  () => ({
    areAuthenticatedRequestsBlocked:
      jest.fn(),
  }),
);

jest.mock(
  "../../src/shared/storage/tokenStorage",
  () => ({
    getAccessToken: jest.fn(),
  }),
);

const mockedNotifyAuthFailure =
  jest.mocked(notifyAuthFailure);

const mockedAreAuthenticatedRequestsBlocked =
  jest.mocked(
    areAuthenticatedRequestsBlocked,
  );

const mockedGetAccessToken =
  jest.mocked(getAccessToken);

const originalAuthenticatedAdapter =
  authenticatedApiClient.defaults.adapter;

const originalPublicAdapter =
  publicApiClient.defaults.adapter;

function createResponse(
  config: InternalAxiosRequestConfig,
  status: number,
): AxiosResponse<null> {
  return {
    data: null,
    status,
    statusText:
      status === 200
        ? "OK"
        : status === 401
          ? "Unauthorized"
          : "Error",
    headers: new AxiosHeaders(),
    config,
  };
}

function createRejectingAdapter(
  status: number,
): AxiosAdapter {
  return async (config) => {
    const response =
      createResponse(
        config,
        status,
      );

    throw new AxiosError(
      `Request failed with status code ${status}`,
      undefined,
      config,
      undefined,
      response,
    );
  };
}

describe("API Client auth policy", () => {
  beforeEach(() => {
    jest.resetAllMocks();

    mockedAreAuthenticatedRequestsBlocked
      .mockReturnValue(false);

    authenticatedApiClient.defaults.adapter =
      originalAuthenticatedAdapter;

    publicApiClient.defaults.adapter =
      originalPublicAdapter;
  });

  afterAll(() => {
    authenticatedApiClient.defaults.adapter =
      originalAuthenticatedAdapter;

    publicApiClient.defaults.adapter =
      originalPublicAdapter;
  });

  test(
    "보호 API 요청에는 현재 Access Token을 Bearer Header로 주입한다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        "TOKEN_A",
      );

      let authorizationHeader:
        string | undefined;

      authenticatedApiClient.defaults.adapter =
        async (config) => {
          const authorization =
            config.headers.get(
              "Authorization",
            );

          authorizationHeader =
            typeof authorization === "string"
              ? authorization
              : undefined;

          return createResponse(
            config,
            200,
          );
        };

      await authenticatedApiClient.get(
        "/protected",
      );

      expect(
        authorizationHeader,
      ).toBe("Bearer TOKEN_A");

      expect(
        mockedGetAccessToken,
      ).toHaveBeenCalledTimes(1);
    },
  );

  test(
    "현재 Access Token으로 보낸 보호 API가 401이면 Auth Failure를 발생시킨다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        "TOKEN_A",
      );

      authenticatedApiClient.defaults.adapter =
        createRejectingAdapter(401);

      await expect(
        authenticatedApiClient.get(
          "/protected",
        ),
      ).rejects.toMatchObject({
        response: {
          status: 401,
        },
      });

      expect(
        mockedNotifyAuthFailure,
      ).toHaveBeenCalledTimes(1);

      expect(
        mockedGetAccessToken,
      ).toHaveBeenCalledTimes(2);
    },
  );

  test(
    "TOKEN_A 요청의 늦은 401이 도착했을 때 현재 Token이 TOKEN_B이면 Auth Failure를 발생시키지 않는다",
    async () => {
      mockedGetAccessToken
        .mockResolvedValueOnce(
          "TOKEN_A",
        )
        .mockResolvedValueOnce(
          "TOKEN_B",
        );

      authenticatedApiClient.defaults.adapter =
        createRejectingAdapter(401);

      await expect(
        authenticatedApiClient.get(
          "/protected",
        ),
      ).rejects.toMatchObject({
        response: {
          status: 401,
        },
      });

      expect(
        mockedNotifyAuthFailure,
      ).not.toHaveBeenCalled();

      expect(
        mockedGetAccessToken,
      ).toHaveBeenCalledTimes(2);
    },
  );

  test(
    "Bearer Token 없이 보낸 요청의 401은 Auth Failure를 발생시키지 않는다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        null,
      );

      authenticatedApiClient.defaults.adapter =
        createRejectingAdapter(401);

      await expect(
        authenticatedApiClient.get(
          "/protected",
        ),
      ).rejects.toMatchObject({
        response: {
          status: 401,
        },
      });

      expect(
        mockedNotifyAuthFailure,
      ).not.toHaveBeenCalled();

      expect(
        mockedGetAccessToken,
      ).toHaveBeenCalledTimes(1);
    },
  );

  test(
    "401이 아닌 보호 API 오류는 Auth Failure를 발생시키지 않는다",
    async () => {
      mockedGetAccessToken.mockResolvedValue(
        "TOKEN_A",
      );

      authenticatedApiClient.defaults.adapter =
        createRejectingAdapter(500);

      await expect(
        authenticatedApiClient.get(
          "/protected",
        ),
      ).rejects.toMatchObject({
        response: {
          status: 500,
        },
      });

      expect(
        mockedNotifyAuthFailure,
      ).not.toHaveBeenCalled();

      expect(
        mockedGetAccessToken,
      ).toHaveBeenCalledTimes(1);
    },
  );

  test(
    "Session 종료가 이미 시작된 상태에서는 보호 API 요청을 보내지 않는다",
    async () => {
      mockedAreAuthenticatedRequestsBlocked
        .mockReturnValue(true);

      let adapterCalled = false;

      authenticatedApiClient.defaults.adapter =
        async (config) => {
          adapterCalled = true;

          return createResponse(
            config,
            200,
          );
        };

      await expect(
        authenticatedApiClient.get(
          "/protected",
        ),
      ).rejects.toThrow(
        "Authenticated request is blocked during session termination.",
      );

      expect(
        mockedGetAccessToken,
      ).not.toHaveBeenCalled();

      expect(adapterCalled).toBe(false);
    },
  );

  test(
    "Access Token 조회 중 Session 종료가 시작되면 보호 API 요청을 보내지 않는다",
    async () => {
      mockedAreAuthenticatedRequestsBlocked
        .mockReturnValueOnce(false)
        .mockReturnValueOnce(true);

      mockedGetAccessToken.mockResolvedValue(
        "TOKEN_A",
      );

      let adapterCalled = false;

      authenticatedApiClient.defaults.adapter =
        async (config) => {
          adapterCalled = true;

          return createResponse(
            config,
            200,
          );
        };

      await expect(
        authenticatedApiClient.get(
          "/protected",
        ),
      ).rejects.toThrow(
        "Authenticated request is blocked during session termination.",
      );

      expect(
        mockedGetAccessToken,
      ).toHaveBeenCalledTimes(1);

      expect(adapterCalled).toBe(false);
    },
  );

  test(
    "로그인 API의 401은 Global Auth Failure를 발생시키지 않는다",
    async () => {
      publicApiClient.defaults.adapter =
        createRejectingAdapter(401);

      await expect(
        login({
          login_id: "wrong_user",
          password: "wrong_password",
        }),
      ).rejects.toMatchObject({
        response: {
          status: 401,
        },
      });

      expect(
        mockedNotifyAuthFailure,
      ).not.toHaveBeenCalled();

      expect(
        mockedGetAccessToken,
      ).not.toHaveBeenCalled();
    },
  );
});
