export type CategoryCode = 
    | "FASHION"
    | "FOOD"
    | "IT_DIGITAL"
    | "ENTERTAINMENT"
    | "BEAUTY"
    | "GAME";

export interface CategoryItem {
    category_id: number;
    category_code: CategoryCode | null;   // 세부분류에서는 코드가 없기 때문에 null 가능
    category_name: string;    
    parent_id: number | null;
    sort_order: number;
    children: CategoryItem[];
}

export interface CategoryListData {
    categories: CategoryItem[];
}
