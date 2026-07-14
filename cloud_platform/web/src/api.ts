import type { Alarm, AlarmListResponse, ApiResponse, FilterParams } from './types';
import { MOCK_ALARMS } from './mock';

const API_BASE = '/api/v1';

let useMock = false;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  };

  const token = import.meta.env.VITE_API_TOKEN;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const json: ApiResponse<T> = await res.json();
  if (json.code !== 0) throw new Error(json.msg);
  return json.data;
}

function getDateRange(days: number): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - days);
  return {
    from: from.toISOString().slice(0, 19),
    to: to.toISOString().slice(0, 19),
  };
}

export async function fetchAlarms(params: FilterParams = {}): Promise<AlarmListResponse> {
  if (useMock) {
    return getMockAlarmList(params);
  }

  try {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', String(params.page));
    if (params.size) searchParams.set('size', String(params.size));
    if (params.type) searchParams.set('type', params.type);
    if (params.car_id) searchParams.set('car_id', params.car_id);
    if (params.from) searchParams.set('from', params.from);
    if (params.to) searchParams.set('to', params.to);

    const qs = searchParams.toString();
    return await request<AlarmListResponse>(`/fire-alarms${qs ? `?${qs}` : ''}`);
  } catch {
    useMock = true;
    return getMockAlarmList(params);
  }
}

export async function fetchAlarmDetail(id: number): Promise<Alarm> {
  if (useMock) {
    const item = MOCK_ALARMS.find(a => a.id === id) || MOCK_ALARMS[0];
    return { ...item, raw_payload: getMockPayload(item) };
  }

  try {
    return await request<Alarm>(`/fire-alarms/${id}`);
  } catch {
    useMock = true;
    const item = MOCK_ALARMS.find(a => a.id === id) || MOCK_ALARMS[0];
    return { ...item, raw_payload: getMockPayload(item) };
  }
}

export async function healthCheck(): Promise<{ code: number; msg: string; db: string }> {
  try {
    const res = await fetch('/healthz');
    return await res.json();
  } catch {
    useMock = true;
    return { code: 0, msg: 'ok (mock)', db: 'up' };
  }
}

export function isUsingMock(): boolean {
  return useMock;
}

/* ── Mock helpers ── */

function getMockPayload(alarm: Alarm): Record<string, unknown> {
  return {
    event_id: alarm.event_id,
    alarm_type: alarm.alarm_type,
    occurred_at: alarm.occurred_at,
    reason: alarm.reason,
    confidence: alarm.confidence,
    evidence_url: alarm.evidence_url,
    detection_classes: alarm.detection_classes?.split(',') ?? [],
    max_confidence: alarm.max_confidence,
    local_detection_gone: alarm.local_detection_gone,
    car_id: alarm.car_id,
  };
}

function getMockAlarmList(params: FilterParams): AlarmListResponse {
  let items = [...MOCK_ALARMS];

  if (params.type) {
    items = items.filter(a => a.alarm_type === params.type);
  }
  if (params.car_id) {
    items = items.filter(a => a.car_id === params.car_id);
  }
  if (params.keyword) {
    const kw = params.keyword.toLowerCase();
    items = items.filter(
      a =>
        a.event_id.toLowerCase().includes(kw) ||
        (a.reason ?? '').toLowerCase().includes(kw),
    );
  }

  const total = items.length;
  const page = params.page ?? 1;
  const size = params.size ?? 20;
  const start = (page - 1) * size;
  items = items.slice(start, start + size);

  return { total, page, size, items };
}
