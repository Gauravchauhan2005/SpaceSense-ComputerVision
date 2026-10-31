import React from 'react';

interface StatusBadgeProps {
  status: 'connected' | 'disconnected' | 'connecting' | 'error' | 'NORMAL' | 'WARNING' | 'CRITICAL' | string;
  label?: string;
  pulse?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, pulse = false }) => {
  let bg = 'bg-[#2A313B]/50';
  let text = 'text-[#9BA7B5]';
  let dot = 'bg-[#9BA7B5]';
  let displayLabel = label || status;

  switch (status) {
    case 'connected':
    case 'NORMAL':
      bg = 'bg-[#37C98B]/10 border-[#37C98B]/30';
      text = 'text-[#37C98B]';
      dot = 'bg-[#37C98B]';
      break;
    case 'connecting':
    case 'WARNING':
      bg = 'bg-[#FFB547]/10 border-[#FFB547]/30';
      text = 'text-[#FFB547]';
      dot = 'bg-[#FFB547]';
      break;
    case 'disconnected':
    case 'CRITICAL':
    case 'error':
      bg = 'bg-[#FF5C65]/10 border-[#FF5C65]/30';
      text = 'text-[#FF5C65]';
      dot = 'bg-[#FF5C65]';
      break;
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${bg} ${text}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${dot} ${pulse ? 'animate-ping' : ''}`}
      />
      {displayLabel}
    </span>
  );
};
