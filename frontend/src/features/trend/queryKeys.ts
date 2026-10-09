export const trendQueryKeys = {
  all: [
    "trends",
  ] as const,

  list: (
    categoryId: number | null,
    limit: number,
  ) => [
    ...trendQueryKeys.all,
    "list",
    {
      categoryId,
      limit,
    },
  ] as const,

  personalizedAll: [
    "trends",
    "personalized",
  ] as const,

  personalizedList: (
    limit: number,
  ) => [
    ...trendQueryKeys.personalizedAll,
    {
      limit,
    },
  ] as const,
};
