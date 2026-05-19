/* ═══════════════════════════════════════════════════════════════════════
   MetricCard — displays a single KPI with color coding.
   ═══════════════════════════════════════════════════════════════════════ */

interface MetricCardProps {
  label: string;
  value: string | number;
  colorMode?: 'positive' | 'negative' | 'neutral' | 'auto';
  numericValue?: number;
}

export default function MetricCard({
  label,
  value,
  colorMode = 'auto',
  numericValue,
}: MetricCardProps) {
  let className = 'metric-card__value metric-card__value--neutral';

  if (colorMode === 'auto' && numericValue !== undefined) {
    if (numericValue > 0) className = 'metric-card__value metric-card__value--positive';
    else if (numericValue < 0) className = 'metric-card__value metric-card__value--negative';
  } else if (colorMode === 'positive') {
    className = 'metric-card__value metric-card__value--positive';
  } else if (colorMode === 'negative') {
    className = 'metric-card__value metric-card__value--negative';
  }

  return (
    <div className="metric-card">
      <div className="metric-card__label">{label}</div>
      <div className={className}>{value}</div>
    </div>
  );
}
