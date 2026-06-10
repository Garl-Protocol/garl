"use client";

import { motion } from "framer-motion";
import { useState, useMemo, useEffect } from "react";
import { Share2, RotateCcw } from "lucide-react";

const WEIGHTS = { reliability: 0.30, security: 0.20, speed: 0.15, cost_efficiency: 0.10, consistency: 0.25 };

const DIMENSIONS = [
  { key: "reliability" as const, label: "Reliability", weight: 0.30, color: "bg-green-400", trackColor: "bg-green-400/20" },
  { key: "security" as const, label: "Security", weight: 0.20, color: "bg-red-400", trackColor: "bg-red-400/20" },
  { key: "speed" as const, label: "Speed", weight: 0.15, color: "bg-blue-400", trackColor: "bg-blue-400/20" },
  { key: "cost_efficiency" as const, label: "Cost Efficiency", weight: 0.10, color: "bg-yellow-400", trackColor: "bg-yellow-400/20" },
  { key: "consistency" as const, label: "Consistency", weight: 0.25, color: "bg-purple-400", trackColor: "bg-purple-400/20" },
];

const TIERS = [
  { name: "Enterprise", min: 90, color: "text-purple-400", bg: "bg-purple-400/10", border: "border-purple-400/30" },
  { name: "Gold", min: 70, color: "text-yellow-400", bg: "bg-yellow-400/10", border: "border-yellow-400/30" },
  { name: "Silver", min: 40, color: "text-gray-300", bg: "bg-gray-300/10", border: "border-gray-300/30" },
  { name: "Bronze", min: 0, color: "text-amber-600", bg: "bg-amber-600/10", border: "border-amber-600/30" },
];

const PRESETS: { name: string; desc: string; scores: Record<string, number> }[] = [
  { name: "Baseline", desc: "Fresh agent, no history", scores: { reliability: 50, security: 50, speed: 50, cost_efficiency: 50, consistency: 50 } },
  { name: "Strong Coder", desc: "Reliable coding agent", scores: { reliability: 82, security: 65, speed: 70, cost_efficiency: 55, consistency: 78 } },
  { name: "Enterprise Data", desc: "High-security data agent", scores: { reliability: 88, security: 92, speed: 60, cost_efficiency: 45, consistency: 85 } },
  { name: "Fast & Cheap", desc: "Speed-optimized agent", scores: { reliability: 60, security: 45, speed: 95, cost_efficiency: 90, consistency: 55 } },
  { name: "Gold Tier", desc: "Balanced gold-tier agent", scores: { reliability: 75, security: 70, speed: 72, cost_efficiency: 68, consistency: 74 } },
];

function getTier(score: number) {
  return TIERS.find((t) => score >= t.min) || TIERS[TIERS.length - 1];
}

export default function SimulatorPage() {
  const [scores, setScores] = useState<Record<string, number>>({
    reliability: 50,
    security: 50,
    speed: 50,
    cost_efficiency: 50,
    consistency: 50,
  });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const r = params.get("r"), se = params.get("se"), sp = params.get("sp"), c = params.get("c"), co = params.get("co");
    if (r && se && sp && c && co) {
      setScores({
        reliability: Math.min(100, Math.max(0, Number(r))),
        security: Math.min(100, Math.max(0, Number(se))),
        speed: Math.min(100, Math.max(0, Number(sp))),
        cost_efficiency: Math.min(100, Math.max(0, Number(c))),
        consistency: Math.min(100, Math.max(0, Number(co))),
      });
    }
  }, []);

  const composite = useMemo(() => {
    return Object.entries(WEIGHTS).reduce((sum, [key, weight]) => sum + (scores[key] || 0) * weight, 0);
  }, [scores]);

  const tier = getTier(composite);
  const gaugeAngle = (composite / 100) * 180;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <motion.div initial={false} animate={{ opacity: 1, y: 0 }}>
        <h1 className="mb-2 font-mono text-2xl font-bold">
          <span className="text-garl-accent">$</span> simulator
        </h1>
        <p className="mb-8 font-mono text-sm text-garl-muted">
          Drag the sliders to see how each dimension affects the composite trust score
        </p>

        <div className="grid gap-8 lg:grid-cols-5">
          {/* Sliders */}
          <div className="space-y-5 lg:col-span-3">
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <h2 className="mb-5 font-mono text-xs uppercase tracking-wider text-garl-muted">
                Trust Dimensions
              </h2>
              <div className="space-y-6">
                {DIMENSIONS.map((dim) => (
                  <div key={dim.key}>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="font-mono text-sm text-garl-text">{dim.label}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-garl-muted">{(dim.weight * 100).toFixed(0)}% weight</span>
                        <span className="w-10 text-right font-mono text-sm font-semibold text-garl-text">
                          {scores[dim.key]}
                        </span>
                      </div>
                    </div>
                    <div className="relative">
                      <div className={`absolute inset-0 h-2 rounded-full ${dim.trackColor}`} style={{ top: "50%", transform: "translateY(-50%)" }} />
                      <div
                        className={`absolute h-2 rounded-full ${dim.color}`}
                        style={{
                          top: "50%",
                          transform: "translateY(-50%)",
                          width: `${scores[dim.key]}%`,
                        }}
                      />
                      <input
                        type="range"
                        min={0}
                        max={100}
                        value={scores[dim.key]}
                        onChange={(e) =>
                          setScores((prev) => ({ ...prev, [dim.key]: Number(e.target.value) }))
                        }
                        className="relative z-10 h-2 w-full cursor-pointer appearance-none bg-transparent [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-garl-accent [&::-moz-range-thumb]:bg-garl-bg [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-garl-accent [&::-webkit-slider-thumb]:bg-garl-bg"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Weight breakdown */}
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <h2 className="mb-3 font-mono text-xs uppercase tracking-wider text-garl-muted">
                Weighted Contribution
              </h2>
              <div className="space-y-2">
                {DIMENSIONS.map((dim) => {
                  const contribution = scores[dim.key] * dim.weight;
                  return (
                    <div key={dim.key} className="flex items-center justify-between font-mono text-xs">
                      <span className="text-garl-muted">{dim.label}</span>
                      <span className="text-garl-text">
                        {scores[dim.key]} × {(dim.weight * 100).toFixed(0)}% ={" "}
                        <span className="font-semibold text-garl-accent">{contribution.toFixed(1)}</span>
                      </span>
                    </div>
                  );
                })}
                <div className="mt-2 border-t border-garl-border pt-2">
                  <div className="flex items-center justify-between font-mono text-sm font-semibold">
                    <span className="text-garl-text">Composite Score</span>
                    <span className="text-garl-accent">{composite.toFixed(1)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Score Display */}
          <div className="space-y-4 lg:col-span-2">
            {/* Gauge */}
            <div className="flex flex-col items-center rounded-xl border border-garl-border bg-garl-surface p-6">
              <div className="relative mb-4 h-32 w-56 overflow-hidden">
                <svg viewBox="0 0 200 110" className="h-full w-full">
                  <path
                    d="M 10 100 A 90 90 0 0 1 190 100"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="12"
                    strokeLinecap="round"
                    className="text-garl-border"
                  />
                  <path
                    d="M 10 100 A 90 90 0 0 1 190 100"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="12"
                    strokeLinecap="round"
                    className={tier.color}
                    strokeDasharray={`${(gaugeAngle / 180) * 283} 283`}
                  />
                </svg>
                <div className="absolute inset-x-0 bottom-0 text-center">
                  <span className={`font-mono text-4xl font-bold ${tier.color}`}>
                    {composite.toFixed(1)}
                  </span>
                </div>
              </div>
              <div className={`rounded-lg border px-4 py-2 font-mono text-sm font-semibold ${tier.color} ${tier.bg} ${tier.border}`}>
                {tier.name}
              </div>
            </div>

            {/* Tier Reference */}
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <h2 className="mb-3 font-mono text-xs uppercase tracking-wider text-garl-muted">
                Certification Tiers
              </h2>
              <div className="space-y-2">
                {TIERS.map((t) => (
                  <div
                    key={t.name}
                    className={`flex items-center justify-between rounded-lg border px-3 py-2 font-mono text-xs transition-colors ${
                      tier.name === t.name
                        ? `${t.border} ${t.bg}`
                        : "border-transparent"
                    }`}
                  >
                    <span className={tier.name === t.name ? t.color : "text-garl-muted"}>
                      {t.name}
                    </span>
                    <span className="text-garl-muted">
                      {t.min === 0 ? "0–39" : `${t.min}${t.min === 90 ? "+" : `–${TIERS[TIERS.indexOf(t) - 1]?.min ? TIERS[TIERS.indexOf(t) - 1].min - 1 : 100}`}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Formula */}
            <div className="rounded-xl border border-garl-accent/20 bg-garl-accent/[0.03] p-4">
              <p className="font-mono text-[10px] leading-relaxed text-garl-muted">
                <span className="text-garl-accent">Score</span> = (Reliability × 0.30) + (Security × 0.20) + (Speed × 0.15) + (Cost Efficiency × 0.10) + (Consistency × 0.25)
              </p>
            </div>

            {/* What-If */}
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <h2 className="mb-3 font-mono text-xs uppercase tracking-wider text-garl-muted">
                What-If Analysis
              </h2>
              <div className="space-y-2">
                {DIMENSIONS.map((dim) => {
                  const current = scores[dim.key];
                  const improved = Math.min(100, current + 10);
                  const currentComposite = composite;
                  const newComposite = currentComposite + 10 * dim.weight;
                  const delta = newComposite - currentComposite;
                  const currentTier = tier;
                  const newTier = getTier(newComposite);
                  return (
                    <div key={dim.key} className="flex items-center justify-between font-mono text-xs">
                      <span className="text-garl-muted">{dim.label} +10</span>
                      <div className="flex items-center gap-2">
                        <span className="text-garl-accent">+{delta.toFixed(1)}</span>
                        {newTier.name !== currentTier.name && (
                          <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${newTier.bg} ${newTier.color} ${newTier.border} border`}>
                            → {newTier.name}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <button
                onClick={() => {
                  const url = `${window.location.pathname}?r=${scores.reliability}&se=${scores.security}&sp=${scores.speed}&c=${scores.cost_efficiency}&co=${scores.consistency}`;
                  navigator.clipboard.writeText(window.location.origin + url);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-garl-border bg-garl-surface py-2 font-mono text-xs text-garl-muted transition-colors hover:border-garl-accent/30 hover:text-garl-accent"
              >
                <Share2 className="h-3 w-3" />
                {copied ? "Link copied!" : "Share"}
              </button>
              <button
                onClick={() =>
                  setScores({ reliability: 50, security: 50, speed: 50, cost_efficiency: 50, consistency: 50 })
                }
                className="flex items-center gap-2 rounded-lg border border-garl-border bg-garl-surface px-4 py-2 font-mono text-xs text-garl-muted transition-colors hover:border-garl-accent/30 hover:text-garl-accent"
              >
                <RotateCcw className="h-3 w-3" />
                Reset
              </button>
            </div>
          </div>
        </div>

        {/* Presets */}
        <div className="mt-6">
          <h2 className="mb-3 font-mono text-xs uppercase tracking-wider text-garl-muted">
            Quick Presets
          </h2>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.name}
                onClick={() => setScores({ ...preset.scores })}
                className="rounded-lg border border-garl-border bg-garl-surface px-3 py-2 text-left transition-colors hover:border-garl-accent/30"
              >
                <span className="block font-mono text-xs font-semibold text-garl-text">
                  {preset.name}
                </span>
                <span className="font-mono text-[10px] text-garl-muted">
                  {preset.desc}
                </span>
              </button>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
