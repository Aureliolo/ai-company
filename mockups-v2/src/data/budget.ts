import type { BudgetDay } from "@/data/types"
import { createRng, randFloat } from "@/data/seed"

// ---------------------------------------------------------------------------
// 30-day budget history: Mar 1 - Mar 30, 2026
// ---------------------------------------------------------------------------

function buildBudgetHistory(): BudgetDay[] {
  const rng = createRng(2026)
  const days: BudgetDay[] = []

  // Parameters
  const today = 23 // Mar 23 is "today"

  // Generate daily actual spend for days 1-23
  // Start around $8-15/day, trend slightly upward as org grows
  let cumulativeActual = 0
  const dailyActuals: number[] = []

  for (let d = 1; d <= 30; d++) {
    // Base daily spend increases slightly over time (org ramp-up)
    const baseSpend = 55 + d * 1.2
    const dailySpend = randFloat(rng, baseSpend * 0.75, baseSpend * 1.3)
    dailyActuals.push(dailySpend)
  }

  for (let d = 1; d <= 30; d++) {
    const dayLabel = `Mar ${d}`
    cumulativeActual += dailyActuals[d - 1]

    if (d < today) {
      // Past days: actual only
      days.push({
        day: dayLabel,
        actual: Math.round(cumulativeActual * 100) / 100,
        forecast: null,
      })
    } else if (d === today) {
      // Today: both actual and forecast
      days.push({
        day: dayLabel,
        actual: Math.round(cumulativeActual * 100) / 100,
        forecast: Math.round(cumulativeActual * 100) / 100,
      })
    } else {
      // Future: forecast only (projected at average daily rate)
      const avgDaily = cumulativeActual / today
      const projected = cumulativeActual + avgDaily * (d - today)
      days.push({
        day: dayLabel,
        actual: null,
        forecast: Math.round(projected * 100) / 100,
      })
    }
  }

  return days
}

export const budgetHistory: BudgetDay[] = buildBudgetHistory()

// ---------------------------------------------------------------------------
// Budget summary
// ---------------------------------------------------------------------------

function buildBudgetSummary() {
  const todayEntry = budgetHistory.find((d) => d.day === "Mar 23")
  const endEntry = budgetHistory[budgetHistory.length - 1]
  const totalSpent = todayEntry?.actual ?? 0
  const monthlyBudget = 2400
  const daysLeft = 30 - 23
  const projectedTotal = endEntry?.forecast ?? 0

  return {
    remaining: Math.round((monthlyBudget - totalSpent) * 100) / 100,
    percentUsed: Math.round((totalSpent / monthlyBudget) * 10000) / 100,
    daysLeft,
    projectedTotal: Math.round(projectedTotal * 100) / 100,
  }
}

export const budgetSummary = buildBudgetSummary()
