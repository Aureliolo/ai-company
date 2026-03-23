// Mulberry32 seeded PRNG
export function createRng(seed: number) {
  let s = seed | 0
  return function random(): number {
    s = (s + 0x6d2b79f5) | 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// Helper: pick random item from array
export function pick<T>(rng: () => number, arr: T[]): T {
  return arr[Math.floor(rng() * arr.length)]
}

// Helper: random int in range [min, max]
export function randInt(rng: () => number, min: number, max: number): number {
  return Math.floor(rng() * (max - min + 1)) + min
}

// Helper: random float in range [min, max] with 2 decimal places
export function randFloat(
  rng: () => number,
  min: number,
  max: number,
): number {
  return Math.round((rng() * (max - min) + min) * 100) / 100
}

// Helper: weighted random pick
export function weightedPick<T>(
  rng: () => number,
  items: T[],
  weights: number[],
): T {
  const total = weights.reduce((a, b) => a + b, 0)
  let r = rng() * total
  for (let i = 0; i < items.length; i++) {
    r -= weights[i]
    if (r <= 0) return items[i]
  }
  return items[items.length - 1]
}
