import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../../services/api';

interface NotificationChannel {
  name: string;
  configured: boolean;
  enabled: boolean;
}

interface NotificationSettingsData {
  slack_enabled: boolean;
  telegram_enabled: boolean;
  email_enabled: boolean;
  buy_signals: boolean;
  sell_signals: boolean;
  price_alerts: boolean;
  order_updates: boolean;
  daily_reports: boolean;
  min_signal_strength: number;
}

interface PriceAlert {
  id: number;
  symbol: string;
  price_above: number | null;
  price_below: number | null;
  note: string | null;
  created_at: string;
}

export default function NotificationSettings() {
  const queryClient = useQueryClient();
  const [testChannel, setTestChannel] = useState<string>('');
  const [testMessage, setTestMessage] = useState('테스트 알림입니다.');
  const [newAlert, setNewAlert] = useState({ symbol: '', price_above: '', price_below: '', note: '' });

  // Fetch notification status
  const { data: status } = useQuery({
    queryKey: ['notifications', 'status'],
    queryFn: notificationsApi.getStatus,
  });

  // Fetch settings
  const { data: settings, isLoading: settingsLoading } = useQuery<NotificationSettingsData>({
    queryKey: ['notifications', 'settings'],
    queryFn: notificationsApi.getSettings,
  });

  // Fetch price alerts
  const { data: alerts } = useQuery<PriceAlert[]>({
    queryKey: ['notifications', 'alerts'],
    queryFn: notificationsApi.getAlerts,
  });

  // Update settings mutation
  const updateSettingsMutation = useMutation({
    mutationFn: notificationsApi.updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications', 'settings'] });
    },
  });

  // Test notification mutation
  const testNotificationMutation = useMutation({
    mutationFn: ({ channel, message }: { channel: string; message: string }) =>
      notificationsApi.sendTest(channel, message),
  });

  // Create alert mutation
  const createAlertMutation = useMutation({
    mutationFn: notificationsApi.createAlert,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications', 'alerts'] });
      setNewAlert({ symbol: '', price_above: '', price_below: '', note: '' });
    },
  });

  // Delete alert mutation
  const deleteAlertMutation = useMutation({
    mutationFn: notificationsApi.deleteAlert,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications', 'alerts'] });
    },
  });

  const handleSettingChange = (key: keyof NotificationSettingsData, value: boolean | number) => {
    if (settings) {
      updateSettingsMutation.mutate({ ...settings, [key]: value });
    }
  };

  const handleTestNotification = () => {
    if (testChannel) {
      testNotificationMutation.mutate({ channel: testChannel, message: testMessage });
    }
  };

  const handleCreateAlert = (e: React.FormEvent) => {
    e.preventDefault();
    if (newAlert.symbol && (newAlert.price_above || newAlert.price_below)) {
      createAlertMutation.mutate({
        symbol: newAlert.symbol.toUpperCase(),
        price_above: newAlert.price_above ? parseFloat(newAlert.price_above) : null,
        price_below: newAlert.price_below ? parseFloat(newAlert.price_below) : null,
        note: newAlert.note || null,
      });
    }
  };

  const getChannelIcon = (name: string) => {
    switch (name) {
      case 'slack': return '💬';
      case 'telegram': return '✈️';
      case 'email': return '📧';
      default: return '📢';
    }
  };

  const getChannelLabel = (name: string) => {
    switch (name) {
      case 'slack': return 'Slack';
      case 'telegram': return 'Telegram';
      case 'email': return 'Email';
      default: return name;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">알림 설정</h1>
        <p className="text-sm text-gray-500 mt-1">
          매매 시그널 및 가격 알림을 받을 채널을 설정하세요
        </p>
      </div>

      {/* Notification Channels */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">알림 채널</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {status?.channels?.map((channel: NotificationChannel) => (
            <div
              key={channel.name}
              className={`p-4 rounded-lg border-2 ${
                channel.configured
                  ? 'border-green-200 bg-green-50'
                  : 'border-gray-200 bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">{getChannelIcon(channel.name)}</span>
                  <div>
                    <p className="font-medium">{getChannelLabel(channel.name)}</p>
                    <p className={`text-sm ${channel.configured ? 'text-green-600' : 'text-gray-500'}`}>
                      {channel.configured ? '연동됨' : '미설정'}
                    </p>
                  </div>
                </div>
                {channel.configured && (
                  <span className="w-3 h-3 bg-green-500 rounded-full" />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Notification Preferences */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">알림 유형</h2>
        {settingsLoading ? (
          <div className="text-center py-4 text-gray-500">로딩 중...</div>
        ) : settings ? (
          <div className="space-y-4">
            {[
              { key: 'buy_signals', label: '매수 시그널', desc: 'AI가 생성한 매수 신호 알림' },
              { key: 'sell_signals', label: '매도 시그널', desc: 'AI가 생성한 매도 신호 알림' },
              { key: 'price_alerts', label: '가격 알림', desc: '설정한 가격 도달 시 알림' },
              { key: 'order_updates', label: '주문 알림', desc: '주문 체결/취소 알림' },
              { key: 'daily_reports', label: '일간 리포트', desc: '매일 장 마감 후 일간 리포트' },
            ].map((item) => (
              <div key={item.key} className="flex items-center justify-between py-3 border-b last:border-0">
                <div>
                  <p className="font-medium text-gray-900">{item.label}</p>
                  <p className="text-sm text-gray-500">{item.desc}</p>
                </div>
                <button
                  onClick={() => handleSettingChange(
                    item.key as keyof NotificationSettingsData,
                    !settings[item.key as keyof NotificationSettingsData]
                  )}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    settings[item.key as keyof NotificationSettingsData]
                      ? 'bg-primary-600'
                      : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      settings[item.key as keyof NotificationSettingsData]
                        ? 'translate-x-6'
                        : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            ))}

            {/* Signal Strength Threshold */}
            <div className="py-3">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="font-medium text-gray-900">최소 시그널 강도</p>
                  <p className="text-sm text-gray-500">이 강도 이상의 시그널만 알림</p>
                </div>
                <span className="font-bold text-primary-600">{settings.min_signal_strength}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="10"
                value={settings.min_signal_strength}
                onChange={(e) => handleSettingChange('min_signal_strength', parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0%</span>
                <span>50%</span>
                <span>100%</span>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Test Notification */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">테스트 알림</h2>
        <div className="flex flex-col md:flex-row gap-4">
          <select
            value={testChannel}
            onChange={(e) => setTestChannel(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="">채널 선택</option>
            {status?.channels?.filter((c: NotificationChannel) => c.configured).map((channel: NotificationChannel) => (
              <option key={channel.name} value={channel.name}>
                {getChannelLabel(channel.name)}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={testMessage}
            onChange={(e) => setTestMessage(e.target.value)}
            placeholder="테스트 메시지"
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
          />
          <button
            onClick={handleTestNotification}
            disabled={!testChannel || testNotificationMutation.isPending}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 font-medium"
          >
            {testNotificationMutation.isPending ? '전송 중...' : '테스트 전송'}
          </button>
        </div>
        {testNotificationMutation.isSuccess && (
          <p className="mt-2 text-sm text-green-600">
            테스트 알림이 전송되었습니다!
          </p>
        )}
        {testNotificationMutation.isError && (
          <p className="mt-2 text-sm text-red-600">
            알림 전송에 실패했습니다.
          </p>
        )}
      </div>

      {/* Price Alerts */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">가격 알림</h2>

        {/* Create Alert Form */}
        <form onSubmit={handleCreateAlert} className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">종목 코드</label>
              <input
                type="text"
                value={newAlert.symbol}
                onChange={(e) => setNewAlert({ ...newAlert, symbol: e.target.value.toUpperCase() })}
                placeholder="예: 005930"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">상한가</label>
              <input
                type="number"
                value={newAlert.price_above}
                onChange={(e) => setNewAlert({ ...newAlert, price_above: e.target.value })}
                placeholder="이상 도달 시"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">하한가</label>
              <input
                type="number"
                value={newAlert.price_below}
                onChange={(e) => setNewAlert({ ...newAlert, price_below: e.target.value })}
                placeholder="이하 도달 시"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={createAlertMutation.isPending}
                className="w-full px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:bg-gray-300"
              >
                추가
              </button>
            </div>
          </div>
        </form>

        {/* Alerts List */}
        {alerts && alerts.length > 0 ? (
          <div className="divide-y">
            {alerts.map((alert) => (
              <div key={alert.id} className="py-4 flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">{alert.symbol}</p>
                  <div className="flex space-x-4 text-sm text-gray-500">
                    {alert.price_above && (
                      <span className="text-red-600">상한: {alert.price_above.toLocaleString()}원</span>
                    )}
                    {alert.price_below && (
                      <span className="text-blue-600">하한: {alert.price_below.toLocaleString()}원</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => deleteAlertMutation.mutate(alert.id)}
                  className="text-red-600 hover:text-red-800 text-sm"
                >
                  삭제
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            설정된 가격 알림이 없습니다
          </div>
        )}
      </div>
    </div>
  );
}
