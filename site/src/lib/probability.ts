import type { GoalsModel } from "./types";

// Sum of ln(i) for i = 1..n. Keeps large factorials out of floating-point overflow.
function logFactorial(n: number): number {
  let total = 0;
  for (let i = 2; i <= n; i++) total += Math.log(i);
  return total;
}

export function poissonPmf(k: number, mu: number): number {
  if (!Number.isInteger(k) || k < 0) return 0;
  if (mu === 0) return k === 0 ? 1 : 0;
  return Math.exp(k * Math.log(mu) - mu - logFactorial(k));
}

/**
 * Negative binomial with mean `mu` and size `size` (p = size / (size + mu)).
 * `size === null` means Poisson.
 */
export function negBinPmf(k: number, mu: number, size: number | null): number {
  if (size === null) return poissonPmf(k, mu);
  if (!Number.isInteger(k) || k < 0) return 0;
  if (mu === 0) return k === 0 ? 1 : 0;

  // log p and log(1 - p), written so that large `size` keeps its precision.
  const logP = -Math.log1p(mu / size);
  const logOneMinusP = Math.log(mu) - Math.log(size) - Math.log1p(mu / size);

  // ln C(k + size - 1, k) = sum_{i<k} ln(size + i) - ln(k!)
  let logCoefficient = -logFactorial(k);
  for (let i = 0; i < k; i++) logCoefficient += Math.log(size + i);

  return Math.exp(logCoefficient + size * logP + k * logOneMinusP);
}

/** P(X > line) for a count with mean `mu`. Equals 1 - CDF(floor(line)). */
export function probOver(line: number, mu: number, size: number | null): number {
  const cutoff = Math.floor(line);
  if (cutoff < 0) return 1;
  let cumulative = 0;
  for (let k = 0; k <= cutoff; k++) cumulative += negBinPmf(k, mu, size);
  return Math.min(1, Math.max(0, 1 - cumulative));
}

export function goalLambdas(
  goals: GoalsModel,
  home: string,
  away: string,
): { home: number; away: number } {
  const homeRatings = goals.teams[home];
  const awayRatings = goals.teams[away];
  if (!homeRatings) throw new Error(`Unknown team: ${home}`);
  if (!awayRatings) throw new Error(`Unknown team: ${away}`);
  return {
    home: Math.exp(homeRatings.attack + awayRatings.defense + goals.home_advantage),
    away: Math.exp(awayRatings.attack + homeRatings.defense),
  };
}

// Dixon-Coles low-score correction for cells (0,0), (0,1), (1,0) and (1,1).
function tau(x: number, y: number, lambdaHome: number, lambdaAway: number, rho: number): number {
  if (x === 0 && y === 0) return 1 - lambdaHome * lambdaAway * rho;
  if (x === 0 && y === 1) return 1 + lambdaHome * rho;
  if (x === 1 && y === 0) return 1 + lambdaAway * rho;
  if (x === 1 && y === 1) return 1 - rho;
  return 1;
}

/** matrix[i][j] = P(home scores i, away scores j), truncated at maxGoals and renormalized to sum 1. */
export function scoreMatrix(
  lambdaHome: number,
  lambdaAway: number,
  rho: number,
  maxGoals = 10,
): number[][] {
  const matrix: number[][] = [];
  let total = 0;
  for (let i = 0; i <= maxGoals; i++) {
    const row: number[] = [];
    for (let j = 0; j <= maxGoals; j++) {
      const cell =
        poissonPmf(i, lambdaHome) *
        poissonPmf(j, lambdaAway) *
        tau(i, j, lambdaHome, lambdaAway, rho);
      row.push(cell);
      total += cell;
    }
    matrix.push(row);
  }
  return matrix.map((row) => row.map((cell) => cell / total));
}

export function goalMarkets(matrix: number[][]): {
  home: number;
  draw: number;
  away: number;
  over2_5: number;
  btts: number;
} {
  let home = 0;
  let draw = 0;
  let away = 0;
  let over2_5 = 0;
  let btts = 0;
  matrix.forEach((row, i) => {
    row.forEach((cell, j) => {
      if (i > j) home += cell;
      else if (i === j) draw += cell;
      else away += cell;
      if (i + j > 2.5) over2_5 += cell;
      if (i >= 1 && j >= 1) btts += cell;
    });
  });
  return { home, draw, away, over2_5, btts };
}

/** P(goals scored by `side` > line). */
export function teamGoalsOver(matrix: number[][], side: "home" | "away", line: number): number {
  let total = 0;
  matrix.forEach((row, i) => {
    row.forEach((cell, j) => {
      const goals = side === "home" ? i : j;
      if (goals > line) total += cell;
    });
  });
  return total;
}
