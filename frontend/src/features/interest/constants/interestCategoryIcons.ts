import type {
    ImageSourcePropType,
} from "react-native";

import type {
    CategoryCode,
} from "../types/category";

export const interestCategoryIcons:
  Record<CategoryCode, ImageSourcePropType> = {
    FASHION: require(
      "../../../../assets/images/interests/fashion.png"
    ),
    FOOD: require(
      "../../../../assets/images/interests/food.png"
    ),
    IT_DIGITAL: require(
      "../../../../assets/images/interests/it-digital.png"
    ),
    ENTERTAINMENT: require(
      "../../../../assets/images/interests/entertainment.png"
    ),
    BEAUTY: require(
      "../../../../assets/images/interests/beauty.png"
    ),
    GAME: require(
      "../../../../assets/images/interests/game.png"
    ),
  };
