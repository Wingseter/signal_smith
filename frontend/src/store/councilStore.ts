import { create } from 'zustand';

interface CouncilTrigger {
  id: string;
  symbol: string;
  company_name: string;
  news_title: string;
  news_score: number;
  timestamp: string;
  type: 'news_trigger' | 'meeting_started' | 'signal_created' | 'signal_approved';
}

interface PendingSignal {
  id: string;
  symbol: string;
  company_name: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  allocation_percent: number;
  created_at: string;
}

interface CouncilState {
  // 트리거 알림
  triggers: CouncilTrigger[];
  unreadCount: number;

  // 대기 시그널
  pendingSignals: PendingSignal[];

  // Council 상태
  isCouncilRunning: boolean;
  activeMeetingId: string | null;

  // 모달/알림 상태
  showTriggerModal: boolean;
  latestTrigger: CouncilTrigger | null;

  // Actions
  addTrigger: (trigger: CouncilTrigger) => void;
  clearTriggers: () => void;
  markAsRead: () => void;

  setPendingSignals: (signals: PendingSignal[]) => void;
  addPendingSignal: (signal: PendingSignal) => void;
  removePendingSignal: (signalId: string) => void;

  setCouncilRunning: (running: boolean) => void;
  setActiveMeeting: (meetingId: string | null) => void;

  setShowTriggerModal: (show: boolean) => void;
  dismissLatestTrigger: () => void;
}

export const useCouncilStore = create<CouncilState>((set) => ({
  triggers: [],
  unreadCount: 0,
  pendingSignals: [],
  isCouncilRunning: false,
  activeMeetingId: null,
  showTriggerModal: false,
  latestTrigger: null,

  addTrigger: (trigger) =>
    set((state) => ({
      triggers: [trigger, ...state.triggers].slice(0, 50), // 최대 50개 유지
      unreadCount: state.unreadCount + 1,
      latestTrigger: trigger,
      showTriggerModal: true, // 새 트리거 시 모달 자동 표시
    })),

  clearTriggers: () =>
    set({
      triggers: [],
      unreadCount: 0,
    }),

  markAsRead: () =>
    set({
      unreadCount: 0,
    }),

  setPendingSignals: (signals) =>
    set({
      pendingSignals: signals,
    }),

  addPendingSignal: (signal) =>
    set((state) => ({
      pendingSignals: [signal, ...state.pendingSignals],
    })),

  removePendingSignal: (signalId) =>
    set((state) => ({
      pendingSignals: state.pendingSignals.filter((s) => s.id !== signalId),
    })),

  setCouncilRunning: (running) =>
    set({
      isCouncilRunning: running,
    }),

  setActiveMeeting: (meetingId) =>
    set({
      activeMeetingId: meetingId,
    }),

  setShowTriggerModal: (show) =>
    set({
      showTriggerModal: show,
    }),

  dismissLatestTrigger: () =>
    set({
      showTriggerModal: false,
      latestTrigger: null,
    }),
}));
