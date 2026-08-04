import { apiRequest } from "../../../shared/api/apiClient";
import { CategoryListData, CommonResponse } from "../types/category";


export async function getCategories(): Promise<CategoryListData> {
    const response = await apiRequest<
        CommonResponse<CategoryListData>
    >("/categories");

    return response.data;
}