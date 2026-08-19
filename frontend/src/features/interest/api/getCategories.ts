import { publicApiClient } from "../../../shared/api/publicApiClient";
import { CommonResponse } from "../../../shared/types/api";
import { CategoryListData } from "../types/category";


export async function getCategories(): Promise<CategoryListData> {
    const response = await publicApiClient<
        CommonResponse<CategoryListData>
    >("/categories");

    return response.data.data;
}
