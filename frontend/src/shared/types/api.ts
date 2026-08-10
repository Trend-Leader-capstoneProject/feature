export interface CommonResponse<Data> {
    success: true;
    statusCode: number;
    message: string;
    data: Data;
}