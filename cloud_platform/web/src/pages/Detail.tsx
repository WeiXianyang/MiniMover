import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Download, Flame, Cloud, BotOff, Database, Image } from 'lucide-react';
import TopBar from '../components/layout/TopBar';
import { fetchAlarmDetail } from '../api';
import type { Alarm, AlarmType } from '../types';

const typeConfig: Record<AlarmType, { label: string; badge: string; Icon: typeof Flame }> = {
  confirmed_fire: { label: '确认明火', badge: 'badge-fire', Icon: Flame },
  suspected_smoke: { label: '疑似烟雾', badge: 'badge-smoke', Icon: Cloud },
  ai_unavailable: { label: 'AI 失效', badge: 'badge-unavailable', Icon: BotOff },
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

export default function Detail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [alarm, setAlarm] = useState<Alarm | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchAlarmDetail(Number(id))
      .then((data) => {
        setAlarm(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div>
        <TopBar title="告警详情" subtitle="加载中..." />
        <div className="panel p-12 text-center text-muted">
          <p>加载中...</p>
        </div>
      </div>
    );
  }

  if (error || !alarm) {
    return (
      <div>
        <TopBar title="告警详情" subtitle="错误">
          <button className="ghost-btn" onClick={() => navigate('/')}>
            <ArrowLeft className="w-4 h-4" />
            返回列表
          </button>
        </TopBar>
        <div className="panel p-12 text-center text-danger">
          <p>{error ?? '未找到该告警记录'}</p>
        </div>
      </div>
    );
  }

  const cfg = typeConfig[alarm.alarm_type];
  const TypeIcon = cfg.Icon;
  const pct = alarm.confidence != null ? Math.round(alarm.confidence * 100) : null;
  const classes = alarm.detection_classes?.split(',').filter(Boolean) ?? [];
  const evidenceClass = !alarm.evidence_url
    ? alarm.alarm_type === 'confirmed_fire'
      ? 'evidence-fire'
      : alarm.alarm_type === 'suspected_smoke'
        ? 'evidence-smoke'
        : 'evidence-empty'
    : '';

  return (
    <div>
      <TopBar title="告警详情" subtitle={alarm.event_id}>
        <button className="ghost-btn" onClick={() => navigate('/')}>
          <ArrowLeft className="w-4 h-4" />
          返回列表
        </button>
        {alarm.evidence_url && (
          <a href={alarm.evidence_url} target="_blank" rel="noopener noreferrer" className="ghost-btn">
            <Download className="w-4 h-4" />
            下载证据
          </a>
        )}
      </TopBar>

      <div className="grid grid-cols-[1fr_320px] gap-5 max-xl:grid-cols-1">
        <div className="space-y-5">
          {/* Evidence */}
          <div className={`panel overflow-hidden ${evidenceClass}`}>
            <div className="min-h-[430px] relative flex items-center justify-center">
              {alarm.evidence_url ? (
                <img
                  src={alarm.evidence_url}
                  alt="evidence"
                  className="w-full h-full object-contain max-h-[500px] cursor-pointer"
                  onClick={() => window.open(alarm.evidence_url!, '_blank')}
                />
              ) : (
                <div className="text-center text-muted-2">
                  <Image className="w-12 h-12 mx-auto mb-2" />
                  <p className="text-[13px]">暂无证据图片</p>
                </div>
              )}
              {alarm.evidence_url && (
                <div className="absolute bottom-3 left-3 text-[11px] text-text/70 bg-surface/60 px-2 py-1 rounded font-mono max-w-[90%] truncate">
                  {alarm.evidence_url}
                </div>
              )}
            </div>
          </div>

          {/* AI Review */}
          <div className="panel p-5">
            <div className="mb-4">
              <h3 className="text-[15px] font-semibold text-text">AI 复核结果</h3>
              <p className="text-[12px] text-muted-2">云端模型对本地检测结果的二次判断</p>
            </div>
            <div className="flex items-center gap-2 mb-3">
              <span className={`badge ${cfg.badge}`}>
                <TypeIcon className="w-3.5 h-3.5" />
                {cfg.label}
              </span>
            </div>
            <p className="text-[14px] text-text leading-relaxed mb-4">
              {alarm.reason ?? '—'}
            </p>
            <div className="grid grid-cols-2 gap-4">
              {pct !== null && (
                <div className="flex items-center gap-4">
                  <div
                    className="confidence-ring flex-shrink-0"
                    style={{ '--pct': pct } as React.CSSProperties}
                  >
                    <span>{pct}%</span>
                  </div>
                  <div>
                    <p className="text-[13px] text-text font-medium">AI 置信度</p>
                    <p className="text-[11px] text-muted mt-0.5">confidence = {alarm.confidence}</p>
                    {alarm.max_confidence != null && (
                      <p className="text-[11px] text-muted">max = {alarm.max_confidence}</p>
                    )}
                  </div>
                </div>
              )}
              <div>
                <span className="text-[12px] text-muted block mb-1.5">标签</span>
                <div className="flex gap-1.5 flex-wrap">
                  {classes.map((c) => (
                    <span key={c} className="tag tag-cyan">{c}</span>
                  ))}
                  <span className={`tag ${alarm.local_detection_gone ? 'tag-cyan' : 'tag-muted'}`}>
                    local_detection_gone: {String(alarm.local_detection_gone)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Raw Payload */}
          {alarm.raw_payload && (
            <details className="panel" open>
              <summary className="px-5 py-3 cursor-pointer flex items-center gap-2 text-[13px] text-muted hover:text-text transition-colors">
                <Database className="w-4 h-4" />
                raw_payload
              </summary>
              <pre className="px-5 pb-4 text-[12px] text-muted font-mono overflow-x-auto leading-relaxed">
                {JSON.stringify(alarm.raw_payload, null, 2)}
              </pre>
            </details>
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-5">
          <div className="panel p-5">
            <h3 className="text-[15px] font-semibold text-text mb-4">基本信息</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-start">
                <span className="text-[12px] text-muted">事件 ID</span>
                <span className="text-[12px] text-text font-mono text-right max-w-[180px] truncate" title={alarm.event_id}>
                  {alarm.event_id}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[12px] text-muted">车辆</span>
                <span className="text-[13px] text-text">{alarm.car_id}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[12px] text-muted">告警类型</span>
                <span className={`badge ${cfg.badge}`}>
                  <TypeIcon className="w-3 h-3" />
                  {cfg.label}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[12px] text-muted">发生时间</span>
                <span className="text-[12px] text-text">{formatTime(alarm.occurred_at)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[12px] text-muted">接收时间</span>
                <span className="text-[12px] text-text">{formatTime(alarm.received_at)}</span>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="panel p-5">
            <h3 className="text-[15px] font-semibold text-text mb-4">处理状态</h3>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="timeline-dot timeline-dot-done mt-1" />
                <div>
                  <p className="text-[13px] text-text font-medium">本地检测</p>
                  <p className="text-[12px] text-muted">
                    {classes.length > 0 ? `YOLO 命中 ${classes.join(' / ')}` : 'YOLO 检测完成'}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="timeline-dot timeline-dot-done mt-1" />
                <div>
                  <p className="text-[13px] text-text font-medium">云端入库</p>
                  <p className="text-[12px] text-muted">
                    {alarm.received_at && alarm.occurred_at
                      ? `延迟 ${((new Date(alarm.received_at).getTime() - new Date(alarm.occurred_at).getTime()) / 1000).toFixed(1)}s`
                      : '已入库'}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="timeline-dot timeline-dot-active mt-1" />
                <div>
                  <p className="text-[13px] text-text font-medium">AI 复核</p>
                  <p className="text-[12px] text-muted">{cfg.label}</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="timeline-dot timeline-dot-pending mt-1" />
                <div>
                  <p className="text-[13px] text-text font-medium">人工处理</p>
                  <p className="text-[12px] text-muted-2">等待值守确认</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
