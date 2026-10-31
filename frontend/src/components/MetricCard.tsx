import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number | null;
  unit?: string;
  icon?: LucideIcon;
  status?: 'normal' | 'warning' | 'critical' | 'default';
  subtitle?: string;
  trend?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  icon: Icon,
  status = 'default',
  subtitle,
  trend,
}) => {
  let statusBorder = 'border-[#2A313B]';
  let valueColor = 'text-[#E8EDF4]';

  if (status === 'normal') {
    statusBorder = 'border-[#37C98B]/30';
    valueColor = 'text-[#37C98B]';
  } else if (status === 'warning') {
    statusBorder = 'border-[#FFB547]/40';
    valueColor = 'text-[#FFB547]';
  } else if (status === 'critical') {
    statusBorder = 'border-[#FF5C65]/50';
    valueColor = 'text-[#FF5C65]';
  }

  return (
    <div
      className={`bg-[#181D24] p-4 rounded-xl border ${statusBorder} flex flex-col justify-between transition-all duration-200 hover:border-[#3B4452]`}
    >
      <div className="flex items-center justify-between text-[#9BA7B5] mb-2">
        <span className="text-xs uppercase tracking-wider font-semibold">{title}</span>
        {Icon && <Icon className="w-4 h-4 text-[#53B7FF]" />}
      </div>

      <div className="flex items-baseline gap-1.5 my-1">
        <span className={`text-2xl font-bold font-mono ${valueColor}`}>
          {value !== null && value !== undefined ? value : '—'}
        </span>
        {unit && <span className="text-xs font-mono text-[#9BA7B5]">{unit}</span>}
      </div>

      {(subtitle || trend) && (
        <div className="flex items-center justify-between text-xs text-[#9BA7B5] mt-1 pt-2 border-t border-[#2A313B]/50">
          {subtitle && <span>{subtitle}</span>}
          {trend && <span className="font-mono text-[#53B7FF]">{trend}</span>}
        </div>
      )}
    </div>
  );
};
