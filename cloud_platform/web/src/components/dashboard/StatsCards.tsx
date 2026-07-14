import { useRef, useEffect } from 'react';
import { TriangleAlert, Flame, Cloud, BotOff } from 'lucide-react';
import type { Alarm } from '../../types';

interface StatsCardsProps {
  alarms: Alarm[];
  pulse?: boolean;
}

export default function StatsCards({ alarms, pulse }: StatsCardsProps) {
  const today = new Date().toISOString().slice(0, 10);
  const todayAlarms = alarms.filter(a => a.occurred_at.slice(0, 10) === today);
  const total = alarms.length;
  const fire = alarms.filter(a => a.alarm_type === 'confirmed_fire').length;
  const smoke = alarms.filter(a => a.alarm_type === 'suspected_smoke').length;
  const unavailable = alarms.filter(a => a.alarm_type === 'ai_unavailable').length;

  const numRefs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    if (pulse) {
      numRefs.current.forEach(el => {
        if (el) {
          el.classList.remove('stat-pulse');
          void el.offsetWidth;
          el.classList.add('stat-pulse');
        }
      });
    }
  }, [pulse]);

  const cards = [
    {
      icon: TriangleAlert,
      value: total,
      label: '今日告警',
      tag: `${todayAlarms.length} 条今日`,
      iconBg: 'bg-accent/15',
      iconColor: 'text-accent',
      danger: false,
    },
    {
      icon: Flame,
      value: fire,
      label: '确认明火',
      tag: '高优先',
      iconBg: 'bg-danger/15',
      iconColor: 'text-danger',
      danger: true,
    },
    {
      icon: Cloud,
      value: smoke,
      label: '疑似烟雾',
      tag: '待复核',
      iconBg: 'bg-cyan/15',
      iconColor: 'text-cyan',
      danger: false,
    },
    {
      icon: BotOff,
      value: unavailable,
      label: 'AI 失效',
      tag: '需排查',
      iconBg: 'bg-warn/15',
      iconColor: 'text-warn',
      danger: false,
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-4 mb-5 max-xl:grid-cols-2 max-md:grid-cols-1">
      {cards.map((card, i) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className={`panel p-4 ${card.danger ? 'border-danger/40 bg-[#1a1015]' : ''}`}
          >
            <div className="flex items-start justify-between">
              <div className={`w-9 h-9 rounded-lg ${card.iconBg} flex items-center justify-center`}>
                <Icon className={`w-[18px] h-[18px] ${card.iconColor}`} />
              </div>
              <span className={`text-[11px] px-2 py-0.5 rounded-full ${
                card.danger ? 'bg-danger/15 text-danger' :
                card.iconColor === 'text-cyan' ? 'bg-cyan/15 text-cyan' :
                card.iconColor === 'text-warn' ? 'bg-warn/15 text-warn' :
                'bg-accent/15 text-accent'
              }`}>
                {card.tag}
              </span>
            </div>
            <div className="mt-3">
              <span
                ref={el => { numRefs.current[i] = el; }}
                className="text-[28px] font-bold text-text"
              >
                {card.value}
              </span>
              <p className="text-[13px] text-muted mt-0.5">{card.label}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
