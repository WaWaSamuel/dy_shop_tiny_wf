import api from './api';
import type { ImportedCatalogItem } from '@/types';

export interface GuardStatus {
  checkedAt: string;
  environment: string;
  allowDevelopmentFlow: boolean;
  allowBusinessFlow: boolean;
  allowExternalFlow: boolean;
  guardLevel: 'ready' | 'warning' | 'blocked';
  summary: string;
  blockingReasons: string[];
  sources: Array<{
    id: string;
    name: string;
    healthy: boolean;
    status: string;
    message: string;
    isStale?: boolean;
  }>;
}

export interface ResultBreakdownEntry {
  key: string;
  label: string;
  count: number;
}

export interface QualityReview {
  score: number;
  riskLevel: 'low' | 'medium' | 'high';
  summary: string;
  findings: Array<{ label: string; count: number }>;
}

export interface CandidateHighlight {
  catalogKey: string;
  name: string;
  sku: string;
  category: string;
  listingStatus: ImportedCatalogItem['listingStatus'];
  price: number | null;
  cost: number | null;
  stock: number | null;
  score: number;
  reasons: string[];
}

export interface CandidateHighlights {
  summary: string;
  recommendedCatalogKey?: string | null;
  items: CandidateHighlight[];
}

export interface WorkItemSummary {
  catalogKey: string;
  name: string;
  shopName: string;
  listingStatus: ImportedCatalogItem['listingStatus'];
  currentStageKey: string;
  currentStageLabel: string;
  riskLevel: 'low' | 'medium' | 'high';
  latestResult: string;
  recommendedFocus: string;
  updatedAt: string;
}

export interface CatalogResultSnapshot {
  generatedAt: string;
  summary: string;
  totalItems: number;
  healthyItems: number;
  attentionCount: number;
  statusBreakdown: ResultBreakdownEntry[];
  stageBreakdown: ResultBreakdownEntry[];
  qualityReview: QualityReview;
  candidateHighlights: CandidateHighlights;
  recommendedFocus: string[];
  workItems: WorkItemSummary[];
}

const mapCatalogItem = (item: ImportedCatalogItem) => ({
  id: item.id,
  catalog_key: item.catalogKey,
  name: item.name,
  sku: item.sku,
  shop_name: item.shopName,
  category: item.category,
  supplier: item.supplier,
  source: item.source,
  price: item.price,
  cost: item.cost,
  stock: item.stock,
  status_text: item.statusText,
  listing_status: item.listingStatus,
  updated_at: item.updatedAt,
});

export const getGuardStatus = async (refresh = false): Promise<GuardStatus> => {
  const response = await api.get('/v1/ecommerce/results/guard-status', {
    params: refresh ? { refresh: true } : undefined,
  }) as {
    checked_at: string;
    environment: string;
    allow_development_flow: boolean;
    allow_business_flow: boolean;
    allow_external_flow: boolean;
    guard_level: GuardStatus['guardLevel'];
    summary: string;
    blocking_reasons: string[];
    sources: GuardStatus['sources'];
  };

  return {
    checkedAt: response.checked_at,
    environment: response.environment,
    allowDevelopmentFlow: response.allow_development_flow,
    allowBusinessFlow: response.allow_business_flow,
    allowExternalFlow: response.allow_external_flow,
    guardLevel: response.guard_level,
    summary: response.summary,
    blockingReasons: response.blocking_reasons,
    sources: response.sources,
  };
};

export const buildCatalogResultSnapshot = async (items: ImportedCatalogItem[]): Promise<CatalogResultSnapshot> => {
  const response = await api.post('/v1/ecommerce/results/catalog-result-snapshot', {
    items: items.map(mapCatalogItem),
  }) as {
    generated_at: string;
    summary: string;
    total_items: number;
    healthy_items: number;
    attention_count: number;
    status_breakdown: Array<{ key: string; label: string; count: number }>;
    stage_breakdown: Array<{ key: string; label: string; count: number }>;
    quality_review: {
      score: number;
      risk_level: QualityReview['riskLevel'];
      summary: string;
      findings: QualityReview['findings'];
    };
    candidate_highlights: {
      summary: string;
      recommended_catalog_key?: string | null;
      items: Array<{
        catalog_key: string;
        name: string;
        sku: string;
        category: string;
        listing_status: ImportedCatalogItem['listingStatus'];
        price: number | null;
        cost: number | null;
        stock: number | null;
        score: number;
        reasons: string[];
      }>;
    };
    recommended_focus: string[];
    work_items: Array<{
      catalog_key: string;
      name: string;
      shop_name: string;
      listing_status: ImportedCatalogItem['listingStatus'];
      current_stage_key: string;
      current_stage_label: string;
      risk_level: WorkItemSummary['riskLevel'];
      latest_result: string;
      recommended_focus: string;
      updated_at: string;
    }>;
  };

  return {
    generatedAt: response.generated_at,
    summary: response.summary,
    totalItems: response.total_items,
    healthyItems: response.healthy_items,
    attentionCount: response.attention_count,
    statusBreakdown: response.status_breakdown,
    stageBreakdown: response.stage_breakdown,
    qualityReview: {
      score: response.quality_review.score,
      riskLevel: response.quality_review.risk_level,
      summary: response.quality_review.summary,
      findings: response.quality_review.findings,
    },
    candidateHighlights: {
      summary: response.candidate_highlights.summary,
      recommendedCatalogKey: response.candidate_highlights.recommended_catalog_key,
      items: response.candidate_highlights.items.map((item) => ({
        catalogKey: item.catalog_key,
        name: item.name,
        sku: item.sku,
        category: item.category,
        listingStatus: item.listing_status,
        price: item.price,
        cost: item.cost,
        stock: item.stock,
        score: item.score,
        reasons: item.reasons,
      })),
    },
    recommendedFocus: response.recommended_focus,
    workItems: response.work_items.map((item) => ({
      catalogKey: item.catalog_key,
      name: item.name,
      shopName: item.shop_name,
      listingStatus: item.listing_status,
      currentStageKey: item.current_stage_key,
      currentStageLabel: item.current_stage_label,
      riskLevel: item.risk_level,
      latestResult: item.latest_result,
      recommendedFocus: item.recommended_focus,
      updatedAt: item.updated_at,
    })),
  };
};
