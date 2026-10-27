import { describe, expect, it } from "vitest";
import E0 from "../../contract/example/leagues/E0.json";
import {
  goalLambdas,
  goalMarkets,
  negBinPmf,
  poissonPmf,
  probOver,
  scoreMatrix,
  teamGoalsOver,
} from "../src/lib/probability";

function expectClose(actual: number, expected: number, tolerance: number): void {
  expect(Math.abs(actual - expected)).toBeLessThan(tolerance);
}

describe("poissonPmf", () => {
  it("returns exp(-mu) for k = 0", () => {
    expectClose(poissonPmf(0, 1), Math.exp(-1), 1e-12);
  });

  it("sums to 1 over k <= 50", () => {
    let total = 0;
    for (let k = 0; k <= 50; k++) total += poissonPmf(k, 3.2);
    expectClose(total, 1, 1e-12);
  });
});

describe("negBinPmf", () => {
  it("approaches the Poisson pmf when size is huge", () => {
    for (let k = 0; k <= 10; k++) {
      expectClose(negBinPmf(k, 4, 1e9), poissonPmf(k, 4), 1e-6);
    }
  });

  it("falls back to Poisson when size is null", () => {
    expectClose(negBinPmf(3, 2.5, null), poissonPmf(3, 2.5), 1e-12);
  });

  it("has mean mu and variance mu + mu^2 / size", () => {
    let mean = 0;
    let secondMoment = 0;
    for (let k = 0; k <= 200; k++) {
      const p = negBinPmf(k, 4, 2);
      mean += k * p;
      secondMoment += k * k * p;
    }
    expectClose(mean, 4, 1e-6);
    expectClose(secondMoment - mean * mean, 4 + 16 / 2, 1e-4);
  });
});

describe("probOver", () => {
  it("computes P(X > 2.5) for a Poisson with mu 2.5", () => {
    expectClose(probOver(2.5, 2.5, null), 0.4562, 1e-4);
  });

  it("uses floor(line) as the cumulative cut-off", () => {
    expectClose(probOver(2.2, 2.5, null), probOver(2.5, 2.5, null), 1e-12);
  });
});

describe("goalLambdas", () => {
  it("applies attack, opponent defense and home advantage for Arsenal-Brighton", () => {
    const lambdas = goalLambdas(E0.goals, "Arsenal", "Brighton");
    expectClose(lambdas.home, Math.exp(0.35 + 0.05 + 0.25), 1e-12);
    expectClose(lambdas.away, Math.exp(0.0 - 0.3), 1e-12);
  });
});

describe("scoreMatrix", () => {
  it("equals the renormalized Poisson product when rho is 0", () => {
    const matrix = scoreMatrix(1.4, 1.1, 0, 10);
    let raw = 0;
    for (let i = 0; i <= 10; i++) {
      for (let j = 0; j <= 10; j++) {
        raw += poissonPmf(i, 1.4) * poissonPmf(j, 1.1);
      }
    }
    for (let i = 0; i <= 10; i++) {
      for (let j = 0; j <= 10; j++) {
        expectClose(matrix[i][j], (poissonPmf(i, 1.4) * poissonPmf(j, 1.1)) / raw, 1e-12);
      }
    }
  });

  it("sums to 1 for a negative rho", () => {
    const matrix = scoreMatrix(1.4, 1.1, -0.1, 10);
    const total = matrix.flat().reduce((acc, value) => acc + value, 0);
    expectClose(total, 1, 1e-9);
  });
});

describe("goalMarkets", () => {
  it("gives equal home and away probabilities for symmetric teams", () => {
    const markets = goalMarkets(scoreMatrix(1, 1, 0, 10));
    expectClose(markets.home, markets.away, 1e-9);
    expectClose(markets.home + markets.draw + markets.away, 1, 1e-9);
  });

  it("returns over 2.5 and BTTS probabilities that stay within [0, 1]", () => {
    const markets = goalMarkets(scoreMatrix(1.6, 1.2, -0.05, 10));
    expect(markets.over2_5).toBeGreaterThan(0);
    expect(markets.over2_5).toBeLessThan(1);
    expect(markets.btts).toBeGreaterThan(0);
    expect(markets.btts).toBeLessThan(1);
  });
});

describe("teamGoalsOver", () => {
  it("sums the home team's goal rows strictly above the line", () => {
    const matrix = scoreMatrix(1.4, 1.1, 0, 10);
    const expected = matrix
      .map((row, i) => (i > 1.5 ? row.reduce((acc, value) => acc + value, 0) : 0))
      .reduce((acc, value) => acc + value, 0);
    expectClose(teamGoalsOver(matrix, "home", 1.5), expected, 1e-12);
  });
});
