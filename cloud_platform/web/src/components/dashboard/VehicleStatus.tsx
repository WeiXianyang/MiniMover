import { Car } from 'lucide-react';
import { MOCK_VEHICLES } from '../../mock';

export default function VehicleStatus() {
  const vehicles = MOCK_VEHICLES;

  return (
    <div className="panel p-4">
      <div className="mb-3">
        <h3 className="text-[15px] font-semibold text-text">车辆状态</h3>
        <p className="text-[12px] text-muted-2">最近一次上报时间</p>
      </div>

      <div className="space-y-3">
        {vehicles.map(v => (
          <div key={v.car_id} className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-panel-2 flex items-center justify-center">
              <Car className="w-4 h-4 text-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] text-text font-medium">{v.car_id}</p>
              <p className={`text-[12px] ${v.status === 'online' ? 'text-success' : 'text-danger'}`}>
                {v.status === 'online' ? '在线' : '超时'} · {v.lastSeen}
              </p>
            </div>
            <div
              className={`w-2 h-2 rounded-full ${
                v.status === 'online' ? 'bg-success' : 'bg-danger'
              }`}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
