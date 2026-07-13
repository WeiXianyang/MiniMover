export type AlarmType = 'confirmed_fire' | 'suspected_smoke' | 'ai_unavailable';

export interface Alarm {
  id: number;
  event_id: string;
  alarm_type: AlarmType;
  occurred_at: string;
  reason: string | null;
  confidence: number | null;
  evidence_url: string | null;
  detection_classes: string | null;
  max_confidence: number | null;
  local_detection_gone: boolean;
  car_id: string;
  received_at: string;
  raw_payload?: Record<string, unknown>;
}

export interface AlarmListResponse {
  total: number;
  page: number;
  size: number;
  items: Alarm[];
}

export interface ApiResponse<T> {
  code: number;
  msg: string;
  data: T;
}

export interface FilterParams {
  type?: AlarmType | '';
  car_id?: string;
  from?: string;
  to?: string;
  page?: number;
  size?: number;
  keyword?: string;
}

export const ALARM_TYPE_MAP: Record<AlarmType, { label: string; color: string; icon: string }> = {
  confirmed_fire: { label: '确认明火', color: 'danger', icon: 'flame' },
  suspected_smoke: { label: '疑似烟雾', color: 'accent', icon: 'cloud-smoke' },
  ai_unavailable: { label: 'AI 失效', color: 'warn', icon: 'bot-off' },
};
