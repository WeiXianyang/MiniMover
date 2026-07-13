import { useState, useEffect, useCallback, useRef } from 'react';
import TopBar from '../components/layout/TopBar';
import StatsCards from '../components/dashboard/StatsCards';
import FilterBar from '../components/dashboard/FilterBar';
import AlarmTable from '../components/dashboard/AlarmTable';
import DetailPreview from '../components/dashboard/DetailPreview';
import TrendChart from '../components/dashboard/TrendChart';
import EventStream from '../components/dashboard/EventStream';
import VehicleStatus from '../components/dashboard/VehicleStatus';
import { fetchAlarms } from '../api';
import type { Alarm, FilterParams } from '../types';

export default function Overview() {
  const [alarms, setAlarms] = useState<Alarm[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedAlarm, setSelectedAlarm] = useState<Alarm | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pulse, setPulse] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [filters, setFilters] = useState<FilterParams>({
    page: 1,
    size: 20,
  });

  const load = useCallback(async (f: FilterParams) => {
    try {
      setLoading(true);
      const data = await fetchAlarms(f);
      setAlarms(data.items);
      setTotal(data.total);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters);
  }, [filters, load]);

  const intervalRef = useRef<number | null>(null);
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = window.setInterval(() => {
        load(filters);
        setPulse(true);
        setTimeout(() => setPulse(false), 500);
      }, 30000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, filters, load]);

  const handleRefresh = () => {
    load(filters);
    setPulse(true);
    setTimeout(() => setPulse(false), 500);
  };

  const handleSearch = () => {
    setFilters((prev) => ({ ...prev, page: 1 }));
  };

  return (
    <div>
      <TopBar
        title="告警总览"
        subtitle="近 7 天烟火识别结果、车辆来源与证据链路"
        autoRefresh={autoRefresh}
        onAutoRefreshChange={setAutoRefresh}
        onRefresh={handleRefresh}
      />

      <StatsCards alarms={alarms} pulse={pulse} />

      <FilterBar filters={filters} onChange={setFilters} onSearch={handleSearch} />

      {error && (
        <div className="panel p-4 mb-5 border-danger/40 text-danger text-[13px]">
          {error}
        </div>
      )}

      {loading && alarms.length === 0 ? (
        <div className="panel p-12 text-center text-muted">
          <p>加载中...</p>
        </div>
      ) : (
        <div className="grid grid-cols-[1fr_320px] gap-5 mb-5 max-xl:grid-cols-1">
          <AlarmTable
            alarms={alarms}
            total={total}
            page={filters.page ?? 1}
            size={filters.size ?? 20}
            onPageChange={(page) => setFilters((prev) => ({ ...prev, page }))}
            selectedId={selectedAlarm?.id ?? null}
            onSelect={setSelectedAlarm}
          />
          <DetailPreview alarm={selectedAlarm} />
        </div>
      )}

      <div className="grid grid-cols-3 gap-5 max-xl:grid-cols-1">
        <TrendChart />
        <EventStream alarms={alarms} />
        <VehicleStatus />
      </div>
    </div>
  );
}
