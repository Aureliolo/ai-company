import type { ThemeDensity } from "./types.ts"

/** Dense: tight spacing, small text -- Grafana-like data density */
export const densityDense: ThemeDensity = {
  level: "dense",
  cardPadding: "p-3",
  sectionGap: "gap-3",
  gridGap: "gap-3",
  fontSize: {
    metric: "text-2xl",
    label: "text-[10px]",
    body: "text-xs",
    small: "text-[10px]",
  },
}

/** Balanced: comfortable spacing, standard text sizes */
export const densityBalanced: ThemeDensity = {
  level: "balanced",
  cardPadding: "p-4",
  sectionGap: "gap-4",
  gridGap: "gap-4",
  fontSize: {
    metric: "text-3xl",
    label: "text-xs",
    body: "text-sm",
    small: "text-xs",
  },
}

/** Sparse: generous whitespace, Linear-like breathing room */
export const densitySparse: ThemeDensity = {
  level: "sparse",
  cardPadding: "p-5",
  sectionGap: "gap-6",
  gridGap: "gap-6",
  fontSize: {
    metric: "text-3xl",
    label: "text-xs",
    body: "text-sm",
    small: "text-[11px]",
  },
}

/** Medium: between dense and balanced */
export const densityMedium: ThemeDensity = {
  level: "medium",
  cardPadding: "p-[14px]",
  sectionGap: "gap-4",
  gridGap: "gap-4",
  fontSize: {
    metric: "text-2xl",
    label: "text-[11px]",
    body: "text-xs",
    small: "text-[11px]",
  },
}
