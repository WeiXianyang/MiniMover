import { Car } from 'lucide-react';
import type { VehicleStatusItem } from '../../types';

interface VehicleStatusProps {
  vehicles: VehicleStatusItem[];
  loading?: boolean;
}

function formatLastSeen(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 5) return '刚刚';
  if (seconds < 60) return `${seconds}s 前`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m 前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h 前`;
  const days = Math.floor(hours / 24);
  return `${days}d 前`;
}

function getStatus(lastSeen: string): 'online' | 'offline' {
  const diff = Date.now() - new Date(lastSeen).getTime();
  return diff < 120_000 ? 'online' : 'offline'; // 2 分钟内视为在线
}

export default function VehicleStatus({ vehicles, loading }: VehicleStatusProps) {
  if (loading) {
    return (
      <div className="panel p-4">
        <div className="mb-3">
          <h3 className="text-[15px] font-semibold text-text">车辆状态</h3>
          <p className="text-[12px] text-muted-2">最近一次上报时间</p>
        </div>
        <div className="space-y-3 flex items-center justify-center h-[140px] text-muted text-[13px]">
          加载中...
        </div>
      </div>
    );
  }

  if (vehicles.length === 0) {
    return (
      <div className="panel p-4">
        <div className="mb-3">
          <h3 className="text-[15px] font-semibold text-text">车辆状态</h3>
          <p className="text-[12px] text-muted-2">最近一次上报时间</p>
        </div>
        <div className="space-y-3 flex items-center justify-center h-[140px] text-muted text-[13px]">
          暂无数据
        </div>
      </div>
    );
  }

  return (
    <div className="panel p-4">
      <div className="mb-3">
        <h3 className="text-[15px] font-semibold text-text">车辆状态</h3>
        <p className="text-[12px] text-muted-2">最近一次上报时间</p>
      </div>

      <div className="space-y-3">
        {vehicles.map(v => {
          const status = getStatus(v.last_seen);
          return (
            <div key={v.car_id} className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-panel-2 flex items-center justify-center">
                <Car className="w-4 h-4 text-muted" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] text-text font-medium">{v.car_id}</p>
                <p className={`text-[12px] ${status === 'online' ? 'text-success' : 'text-danger'}`}>
                  {status === 'online' ? '在线' : '离线'} · {formatLastSeen(v.last_seen)}
                </p>
              </div>
              <div
                className={`w-2 h-2 rounded-full ${
                  status === 'online' ? 'bg-success' : 'bg-danger'
                }`}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
