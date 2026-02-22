import { api } from './client';

export const sectorsApi = {
  list: async () => {
    const response = await api.get('/sectors/list');
    return response.data;
  },
  getPerformance: async () => {
    const response = await api.get('/sectors/performance');
    return response.data;
  },
  getSectorDetail: async (sectorId: string) => {
    const response = await api.get(`/sectors/sector/${sectorId}`);
    return response.data;
  },
  getThemes: async (hotOnly: boolean = false) => {
    const response = await api.get('/sectors/themes', { params: { hot_only: hotOnly } });
    return response.data;
  },
  getThemeDetail: async (themeId: string) => {
    const response = await api.get(`/sectors/theme/${themeId}`);
    return response.data;
  },
  getRotationSignal: async () => {
    const response = await api.get('/sectors/rotation');
    return response.data;
  },
  getRecommended: async (cyclePhase?: string) => {
    const response = await api.get('/sectors/recommended', {
      params: cyclePhase ? { cycle_phase: cyclePhase } : {},
    });
    return response.data;
  },
  getCorrelation: async (periodDays: number = 60) => {
    const response = await api.get('/sectors/correlation', { params: { period_days: periodDays } });
    return response.data;
  },
  search: async (keyword: string) => {
    const response = await api.get('/sectors/search', { params: { keyword } });
    return response.data;
  },
  getHeatmap: async () => {
    const response = await api.get('/sectors/heatmap');
    return response.data;
  },
};
