// Product
export interface Product {
  id: string;
  name: string;
  sku: string;
  image: string;
  price: number;
  cost: number;
  stock: number;
  status: 'active' | 'inactive' | 'out_of_stock' | 'low_stock';
  platform: string;
  category: string;
  createdAt: string;
  updatedAt?: string;
  description?: string;
  variants?: ProductVariant[];
  tags?: string[];
}

export interface ProductVariant {
  id: string;
  name: string;
  sku: string;
  price: number;
  stock: number;
  attributes: Record<string, string>;
}

export interface ImportedCatalogItem {
  id: string;
  catalogKey?: string;
  externalProductId?: string;
  workflowAssetId?: string;
  name: string;
  sku: string;
  shopName: string;
  category: string;
  supplier: string;
  source: string;
  price: number | null;
  cost: number | null;
  stock: number | null;
  statusText: string;
  listingStatus: 'active' | 'pending' | 'inactive' | 'unknown';
  updatedAt: string;
  link?: string;
  raw: Record<string, string>;
}

// Order
export interface Order {
  id: string;
  orderId: string;
  productName: string;
  buyerName: string;
  amount: number;
  quantity: number;
  status: 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled' | 'refunded';
  platform: string;
  trackingNo: string;
  createdAt: string;
  shippedAt: string;
  deliveredAt?: string;
  buyerAddress?: string;
  note?: string;
}

// Flow Node
export interface FlowNodeData extends Record<string, unknown> {
  id: string;
  label: string;
  status: 'completed' | 'running' | 'pending' | 'failed';
  timestamp: string;
  description?: string;
  logs?: FlowLog[];
  relatedLinks?: RelatedLink[];
  metadata?: Record<string, unknown>;
  sequence?: number;
  warningCount?: number;
}

export interface FlowLog {
  id: string;
  time: string;
  content: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

export interface RelatedLink {
  title: string;
  url: string;
  type?: string;
}

export type WorkflowStageStatus = 'completed' | 'running' | 'pending' | 'failed';

export type WorkflowStageKey =
  | 'candidate_discovery'
  | 'candidate_im_confirm'
  | 'supplier_lookup'
  | 'supplier_im_confirm'
  | 'product_info_collect'
  | 'creative_prepare'
  | 'douyin_listing'
  | 'workflow_archive'
  | 'douzhanggui_bind';

export interface WorkflowStageAsset {
  key: WorkflowStageKey;
  label: string;
  status: WorkflowStageStatus;
  timestamp: string;
  description: string;
  logs: FlowLog[];
  relatedLinks: RelatedLink[];
  metadata?: Record<string, unknown>;
}

export interface WorkflowProductSnapshot {
  catalogKey: string;
  externalProductId?: string;
  name: string;
  sku: string;
  shopName: string;
  category: string;
  supplier: string;
  source: string;
  price: number | null;
  cost: number | null;
  stock: number | null;
  listingStatus: ImportedCatalogItem['listingStatus'];
  statusText: string;
  updatedAt: string;
  link?: string;
}

export interface WorkflowAsset {
  id: string;
  catalogKey: string;
  workflowName: string;
  workflowVersion: string;
  createdAt: string;
  updatedAt: string;
  currentStageKey: WorkflowStageKey;
  productSnapshot: WorkflowProductSnapshot;
  stages: WorkflowStageAsset[];
  tags: string[];
  summary: string;
}

// Creative Asset
export interface CreativeAsset {
  id: string;
  productId?: string;
  category: 'main_image' | 'detail_page' | 'video_cover' | 'ad_banner' | 'social_post';
  pipeline: 'text2img' | 'img2img' | 'inpaint' | 'upscale' | 'video';
  engine: string;
  prompt: string;
  systemWords: string[];
  imageUrl: string;
  thumbnailUrl: string;
  status: 'generating' | 'completed' | 'failed';
  starred: boolean;
  version: number;
  createdAt: string;
  metadata?: Record<string, unknown>;
}

// Shop / Platform
export interface Shop {
  id: string;
  name: string;
  platform: 'tiktok_shop' | 'temu' | 'shopify' | 'amazon';
  status: 'active' | 'inactive' | 'suspended';
  url: string;
  apiKey?: string;
  createdAt: string;
  metrics?: ShopMetrics;
}

export interface ShopMetrics {
  totalProducts: number;
  totalOrders: number;
  totalRevenue: number;
  rating: number;
}

// Provider / Supplier
export interface Provider {
  id: string;
  name: string;
  source: 'alibaba_1688' | 'pinduoduo' | 'taobao' | 'direct_factory';
  contactName: string;
  contactPhone: string;
  location: string;
  rating: number;
  totalOrders: number;
  minOrderAmount: number;
  deliveryDays: number;
  categories: string[];
  verified: boolean;
  createdAt: string;
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// API Response
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export type OrchestrationNodeKind = 'agent' | 'workflow' | 'skill' | 'tool' | 'node';

export interface OrchestrationGraphNodeData extends Record<string, unknown> {
  id: string;
  nodeKey?: string;
  kind: OrchestrationNodeKind;
  label: string;
  subtitle?: string | null;
  description?: string | null;
  status?: string | null;
  filePath?: string | null;
  roleType?: string | null;
  layer?: string | null;
  role?: string | null;
  workflowId?: string;
  workflowScopes?: string[];
  relatedWorkflows?: string[];
  relatedSkills?: string[];
  relatedTools?: string[];
  primaryInputs?: string[];
  primaryOutputs?: string[];
  defaultNext?: string[];
  replacedBySkill?: string | null;
  nodeCount?: number;
  edgeCount?: number;
}

export interface OrchestrationCatalogAgent {
  id: string;
  label: string;
  kind: 'agent';
  status: string;
  roleType?: string | null;
  layer?: string | null;
  workflowScopes: string[];
  filePath?: string | null;
  primaryInputs: string[];
  primaryOutputs: string[];
  defaultNext: string[];
  replacedBySkill?: string | null;
  relatedWorkflows: string[];
  relatedSkills: string[];
  relatedTools: string[];
}

export interface OrchestrationCatalogSkill {
  id: string;
  label: string;
  kind: 'skill';
  status: string;
  roleType?: string | null;
  workflowScopes: string[];
  filePath?: string | null;
  replacesAgents?: string[];
  tools?: string[];
}

export interface OrchestrationCatalogTool {
  id: string;
  label: string;
  kind: 'tool';
  status: string;
  toolType?: string | null;
  filePath?: string | null;
  implementation?: string | null;
  backendEntry?: string | null;
  commandEntry?: string | null;
  invokeName?: string | null;
  usedBySkills: string[];
  primaryInputs: string[];
  primaryOutputs: string[];
}

export interface OrchestrationWorkflowSummary {
  id: string;
  label: string;
  kind: 'workflow';
  department?: string | null;
  description?: string | null;
  parentWorkflow?: string | null;
  childWorkflows: string[];
  ministerRole?: string | null;
  workflowController?: string | null;
  entryRules: string[];
  successCriteria: string[];
  filePath?: string | null;
}

export interface OrchestrationWorkflowGraph extends OrchestrationWorkflowSummary {
  workflowId: string;
  roles: Array<Record<string, unknown>>;
  nodes: Array<{
    id: string;
    type: string;
    position: { x: number; y: number };
    data: OrchestrationGraphNodeData;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    label?: string;
    animated?: boolean;
    data?: Record<string, unknown>;
  }>;
}

export interface OrchestrationGraphPayload {
  source: {
    registry: string;
    workflows: string;
    generatedFrom: string;
  };
  summary: {
    agentCount: number;
    activeAgentCount: number;
    workflowCount: number;
    skillCount: number;
    toolCount: number;
  };
  agents: OrchestrationCatalogAgent[];
  skills: OrchestrationCatalogSkill[];
  tools: OrchestrationCatalogTool[];
  workflows: OrchestrationWorkflowSummary[];
  rootGraph: {
    nodes: OrchestrationWorkflowGraph['nodes'];
    edges: OrchestrationWorkflowGraph['edges'];
  };
  workflowGraphs: Record<string, OrchestrationWorkflowGraph>;
}

export interface NewsDigestWindow {
  start: string;
  end: string;
  timezone: string;
  label: string;
}

export interface NewsTopic {
  topic: string;
  count: number;
  sources: string[];
}

export interface NewsSource {
  id: string;
  name: string;
  feedUrl: string;
  homepageUrl?: string | null;
  articleCount: number;
  status: string;
  lastError?: string | null;
  fetchedAt?: string | null;
}

export interface NewsDigestItem {
  id: string;
  title: string;
  sourceId: string;
  sourceName: string;
  url: string;
  publishedAt: string;
  summary: string;
  highlights: string[];
  excerpt: string;
}

export interface NewsDigestPushRecord {
  id: string;
  pushedAt: string;
  title: string;
  content: string;
  itemCount: number;
  status: 'sent' | 'failed';
  targetHint: string;
  receiveIdType: string;
  receiveId: string;
  messageId?: string | null;
  errorDetail?: string | null;
}

export interface NewsDigest {
  window: NewsDigestWindow;
  refreshedAt: string;
  totalSources: number;
  totalArticles: number;
  topics: NewsTopic[];
  sources: NewsSource[];
  items: NewsDigestItem[];
  notes: string[];
  mode: string;
  generatedBy?: string | null;
  pushRecords: NewsDigestPushRecord[];
}

export interface SessionSourceProbeDetail {
  displayName?: string | null;
  userVid?: string | null;
}

export interface SessionSource {
  id: string;
  name: string;
  description: string;
  homepageUrl: string;
  loginUrl: string;
  domainPatterns: string[];
  projectKeys: string[];
  authKind: string;
  probeKind: string;
  probePath: string;
  cookieKey: string;
  enabled: boolean;
  status: 'healthy' | 'expired' | 'unknown';
  severity: 'success' | 'warning' | 'danger';
  healthy: boolean;
  message: string;
  lastCheckedAt?: string | null;
  lastSuccessAt?: string | null;
  lastError?: string | null;
  supportsBrowserSync: boolean;
  hasStoredCookie: boolean;
  isStale: boolean;
  probeDetail: SessionSourceProbeDetail;
}

export interface RuntimeExecutionRecord {
  id: string;
  owner_id: string;
  project_key: string;
  workflow_id?: string | null;
  run_id: string;
  parent_run_id?: string | null;
  capability_kind: 'agent' | 'workflow' | 'skill' | 'other';
  capability_key: string;
  capability_label?: string | null;
  source_kind?: string | null;
  source_key?: string | null;
  phase?: string | null;
  status: string;
  level: string;
  title: string;
  summary?: string | null;
  detail?: string | null;
  host_issue?: string | null;
  review_scorecard: Record<string, unknown>;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
  artifacts: Array<Record<string, unknown>>;
  tags: string[];
  metadata: Record<string, unknown>;
  loop_round?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RuntimeCapabilityCatalogItem {
  capability_kind: 'agent' | 'workflow' | 'skill' | 'other';
  capability_key: string;
  display_name: string;
  status: string;
  role_type?: string | null;
  workflow_scopes: string[];
  layer?: string | null;
  file_path?: string | null;
  source: string;
  metadata: Record<string, unknown>;
  record_count?: number;
  last_status?: string | null;
  last_run_at?: string | null;
}

export interface RuntimeOverviewSummary {
  total_capabilities: number;
  registered_agents: number;
  registered_workflows: number;
  registered_skills: number;
  total_records: number;
  recent_records_24h: number;
  status_counts: Record<string, number>;
  kind_counts: Record<string, number>;
  project_counts: Record<string, number>;
}

export interface RuntimeOverview {
  summary: RuntimeOverviewSummary;
  catalog: RuntimeCapabilityCatalogItem[];
  recent_records: RuntimeExecutionRecord[];
  filter_options: {
    project_keys: string[];
    workflow_ids: string[];
    status_values: string[];
    capability_kinds: string[];
  };
}
