import { CommonErrorResponse, ValidationErrorData } from "../../../shared/types/api";

export interface InterestSaveRequest {
    category_ids: number[];
}

export interface InterestSaveResponse {
    selected_category_ids: number[];
    selected_count: number;
}

export interface InterestCategoryRuleErrorData {
  inactive_category_ids: number[];
  child_category_ids: number[];
}

export interface InterestMissingCategoryErrorData {
  category_ids: number[];
}

export type InterestSaveErrorResponse =
  | CommonErrorResponse<
      InterestCategoryRuleErrorData,
      400
    >
  | CommonErrorResponse<null, 401>
  | CommonErrorResponse<
      InterestMissingCategoryErrorData,
      404
    >
  | CommonErrorResponse<null, 409>
  | CommonErrorResponse<
      ValidationErrorData,
      422
    >
  | CommonErrorResponse<null, 500>;

export type InterestReadErrorResponse =
  | CommonErrorResponse<null, 401>
  | CommonErrorResponse<null, 500>;

export type InterestUpdateErrorResponse =
  | CommonErrorResponse<
      InterestCategoryRuleErrorData,
      400
    >
  | CommonErrorResponse<null, 401>
  | CommonErrorResponse<
      InterestMissingCategoryErrorData,
      404
    >
  | CommonErrorResponse<
      InterestUpdateConflictData,
      409
    >
  | CommonErrorResponse<
      ValidationErrorData,
      422
    >
  | CommonErrorResponse<null, 500>;

export interface InterestReadResponse {
  selected_category_ids: number[];
  selected_count: number;
}

export interface InterestUpdateRequest {
  category_ids: number[];
}

export interface InterestUpdateResponse {
  selected_category_ids: number[];
  selected_count: number;
}

export type InterestUpdateConflictReason =
  "INTERESTS_NOT_INITIALIZED";

export interface InterestUpdateConflictData {
  reason: InterestUpdateConflictReason;
}
