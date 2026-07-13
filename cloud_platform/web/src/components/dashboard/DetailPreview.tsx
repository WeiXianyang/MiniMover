import { useNavigate } from 'react-router-dom';
import { Eye, Flame, Cloud, BotOff, Image } from 'lucide-react';
import type { Alarm, AlarmType } from '../../types';

interface DetailPreviewProps {
  alarm: Alarm | null;
}

const typeConfig: Record<AlarmType, { label: string; badge: string; Icon: typeof Flame }> = {
  confirmed_fire: { label: '确认明火', badge: 'badge-fire', Icon: Flame },
  suspected_smoke: { label: '疑似烟雾', badge: 'badge-smoke', Icon: Cloud },
  ai_unavailable: { label: 'AI 失效', badge: 'badge-unavailable', Icon: BotOff },
};

function getEvidenceClass(alarm: Alarm): string {
  if (!alarm.evidence_url) {
    if (alarm.alarm_type === 'confirmed_fire') return 'evidence-fire';
    if (alarm.alarm_type === 'suspected_smoke') return 'evidence-smoke';
    return 'evidence-empty';
  }
  return '';
}

export default function DetailPreview({ alarm }: DetailPreviewProps) {
  const navigate = useNavigate();

  if (!alarm) {
    return (
      <div className="panel p-5 sticky top-6">
        <div className="text-center py-8 text-muted">
          <Eye className="w-6 h-6 mx-auto mb-2 text-muted-2" />
          <p className="text-[13px]">点击表格行预览事件</p>
        </div>
      </div>
    );
  }

  const cfg = typeConfig[alarm.alarm_type];
  const TypeIcon = cfg.Icon;
  const pct = alarm.confidence != null ? Math.round(alarm.confidence * 100) : null;
  const classes = alarm.detection_classes?.split(',').filter(Boolean) ?? [];
  const evidenceClass = getEvidenceClass(alarm);

  return (
    <div className="panel p-0 sticky top-6 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-line flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold text-text">事件预览</h3>
          <p className="text-[11px] text-muted-2 font-mono truncate max-w-[200px]">{alarm.event_id}</p>
        </div>
        <button
          onClick={() => navigate(`/alarm/${alarm.id}`)}
          className="text-accent hover:text-accent/80 transition-colors"
        >
          <Eye className="w-4 h-4" />
        </button>
      </div>

      {/* Evidence Image */}
      <div className={`h-[190px] ${evidenceClass} relative`}>
        {alarm.evidence_url ? (
          <img src={alarm.evidence_url} alt="evidence" className="w-full h-full object-cover" />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-2">
            <Image className="w-8 h-8 mb-1" />
            <span className="text-[11px]">暂无证据图片</span>
          </div>
        )}
        <div className="absolute bottom-2 left-3 text-[11px] text-text/70 bg-surface/60 px-2 py-0.5 rounded">
          {alarm.car_id}
        </div>
      </div>

      {/* Info */}
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-muted">告警类型</span>
          <span className={`badge ${cfg.badge}`}>
            <TypeIcon className="w-3 h-3" />
            {cfg.label}
          </span>
        </div>

        <div>
          <span className="text-[12px] text-muted block mb-1">AI 复核</span>
          <p className="text-[13px] text-text leading-relaxed">{alarm.reason ?? '—'}</p>
        </div>

        {classes.length > 0 && (
          <div>
            <span className="text-[12px] text-muted block mb-1.5">命中类别</span>
            <div className="flex gap-1.5 flex-wrap">
              {classes.map(c => (
                <span key={c} className="tag tag-cyan">{c}</span>
              ))}
              <span className={`tag ${alarm.local_detection_gone ? 'tag-cyan' : 'tag-muted'}`}>
                local_detection_gone: {alarm.local_detection_gone ? 'true' : 'false'}
              </span>
            </div>
          </div>
        )}

        {pct !== null && (
          <div className="pt-3 border-t border-line-soft flex items-center gap-4">
            <div
              className="confidence-ring flex-shrink-0"
              style={{ '--pct': pct } as React.CSSProperties}
            >
              <span>{pct}%</span>
            </div>
            <div>
              <p className="text-[13px] text-text font-medium">AI 置信度</p>
              <p className="text-[11px] text-muted mt-0.5">
                confidence = {alarm.confidence}
                {alarm.max_confidence != null && `, max = ${alarm.max_confidence}`}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
