import api from './api';

export interface CompareProductPayload {
  id: string;
  name: string;
  price: number;
  minOrder: number;
  source: string;
  supplier: string;
  rating: number;
  sold: number;
  tags: string[];
}

export interface CompareInsight {
  comparedAt: string;
  sampleSize: number;
  recommendedProductId?: string | null;
  lowestPriceProductId?: string | null;
  highestRatingProductId?: string | null;
  rankings: Array<{
    productId: string;
    score: number;
    reasons: string[];
  }>;
}

export const compareSourcingProducts = async (products: CompareProductPayload[]): Promise<CompareInsight> => {
  const response = await api.post('/v1/ecommerce/sourcing/compare', {
    products: products.map((item) => ({
      id: item.id,
      name: item.name,
      price: item.price,
      min_order: item.minOrder,
      source: item.source,
      supplier: item.supplier,
      rating: item.rating,
      sold: item.sold,
      tags: item.tags,
    })),
  }) as {
    compared_at: string;
    sample_size: number;
    recommended_product_id?: string | null;
    lowest_price_product_id?: string | null;
    highest_rating_product_id?: string | null;
    rankings: Array<{ product_id: string; score: number; reasons: string[] }>;
  };

  return {
    comparedAt: response.compared_at,
    sampleSize: response.sample_size,
    recommendedProductId: response.recommended_product_id,
    lowestPriceProductId: response.lowest_price_product_id,
    highestRatingProductId: response.highest_rating_product_id,
    rankings: response.rankings.map((item) => ({
      productId: item.product_id,
      score: item.score,
      reasons: item.reasons,
    })),
  };
};
