/**
 * Identicon — deterministic gradient avatar for an agent.
 *
 * Hashes the seed (agent UUID or name) into a hue + 2-letter monogram so
 * every agent gets a visually distinct circle on receipt pages, agent
 * cards, and OG cards. No external service, no PII leakage — pure
 * function of inputs.
 */

const seedHash = (seed: string): number => {
  let h = 5381;
  for (let i = 0; i < seed.length; i++) {
    h = ((h << 5) + h + seed.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
};

const monogram = (name: string): string => {
  const cleaned = name.replace(/[^A-Za-z0-9]+/g, " ").trim();
  if (!cleaned) return "??";
  const parts = cleaned.split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return cleaned.slice(0, 2).toUpperCase();
};

export type IdenticonProps = {
  seed: string;
  name: string;
  size?: number;
  className?: string;
};

export default function Identicon({
  seed,
  name,
  size = 36,
  className,
}: IdenticonProps) {
  const h = seedHash(seed || name);
  const hue1 = h % 360;
  const hue2 = (hue1 + 47) % 360;
  const gradient = `linear-gradient(135deg, hsl(${hue1} 70% 55%) 0%, hsl(${hue2} 70% 38%) 100%)`;
  const fontSize = Math.max(10, Math.round(size * 0.42));

  return (
    <div
      role="img"
      aria-label={`${name} avatar`}
      className={className}
      style={{
        width: size,
        height: size,
        borderRadius: 8,
        background: gradient,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#0a0a0f",
        fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace",
        fontSize,
        fontWeight: 700,
        letterSpacing: -0.5,
        boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.18)",
        flexShrink: 0,
      }}
    >
      {monogram(name)}
    </div>
  );
}
