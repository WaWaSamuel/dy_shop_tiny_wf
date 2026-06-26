import type {
  FlowLog,
  ImportedCatalogItem,
  RelatedLink,
  WorkflowAsset,
  WorkflowProductSnapshot,
  WorkflowStageAsset,
  WorkflowStageKey,
  WorkflowStageStatus,
} from '@/types';

const STORAGE_KEY = 'dyshop_workflow_assets';

const stageDefinitions: Array<{
  key: WorkflowStageKey;
  label: string;
  description: string;
}> = [
  {
    key: 'candidate_discovery',
    label: '候选品筛选',
    description: '按每日规则筛候选品，例如抖音榜单 Top10、近期增速、价格带和评论热度。',
  },
  {
    key: 'candidate_im_confirm',
    label: 'IM 确认候选品',
    description: '把候选品推送到 IM，等待确认是否继续深入查货源。',
  },
  {
    key: 'supplier_lookup',
    label: '1688 货源筛选',
    description: '到 1688 查询最相近的 Top5 候选货源，对比价格、起订量、发货地和店铺评分。',
  },
  {
    key: 'supplier_im_confirm',
    label: 'IM 确认货源',
    description: '把 1688 Top5 货源结果发到 IM，确认最终选用哪个货源。',
  },
  {
    key: 'product_info_collect',
    label: '收集商品信息',
    description: '整理商品卖点、参数、规格、定价、竞品信息和基础文案。',
  },
  {
    key: 'creative_prepare',
    label: '制作上架素材',
    description: '制作主图、详情页、标题卖点和上架需要的素材包。',
  },
  {
    key: 'douyin_listing',
    label: '上架抖店',
    description: '完成货品在抖店的上架动作，并准备后续用抖掌柜承接履约。',
  },
  {
    key: 'workflow_archive',
    label: '归档工作流资产',
    description: '将选品过程、IM 记录、1688 候选、素材信息归档成一份工作流资产。',
  },
  {
    key: 'douzhanggui_bind',
    label: '绑定抖掌柜导入',
    description: '当抖掌柜导入货品 list 时，与这份工作流资产自动关联。',
  },
];

export function buildCatalogKey(item: Partial<ImportedCatalogItem>): string {
  const externalId = item.externalProductId?.trim();
  if (externalId) {
    return `external:${externalId}`;
  }

  const shop = (item.shopName || 'unknown-shop').trim().toLowerCase();
  const sku = (item.sku || 'unknown-sku').trim().toLowerCase();
  const name = (item.name || 'unknown-name').trim().toLowerCase();
  return `${shop}::${sku}::${name}`;
}

function createLogs(contents: Array<{ time: string; content: string; type?: FlowLog['type'] }>): FlowLog[] {
  return contents.map((item, index) => ({
    id: `log-${index + 1}-${item.time}`,
    time: item.time,
    content: item.content,
    type: item.type ?? 'info',
  }));
}

function buildProductSnapshot(item: ImportedCatalogItem): WorkflowProductSnapshot {
  const catalogKey = item.catalogKey || buildCatalogKey(item);
  return {
    catalogKey,
    externalProductId: item.externalProductId,
    name: item.name,
    sku: item.sku,
    shopName: item.shopName,
    category: item.category,
    supplier: item.supplier,
    source: item.source,
    price: item.price,
    cost: item.cost,
    stock: item.stock,
    listingStatus: item.listingStatus,
    statusText: item.statusText,
    updatedAt: item.updatedAt,
    link: item.link,
  };
}

function stageStatusByIndex(
  item: ImportedCatalogItem,
  stageKey: WorkflowStageKey,
  index: number
): WorkflowStageStatus {
  if (stageKey === 'douzhanggui_bind') {
    return 'completed';
  }

  if (stageKey === 'workflow_archive') {
    return item.listingStatus === 'active' ? 'completed' : 'running';
  }

  if (stageKey === 'douyin_listing') {
    if (item.listingStatus === 'active') return 'completed';
    if (item.listingStatus === 'pending') return 'running';
    if (item.listingStatus === 'inactive') return 'failed';
    return 'pending';
  }

  if (item.listingStatus === 'active' && index <= 7) {
    return 'completed';
  }

  if (item.listingStatus === 'pending' && index <= 5) {
    return index === 5 ? 'running' : 'completed';
  }

  if (item.listingStatus === 'inactive' && index <= 6) {
    return index === 6 ? 'failed' : 'completed';
  }

  return 'pending';
}

function buildRelatedLinks(item: ImportedCatalogItem, stageKey: WorkflowStageKey): RelatedLink[] {
  const links: RelatedLink[] = [];

  if (item.link) {
    links.push({ title: '抖店货品链接', url: item.link, type: 'external' });
  }

  if (stageKey === 'supplier_lookup') {
    links.push({ title: '1688 候选货源比对', url: '#', type: 'supplier' });
  }

  if (stageKey === 'candidate_im_confirm' || stageKey === 'supplier_im_confirm') {
    links.push({ title: 'IM 确认记录', url: '#', type: 'im' });
  }

  if (stageKey === 'creative_prepare') {
    links.push({ title: '素材工坊入口', url: '/project/ecommerce/creative-studio', type: 'internal' });
  }

  return links;
}

function buildStageMetadata(item: ImportedCatalogItem, key: WorkflowStageKey): Record<string, unknown> {
  const baseMeta: Record<string, unknown> = {
    店铺: item.shopName,
    SKU: item.sku,
    类目: item.category,
    货源: item.supplier,
  };

  if (key === 'candidate_discovery') {
    return {
      ...baseMeta,
      选品规则: '每日榜单规则待定，当前按抖音 Top 榜单候选推演',
      候选来源: '抖音 Top 榜单前十',
      候选排名: 'Top 10',
    };
  }

  if (key === 'supplier_lookup') {
    return {
      ...baseMeta,
        '1688候选数': 5,
      最优货源: item.supplier,
      供货价: item.cost !== null ? `¥${item.cost.toFixed(2)}` : '待补充',
    };
  }

  if (key === 'product_info_collect') {
    return {
      ...baseMeta,
      售价: item.price !== null ? `¥${item.price.toFixed(2)}` : '待补充',
      库存: item.stock ?? '待补充',
      上架状态: item.statusText,
    };
  }

  if (key === 'douyin_listing') {
    return {
      ...baseMeta,
      抖店状态: item.statusText,
      更新时间: item.updatedAt,
    };
  }

  if (key === 'workflow_archive') {
    return {
      ...baseMeta,
      资产归档ID: `asset:${buildCatalogKey(item)}`,
      资产状态: '已归档到工作流资产',
    };
  }

  if (key === 'douzhanggui_bind') {
    return {
      ...baseMeta,
      绑定方式: '通过 catalogKey 自动关联',
      导入来源: item.source,
      绑定时间: item.updatedAt,
    };
  }

  return baseMeta;
}

function buildStageLogs(item: ImportedCatalogItem, key: WorkflowStageKey, status: WorkflowStageStatus): FlowLog[] {
  const timestamp = item.updatedAt || '2026-06-26 10:00';

  if (status === 'pending') {
    return [];
  }

  if (key === 'candidate_discovery') {
    return createLogs([
      { time: '2026-06-26 08:30', content: '按规则扫描抖音榜单前十候选品', type: 'info' },
      { time: '2026-06-26 08:36', content: `命中候选品：${item.name}`, type: 'success' },
    ]);
  }

  if (key === 'candidate_im_confirm') {
    return createLogs([
      { time: '2026-06-26 08:40', content: '已推送候选品确认消息到 IM', type: 'info' },
      { time: '2026-06-26 08:46', content: 'IM 返回确认，继续查 1688 货源', type: 'success' },
    ]);
  }

  if (key === 'supplier_lookup') {
    return createLogs([
      { time: '2026-06-26 08:58', content: '1688 检索相近货源，筛出 Top5 备选', type: 'info' },
      { time: '2026-06-26 09:05', content: `最优货源暂定为：${item.supplier}`, type: 'success' },
    ]);
  }

  if (key === 'supplier_im_confirm') {
    return createLogs([
      { time: '2026-06-26 09:10', content: '已将 1688 Top5 结果推送到 IM', type: 'info' },
      { time: '2026-06-26 09:12', content: 'IM 已确认最终货源', type: 'success' },
    ]);
  }

  if (key === 'product_info_collect') {
    return createLogs([
      { time: '2026-06-26 09:20', content: '已整理卖点、规格、标题和定价信息', type: 'info' },
      { time: '2026-06-26 09:30', content: '商品基础资料收集完成', type: 'success' },
    ]);
  }

  if (key === 'creative_prepare') {
    return createLogs([
      { time: '2026-06-26 09:40', content: '开始准备主图、详情页和上架素材', type: 'info' },
      {
        time: status === 'completed' ? '2026-06-26 10:10' : timestamp,
        content: status === 'running' ? '素材制作进行中' : '素材包已完成',
        type: status === 'running' ? 'warning' : 'success',
      },
    ]);
  }

  if (key === 'douyin_listing') {
    return createLogs([
      { time: '2026-06-26 10:30', content: '开始上架抖店货品', type: 'info' },
      {
        time: timestamp,
        content:
          status === 'completed'
            ? `货品已上架，当前状态：${item.statusText}`
            : status === 'running'
              ? '上架中，等待状态回写'
              : '上架失败或已下架，需要复查',
        type: status === 'failed' ? 'error' : status === 'running' ? 'warning' : 'success',
      },
    ]);
  }

  if (key === 'workflow_archive') {
    return createLogs([
      { time: timestamp, content: '选品、IM 确认、1688 比货和素材信息已归档', type: 'success' },
    ]);
  }

  return createLogs([
    { time: timestamp, content: '已和抖掌柜导入数据关联', type: 'success' },
  ]);
}

function buildWorkflowStages(item: ImportedCatalogItem): WorkflowStageAsset[] {
  return stageDefinitions.map((definition, index) => {
    const status = stageStatusByIndex(item, definition.key, index);
    const timestamp = status === 'pending' ? '' : item.updatedAt || '2026-06-26 10:00';
    return {
      key: definition.key,
      label: definition.label,
      status,
      timestamp,
      description: definition.description,
      logs: buildStageLogs(item, definition.key, status),
      relatedLinks: buildRelatedLinks(item, definition.key),
      metadata: buildStageMetadata(item, definition.key),
    };
  });
}

function findCurrentStageKey(stages: WorkflowStageAsset[]): WorkflowStageKey {
  return (
    stages.find((stage) => stage.status === 'running')?.key ||
    stages.find((stage) => stage.status === 'pending')?.key ||
    stages[stages.length - 1].key
  );
}

function summarizeWorkflow(item: ImportedCatalogItem, stages: WorkflowStageAsset[]): string {
  const completedCount = stages.filter((stage) => stage.status === 'completed').length;
  return `${item.name} 当前已完成 ${completedCount}/${stages.length} 个节点，当前状态为 ${item.statusText}。`;
}

export function buildWorkflowAssetFromCatalog(item: ImportedCatalogItem): WorkflowAsset {
  const catalogKey = item.catalogKey || buildCatalogKey(item);
  const stages = buildWorkflowStages({ ...item, catalogKey });
  const id = `wf:${catalogKey}`;

  return {
    id,
    catalogKey,
    workflowName: '单品选品上架工作流',
    workflowVersion: 'v2',
    createdAt: item.updatedAt || '2026-06-26 10:00',
    updatedAt: item.updatedAt || '2026-06-26 10:00',
    currentStageKey: findCurrentStageKey(stages),
    productSnapshot: buildProductSnapshot({ ...item, catalogKey }),
    stages,
    tags: ['抖音选品', 'IM确认', '1688比货', '抖店上架', '抖掌柜绑定'],
    summary: summarizeWorkflow(item, stages),
  };
}

export function getStoredWorkflowAssets(): WorkflowAsset[] {
  if (typeof window === 'undefined') return [];
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];

  try {
    return JSON.parse(raw) as WorkflowAsset[];
  } catch {
    return [];
  }
}

export function saveWorkflowAssets(assets: WorkflowAsset[]): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(assets));
}

export function upsertWorkflowAssetsFromCatalog(items: ImportedCatalogItem[]): WorkflowAsset[] {
  const existing = getStoredWorkflowAssets();
  const existingMap = new Map(existing.map((asset) => [asset.catalogKey, asset]));

  const nextAssets = items.map((item) => {
    const catalogKey = item.catalogKey || buildCatalogKey(item);
    const generated = buildWorkflowAssetFromCatalog({ ...item, catalogKey });
    const previous = existingMap.get(catalogKey);
    if (!previous) {
      return generated;
    }

    const mergedStages = generated.stages.map((stage) => {
      const prevStage = previous.stages.find((entry) => entry.key === stage.key);
      if (!prevStage) return stage;

      const isManualStage = stage.key === 'product_info_collect' || stage.key === 'creative_prepare' || stage.key === 'workflow_archive';
      if (isManualStage && prevStage.status !== 'pending') {
        return {
          ...stage,
          status: prevStage.status,
          timestamp: prevStage.timestamp || stage.timestamp,
          logs: prevStage.logs.length ? prevStage.logs : stage.logs,
          relatedLinks: prevStage.relatedLinks.length ? prevStage.relatedLinks : stage.relatedLinks,
          metadata: { ...stage.metadata, ...prevStage.metadata },
        };
      }

      return stage;
    });

    return {
      ...generated,
      createdAt: previous.createdAt,
      stages: mergedStages,
      currentStageKey: findCurrentStageKey(mergedStages),
      summary: summarizeWorkflow(item, mergedStages),
    };
  });

  saveWorkflowAssets(nextAssets);
  return nextAssets;
}

export function getWorkflowAssetByCatalogKey(catalogKey: string): WorkflowAsset | null {
  return getStoredWorkflowAssets().find((asset) => asset.catalogKey === catalogKey) || null;
}

export function getWorkflowAssetProgress(asset: WorkflowAsset | null) {
  if (!asset) {
    return {
      completedCount: 0,
      totalCount: stageDefinitions.length,
      currentLabel: '未创建',
    };
  }

  return {
    completedCount: asset.stages.filter((stage) => stage.status === 'completed').length,
    totalCount: asset.stages.length,
    currentLabel: asset.stages.find((stage) => stage.key === asset.currentStageKey)?.label || '未创建',
  };
}
