export interface CommonResponse<Data> {
    /**
     * 성공 공통 구조
     */

    success: true;
    statusCode: number;
    message: string;
    data: Data;
}

export interface CommonErrorResponse<
  Data = null,
  StatusCode extends number = number,
> {
    /**
     * 실패 공통 구조
     */
    
  success: false;
  statusCode: StatusCode;
  message: string;
  data: Data;
}

export interface ValidationErrorItem {
    /**
     * 422의 오류 하나
     */

  field: string;
  message: string;
  type: string;
}

export interface ValidationErrorData {
    /**
     * 422의 errors 배열
     */

    errors: ValidationErrorItem[];
}