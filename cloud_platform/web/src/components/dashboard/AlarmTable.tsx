import { useNavigate } from 'react-router-dom';
import { Flame, Cloud, BotOff, ChevronRight, Image } from 'lucide-react';
import type { Alarm, AlarmType } from '../../types';

interface AlarmTableProps {
  alarms: Alarm[];
  total: number;
  page: number;
  size: number;
  onPageChange: (page: number) => void;
  selectedId: number | null;
  onSelect: (alarm: Alarm) => void;
}

const typeConfig: Record<AlarmType, { label: string; badge: string; Icon: typeof Flame }> = {
  confirmed_fire: { label: '\u786e\u8ba4\u660e\u706b', badge: 'badge-fire', Icon: Flame },
  suspected_smoke: { label: '\u7591\u4f3c\u70df\u96fe', badge: 'badge-smoke', Icon: Cloud },
  ai_unavailable: { label: 'AI \u5931\u6548', badge: 'badge-unavailable', Icon: BotOff },
};

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false,
    });
  } catch {
    return iso;
  }
}

export default function AlarmTable({
  alarms, total, page, size, onPageChange, selectedId, onSelect,
}: AlarmTableProps) {
  const navigate = useNavigate();
  const totalPages = Math.max(1, Math.ceil(total / size));

  const renderPagination = () => {
    const pages: (number | string)[] = [];
    for (let i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || (i >= page - 1 && i <= page + 1)) {
        pages.push(i);
      } else if (pages[pages.length - 1] !== '...') {
        pages.push('...');
      }
    }
    return pages;
  };

  return (
    <div className="panel overflow-hidden">
      <div className="px-4 py-3 border-b border-line flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold text-text">{'\u544a\u8b66\u5217\u8868'}</h3>
          <p className="text-[12px] text-muted-2">{'\u6309\u53d1\u751f\u65f6\u95f4\u5012\u5e8f'}</p>
        </div>
        <span className="text-[11px] px-2.5 py-1 rounded-full bg-panel-2 text-muted">
          {'\u5171'} {total} {'\u6761'}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-muted-2 text-[12px] border-b border-line-soft">
              <th className="text-left px-4 py-2.5 font-medium">{'\u53d1\u751f\u65f6\u95f4'}</th>
              <th className="text-left px-4 py-2.5 font-medium">{'\u7c7b\u578b'}</th>
              <th className="text-left px-4 py-2.5 font-medium">{'\u8f66\u8f86'}</th>
              <th className="text-left px-4 py-2.5 font-medium min-w-[200px]">AI {'\u539f\u56e0'}</th>
              <th className="text-left px-4 py-2.5 font-medium w-[100px]">{'\u7f6e\u4fe1\u5ea6'}</th>
              <th className="text-left px-4 py-2.5 font-medium w-[70px]">{'\u8bc1\u636e'}</th>
              <th className="text-left px-4 py-2.5 font-medium w-[70px]">{'\u64cd\u4f5c'}</th>
            </tr>
          </thead>
          <tbody>
            {alarms.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-muted">
                  <Image className="w-8 h-8 mx-auto mb-2 text-muted-2" />
                  <p>{'\u6682\u65e0\u544a\u8b66\u6570\u636e'}</p>
                  <p className="text-[12px] text-muted-2 mt-1">{'\u8c03\u6574\u7b5b\u9009\u6761\u4ef6\u540e\u91cd\u65b0\u67e5\u8be2'}</p>
                </td>
              </tr>
            ) : (
              alarms.map(alarm => {
                const cfg = typeConfig[alarm.alarm_type];
                const TypeIcon = cfg.Icon;
                const isSelected = alarm.id === selectedId;
                return (
                  <tr
                    key={alarm.id}
                    onClick={() => onSelect(alarm)}
                    className={`border-b border-line-soft cursor-pointer transition-colors hover:bg-panel-2/60 ${
                      isSelected ? 'bg-accent/5 border-l-2 border-l-accent' : ''
                    }`}
                  >
                    <td className="px-4 py-3 text-text whitespace-nowrap">
                      {formatTime(alarm.occurred_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${cfg.badge}`}>
                        <TypeIcon className="w-3 h-3" />
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted">{alarm.car_id}</td>
                    <td className="px-4 py-3 text-muted truncate max-w-[260px]">
                      {alarm.reason ?? '\u2014'}
                    </td>
                    <td className="px-4 py-3">
                      {alarm.confidence != null ? (
                        <div>
                          <div className="confidence-bar w-[80px]">
                            <div className="confidence-bar-fill" style={{ width: `${Math.round(alarm.confidence * 100)}%` }} />
                          </div>
                          <span className="text-[11px] text-muted mt-0.5">
                            {Math.round(alarm.confidence * 100)}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-muted-2 text-[12px]">N/A</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="w-[50px] h-[36px] rounded evidence-placeholder text-[10px]">
                        {alarm.evidence_url ? (
                          <img src={alarm.evidence_url} alt="evidence" className="w-full h-full object-cover rounded" />
                        ) : (
                          <Image className="w-4 h-4 text-muted-2" />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={e => { e.stopPropagation(); navigate(`/alarm/${alarm.id}`); }}
                        className="text-accent text-[12px] font-medium hover:underline flex items-center gap-0.5"
                      >
                        {'\u67e5\u770b'} <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="px-4 py-3 border-t border-line flex items-center justify-center gap-1">
          <button
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="px-3 py-1 text-[12px] text-muted hover:text-text disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {'\u4e0a\u4e00\u9875'}
          </button>
          {renderPagination().map((p, i) =>
            typeof p === 'number' ? (
              <button
                key={i}
                onClick={() => onPageChange(p)}
                className={`w-7 h-7 rounded text-[12px] font-medium ${
                  p === page ? 'bg-accent text-surface' : 'text-muted hover:text-text hover:bg-panel-2'
                }`}
              >
                {p}
              </button>
            ) : (
              <span key={i} className="px-1 text-muted-2">...</span>
            ),
          )}
          <button
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1 text-[12px] text-muted hover:text-text disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {'\u4e0b\u4e00\u9875'}
          </button>
        </div>
      )}
    </div>
  );
}
