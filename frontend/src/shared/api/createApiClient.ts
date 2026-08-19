
import axios from "axios";
import { API_BASE_URL } from '../../app/config/apiConfig';

export function createApiClient() {
    return axios.create({
        baseURL: API_BASE_URL,
        timeout: 10_000,
        headers: {
            "Content-Type": "application/json",
        },
    });
}
