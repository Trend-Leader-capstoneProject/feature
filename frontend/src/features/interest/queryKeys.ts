export const categoryQueryKeys = {
  all: ["categories"] as const,
};

export const userInterestQueryKeys = {
  all: ["user-interests"] as const,
  me: ["user-interests", "me"] as const,
};
