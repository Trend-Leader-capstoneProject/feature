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
};
