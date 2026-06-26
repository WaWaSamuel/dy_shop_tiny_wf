import * as XLSX from 'xlsx';
import type { ImportedCatalogItem } from '@/types';
import { buildCatalogKey, upsertWorkflowAssetsFromCatalog } from '@/services/workflowAssets';

const STORAGE_KEY = 'dyshop_douzhanggui_catalog';
export const CATALOG_UPDATED_EVENT = 'dyshop:catalog-updated';

const headerAliases = {
  name: ['商品名称', '货品名称', '商品标题', '标题', '名称', 'product_name', 'name'],
  sku: ['货号', '货品编码', '商品编码', '商家编码', 'sku', 'SKU'],
  shopName: ['店铺', '店铺名称', '店铺名', '抖店', 'shop', 'shop_name'],
  category: ['类目', '商品类目', '一级类目', '二级类目', 'category'],
  supplier: ['供应商', '供货商', '厂家', '1688店铺', 'supplier'],
  source: ['来源', '来源平台', 'source', 'platform'],
  externalProductId: ['商品ID', '货品ID', '抖店商品ID', 'product_id', 'goods_id', 'id'],
  price: ['售价', '销售价', '零售价', '商品售价', 'price', 'sale_price'],
  cost: ['供货价', '采购价', '成本价', 'cost', 'supply_price'],
  stock: ['可售库存', '库存', '在库库存', '剩余库存', 'stock', 'qty'],
  status: ['上架状态', '商品状态', '状态', 'listing_status', 'status'],
  updatedAt: ['更新时间', '修改时间', '更新于', '最后更新时间', 'updated_at'],
  link: ['商品链接', '货品链接', '抖店链接', '链接', 'url', 'link'],
} as const;

function emitCatalogUpdated() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(CATALOG_UPDATED_EVENT));
  }
}

function normalizeCellValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number') return String(value);
  return String(value).trim();
}

function normalizeHeaders(row: Record<string, unknown>): Record<string, string> {
  return Object.entries(row).reduce<Record<string, string>>((acc, [key, value]) => {
    acc[key.trim()] = normalizeCellValue(value);
    return acc;
  }, {});
}

function pickField(row: Record<string, string>, aliases: readonly string[]): string {
  for (const alias of aliases) {
    const direct = row[alias];
    if (direct) return direct;
    const fuzzyKey = Object.keys(row).find((key) => key.toLowerCase() === alias.toLowerCase());
    if (fuzzyKey && row[fuzzyKey]) return row[fuzzyKey];
  }
  return '';
}

function parseNumber(value: string): number | null {
  if (!value) return null;
  const numeric = Number(value.replace(/[^\d.-]/g, ''));
  return Number.isFinite(numeric) ? numeric : null;
}

function normalizeListingStatus(statusText: string, stock: number | null): ImportedCatalogItem['listingStatus'] {
  const text = statusText.toLowerCase();
  if (!text && stock !== null) {
    return stock > 0 ? 'pending' : 'unknown';
  }
  if (text.includes('上架') || text.includes('在售') || text.includes('售卖')) return 'active';
  if (text.includes('待') || text.includes('草稿') || text.includes('未上架') || text.includes('待发布')) return 'pending';
  if (text.includes('下架') || text.includes('停售') || text.includes('禁售')) return 'inactive';
  return 'unknown';
}

function buildItem(row: Record<string, unknown>, index: number): ImportedCatalogItem {
  const normalizedRow = normalizeHeaders(row);
  const name = pickField(normalizedRow, headerAliases.name) || `未命名货品 ${index + 1}`;
  const sku = pickField(normalizedRow, headerAliases.sku) || `DZG-${index + 1}`;
  const stock = parseNumber(pickField(normalizedRow, headerAliases.stock));
  const statusText = pickField(normalizedRow, headerAliases.status);
  const externalProductId = pickField(normalizedRow, headerAliases.externalProductId) || undefined;
  const previewItem: ImportedCatalogItem = {
    id: `${sku}-${index}`,
    externalProductId,
    name,
    sku,
    shopName: pickField(normalizedRow, headerAliases.shopName) || '未标记店铺',
    category: pickField(normalizedRow, headerAliases.category) || '未分类',
    supplier: pickField(normalizedRow, headerAliases.supplier) || '抖掌柜导入',
    source: pickField(normalizedRow, headerAliases.source) || '抖掌柜 Excel',
    price: parseNumber(pickField(normalizedRow, headerAliases.price)),
    cost: parseNumber(pickField(normalizedRow, headerAliases.cost)),
    stock,
    statusText: statusText || '待处理',
    listingStatus: normalizeListingStatus(statusText, stock),
    updatedAt: pickField(normalizedRow, headerAliases.updatedAt) || '刚刚导入',
    link: pickField(normalizedRow, headerAliases.link) || undefined,
    raw: normalizedRow,
  };
  const catalogKey = buildCatalogKey(previewItem);

  return {
    ...previewItem,
    id: catalogKey,
    catalogKey,
    workflowAssetId: `wf:${catalogKey}`,
  };
}

export async function parseCatalogExcel(file: File): Promise<ImportedCatalogItem[]> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: 'array' });
  const firstSheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[firstSheetName];
  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(worksheet, { defval: '' });

  return rows
    .filter((row) => Object.values(row).some((value) => normalizeCellValue(value)))
    .map((row, index) => buildItem(row, index))
    .filter((item) => item.name || item.sku);
}

export function saveCatalog(items: ImportedCatalogItem[]): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  upsertWorkflowAssetsFromCatalog(items);
  emitCatalogUpdated();
}

export function getStoredCatalog(): ImportedCatalogItem[] {
  if (typeof window === 'undefined') return [];
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];

  try {
    return JSON.parse(raw) as ImportedCatalogItem[];
  } catch {
    return [];
  }
}

export function clearStoredCatalog(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(STORAGE_KEY);
  emitCatalogUpdated();
}

export function getCatalogMetrics(items: ImportedCatalogItem[]) {
  const activeCount = items.filter((item) => item.listingStatus === 'active').length;
  const pendingCount = items.filter((item) => item.listingStatus === 'pending').length;
  const lowStockCount = items.filter((item) => item.stock !== null && item.stock <= 10).length;
  const totalValue = items.reduce((sum, item) => sum + (item.price ?? 0), 0);

  return {
    total: items.length,
    activeCount,
    pendingCount,
    lowStockCount,
    totalValue,
  };
}
