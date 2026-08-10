import { CommonResponse } from "../../../shared/types/api";
import { CategoryListData } from "../types/category";
import { apiClient } from './../../../shared/api/apiClient';


export async function getCategories(): Promise<CategoryListData> {
    const response = await apiClient<
        CommonResponse<CategoryListData>
    >("/categories");

    return response.data.data;
}