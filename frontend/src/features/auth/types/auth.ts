import type {
  CommonErrorResponse,
  ValidationErrorData,
} from "../../../shared/types/api";

export type UserStatus =
  | "ACTIVE"
  | "WITHDRAWN"
  | "SUSPENDED";

export type AuthNextStep =
  | "MAIN"
  | "INTEREST_SELECTION";

export interface AuthUser {
  user_id: number;
  login_id: string;
  name: string;
  status: UserStatus;
}

export interface LoginRequest {
  login_id: string;
  password: string;
}

export interface SignupRequest {
  nickname: string;
  login_id: string;
  password: string;
  password_confirm: string;
  name: string;
  email?: string | null;
}

export interface CheckLoginIdRequest {
  login_id: string;
}

export interface SessionResponse {
  user: AuthUser;
  has_selected_interests: boolean;
  next_step: AuthNextStep;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  access_expires_at: string;
  refresh_expires_at: string;
}

export interface AuthSuccessResponse
  extends SessionResponse, TokenPair {
  /** 앱에서만 붙이는 요청 소속. 서버의 응답 필드는 아니다. */
  _requestEpoch?: number;
  access_token: string;
  token_type: "Bearer";
}

export type LoginResponse =
  AuthSuccessResponse;

export type SignupResponse =
  AuthSuccessResponse;

export type LoginIdAvailabilityReason =
  "DUPLICATED_LOGIN_ID";

export interface CheckLoginIdResponse {
  login_id: string;
  is_available: boolean;
  reason: LoginIdAvailabilityReason | null;
}

export type SignupConflictField =
  | "nickname"
  | "login_id"
  | "email";

export type SignupConflictReason =
  | "DUPLICATED_LOGIN_ID"
  | "DUPLICATED_NICKNAME"
  | "DUPLICATED_EMAIL";

export type SignupConflictData =
  | { field: "nickname"; reason: "DUPLICATED_NICKNAME" }
  | {
      field: "login_id";
      reason: "DUPLICATED_LOGIN_ID";
    }
  | {
      field: "email";
      reason: "DUPLICATED_EMAIL";
    };

export type LoginErrorResponse =
  | CommonErrorResponse<null, 401>
  | CommonErrorResponse<
      ValidationErrorData,
      422
    >
  | CommonErrorResponse<null, 500>;

export type SignupErrorResponse =
  | CommonErrorResponse<
      SignupConflictData,
      409
    >
  | CommonErrorResponse<
      ValidationErrorData,
      422
    >
  | CommonErrorResponse<null, 500>;

export type CheckLoginIdErrorResponse =
  | CommonErrorResponse<
      ValidationErrorData,
      422
    >
  | CommonErrorResponse<null, 500>;
