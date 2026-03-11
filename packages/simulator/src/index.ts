export interface Dimensions {
  reliability: number;    // 0-100
  security: number;       // 0-100
  speed: number;          // 0-100
  cost_efficiency: number; // 0-100
  consistency: number;    // 0-100
}

export const WEIGHTS: Dimensions = {
  reliability: 0.30,
  security: 0.20,
  speed: 0.15,
  cost_efficiency: 0.10,
  consistency: 0.25,
};

export type Tier = 'bronze' | 'silver' | 'gold' | 'enterprise';

export interface SimulationResult {
  composite_score: number;
  tier: Tier;
  dimensions: Dimensions;
  weights: Dimensions;
}

export function clamp(value: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, value));
}

export function computeCompositeScore(dims: Dimensions, weights: Dimensions = WEIGHTS): number {
  const score =
    clamp(dims.reliability) * weights.reliability +
    clamp(dims.security) * weights.security +
    clamp(dims.speed) * weights.speed +
    clamp(dims.cost_efficiency) * weights.cost_efficiency +
    clamp(dims.consistency) * weights.consistency;
  return Math.round(score * 100) / 100;
}

export function computeTier(score: number): Tier {
  if (score >= 90) return 'enterprise';
  if (score >= 70) return 'gold';
  if (score >= 40) return 'silver';
  return 'bronze';
}

export function simulate(dims: Partial<Dimensions>, customWeights?: Partial<Dimensions>): SimulationResult {
  const fullDims: Dimensions = {
    reliability: clamp(dims.reliability ?? 50),
    security: clamp(dims.security ?? 50),
    speed: clamp(dims.speed ?? 50),
    cost_efficiency: clamp(dims.cost_efficiency ?? 50),
    consistency: clamp(dims.consistency ?? 50),
  };
  const weights: Dimensions = { ...WEIGHTS, ...customWeights };
  const composite = computeCompositeScore(fullDims, weights);
  return {
    composite_score: composite,
    tier: computeTier(composite),
    dimensions: fullDims,
    weights,
  };
}

export function whatIf(dims: Dimensions, dimension: keyof Dimensions, delta: number): {
  current: SimulationResult;
  projected: SimulationResult;
  impact: number;
} {
  const current = simulate(dims);
  const projected = simulate({ ...dims, [dimension]: clamp(dims[dimension] + delta) });
  return {
    current,
    projected,
    impact: Math.round((projected.composite_score - current.composite_score) * 100) / 100,
  };
}
