import { RefreshCw } from 'lucide-react';

interface TopBarProps {
  title: string;
  subtitle: string;
  autoRefresh?: boolean;
  onAutoRefreshChange?: (v: boolean) => void;
  onRefresh?: () => void;
  children?: React.ReactNode;
}

export default function TopBar({
  title,
  subtitle,
  autoRefresh,
  onAutoRefreshChange,
  onRefresh,
  children,
}: TopBarProps) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h2 className="text-[24px] font-semibold leading-tight text-text">{title}</h2>
        <p className="text-[13px] text-muted mt-1">{subtitle}</p>
      </div>
      <div className="flex items-center gap-3">
        {onRefresh && (
          <button className="ghost-btn" onClick={onRefresh}>
            <RefreshCw className="w-4 h-4" />
            刷新
          </button>
        )}
        {autoRefresh !== undefined && onAutoRefreshChange && (
          <label className="flex items-center gap-2 text-[13px] text-muted cursor-pointer">
            <div
              className={`toggle ${autoRefresh ? 'active' : ''}`}
              onClick={() => onAutoRefreshChange(!autoRefresh)}
            />
            30s 自动刷新
          </label>
        )}
        {children}
      </div>
    </div>
  );
}
