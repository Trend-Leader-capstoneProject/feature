import axios from "axios";

import { getAccessToken } from "../storage/tokenStorage";
import { API_BASE_URL } from "./../../app/config/apiConfig";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  headers: {
    "Content-Type": "application/json",
  },
});


apiClient.interceptors.request.use(
  async (config) => {
    const accessToken = await getAccessToken();

    if (accessToken) {
      config.headers.set(
        "Authorization",
        `Bearer ${accessToken}`,
      );
    }

    return config;
  },
)