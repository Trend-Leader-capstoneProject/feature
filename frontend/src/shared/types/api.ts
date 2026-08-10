export interface CommonResponse<Data> {
    success: true;
    statusCode: number;
    message: string;
    data: Data;
}

export interface CommonErrorResponse<
  Data = null,
  StatusCode extends number = number,
> {
  success: false;
  statusCode: StatusCode;
  message: string;
  data: Data;
}

export interface ValidationErrorItem {
  field: string;
  message: string;
  type: string;
}

export interface ValidationErrorData {
    errors: ValidationErrorItem[];
}