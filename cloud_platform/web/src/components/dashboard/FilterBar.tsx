import { Search } from 'lucide-react';
import type { AlarmType, FilterParams } from '../../types';

interface FilterBarProps {
  filters: FilterParams;
  onChange: (filters: FilterParams) => void;
  onSearch: () => void;
}

export default function FilterBar({ filters, onChange, onSearch }: FilterBarProps) {
  const update = (key: keyof FilterParams, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <div className="panel p-3 mb-5 flex items-center gap-3 flex-wrap max-md:flex-col max-md:items-stretch">
      {/* Time range */}
      <select
        value={filters.from ? 'custom' : '7d'}
        onChange={e => {
          const v = e.target.value;
          if (v === '24h') {
            const from = new Date();
            from.setDate(from.getDate() - 1);
            onChange({ ...filters, from: from.toISOString().slice(0, 19), to: undefined });
          } else if (v === '7d') {
            const from = new Date();
            from.setDate(from.getDate() - 7);
            onChange({ ...filters, from: from.toISOString().slice(0, 19), to: undefined });
          } else if (v === '30d') {
            const from = new Date();
            from.setDate(from.getDate() - 30);
            onChange({ ...filters, from: from.toISOString().slice(0, 19), to: undefined });
          }
        }}
        className="flex-1 min-w-[140px] bg-panel-2 border border-line rounded-lg px-3 py-2 text-[13px] text-text outline-none focus:border-accent"
      >
        <option value="24h">最近 24 小时</option>
        <option value="7d">最近 7 天</option>
        <option value="30d">最近 30 天</option>
      </select>

      {/* Alarm type */}
      <select
        value={filters.type || ''}
        onChange={e => update('type', e.target.value)}
        className="flex-1 min-w-[140px] bg-panel-2 border border-line rounded-lg px-3 py-2 text-[13px] text-text outline-none focus:border-accent"
      >
        <option value="">全部类型</option>
        <option value="confirmed_fire">确认明火</option>
        <option value="suspected_smoke">疑似烟雾</option>
        <option value="ai_unavailable">AI 失效</option>
      </select>

      {/* Vehicle */}
      <select
        value={filters.car_id || ''}
        onChange={e => update('car_id', e.target.value)}
        className="flex-1 min-w-[140px] bg-panel-2 border border-line rounded-lg px-3 py-2 text-[13px] text-text outline-none focus:border-accent"
      >
        <option value="">全部车辆</option>
        <option value="car-01">car-01</option>
        <option value="car-02">car-02</option>
        <option value="car-03">car-03</option>
      </select>

      {/* Search */}
      <input
        type="search"
        placeholder="event_id / reason"
        value={filters.keyword || ''}
        onChange={e => update('keyword', e.target.value)}
        onKeyDown={e => e.key === 'Enter' && onSearch()}
        className="flex-1 min-w-[180px] bg-panel-2 border border-line rounded-lg px-3 py-2 text-[13px] text-text outline-none placeholder:text-muted-2 focus:border-accent"
      />

      {/* Query button */}
      <button className="primary-btn" onClick={onSearch}>
        <Search className="w-4 h-4" />
        查询
      </button>
    </div>
  );
}
