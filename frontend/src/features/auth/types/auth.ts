import { CommonErrorResponse, ValidationErrorData } from "../../../shared/types/api";

export type UserStatus =
    | "ACTIVE"
    | "WITHDRAWN"
    | "SUSPENDED";

export type LoginNextStep =
    | "MAIN"
    | "INTEREST_SELECTION";

export interface LoginRequest {
    login_id: string;
    password: string;
}

export interface LoginUser {
    user_id: number;
    login_id: string;
    name: string;
    status: UserStatus;
}

export interface LoginResponse {
    access_token: string;
    token_type: "Bearer";
    user: LoginUser;
    has_selected_interests: boolean;
    next_step: LoginNextStep;
}

export type LoginErrorResponse = 
    | CommonErrorResponse<null, 401>
    | CommonErrorResponse<
        ValidationErrorData,
        422
    >
    | CommonErrorResponse<null, 500>;