# @garl-protocol/simulator

GARL Protocol 5D Trust Score Simulator — calculate composite trust scores and
certification tiers from five dimensions: reliability, security, speed,
cost_efficiency, and consistency.

## Install

```bash
npm install @garl-protocol/simulator
```

## Usage

```typescript
import { simulate, whatIf, computeCompositeScore } from '@garl-protocol/simulator';

// Full simulation with partial dimensions (defaults: 50)
const result = simulate({ reliability: 85, security: 90 });
console.log(result);
// { composite_score: 67.5, tier: 'gold', dimensions: {...}, weights: {...} }

// What-if: impact of improving reliability by 10 points
const analysis = whatIf(
  { reliability: 80, security: 70, speed: 60, cost_efficiency: 50, consistency: 75 },
  'reliability',
  10
);
console.log(analysis.impact);  // e.g. 3.0

// Raw composite score
const score = computeCompositeScore({ reliability: 100, security: 100, speed: 80, cost_efficiency: 70, consistency: 90 });
```

## Example Output

```json
{
  "composite_score": 67.5,
  "tier": "gold",
  "dimensions": { "reliability": 85, "security": 90, "speed": 50, "cost_efficiency": 50, "consistency": 50 },
  "weights": { "reliability": 0.30, "security": 0.20, "speed": 0.15, "cost_efficiency": 0.10, "consistency": 0.25 }
}
```

Tiers: bronze (< 40), silver (40–69), gold (70–89), enterprise (90+).

Interactive simulator: [garl.ai/simulator](https://garl.ai/simulator)
