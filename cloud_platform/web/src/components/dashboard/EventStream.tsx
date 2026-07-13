import type { Alarm, AlarmType } from '../../types';

interface EventStreamProps {
  alarms: Alarm[];
}

const dotColor: Record<AlarmType, string> = {
  confirmed_fire: 'bg-danger',
  suspected_smoke: 'bg-accent',
  ai_unavailable: 'bg-warn',
};

function shortTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  } catch {
    return '';
  }
}

const typeLabel: Record<AlarmType, string> = {
  confirmed_fire: '确认明火',
  suspected_smoke: '疑似烟雾',
  ai_unavailable: 'AI 失效',
};

export default function EventStream({ alarms }: EventStreamProps) {
  const recent = alarms.slice(0, 10);

  return (
    <div className="panel p-4">
      <div className="mb-3">
        <h3 className="text-[15px] font-semibold text-text">最近告警</h3>
        <p className="text-[12px] text-muted-2">轮询刷新，保留最新 10 条</p>
      </div>

      <div className="space-y-3">
        {recent.length === 0 ? (
          <p className="text-[13px] text-muted text-center py-6">暂无数据</p>
        ) : (
          recent.map(alarm => (
            <div key={alarm.id} className="flex items-start gap-2.5">
              <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${dotColor[alarm.alarm_type]}`} />
              <div className="min-w-0">
                <p className="text-[13px] text-text font-medium">
                  {shortTime(alarm.occurred_at)}
                  <span className="text-muted font-normal ml-1.5">
                    {alarm.car_id} {typeLabel[alarm.alarm_type]}
                  </span>
                </p>
                {alarm.reason && (
                  <p className="text-[12px] text-muted-2 truncate mt-0.5">{alarm.reason}</p>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
