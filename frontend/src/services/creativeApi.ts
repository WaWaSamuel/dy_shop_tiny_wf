import api from './api';

export interface MockCreativeVersion {
  id: string;
  thumbnail: string;
  prompt: string;
  engine: string;
  timestamp: string;
  starred: boolean;
  status: 'generating' | 'completed' | 'failed';
  category: string;
  pipeline: string;
}

export interface MockCreativeResponse {
  generatedAt: string;
  summary: string;
  versions: MockCreativeVersion[];
}

export const mockGenerateCreative = async (payload: {
  category: string;
  pipeline: string;
  engine: string;
  prompt: string;
  systemWords: string[];
}): Promise<MockCreativeResponse> => {
  const response = await api.post('/v1/ecommerce/creative/mock-generate', {
    category: payload.category,
    pipeline: payload.pipeline,
    engine: payload.engine,
    prompt: payload.prompt,
    system_words: payload.systemWords,
  }) as {
    generated_at: string;
    summary: string;
    versions: MockCreativeVersion[];
  };

  return {
    generatedAt: response.generated_at,
    summary: response.summary,
    versions: response.versions,
  };
};
