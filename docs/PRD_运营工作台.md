# 抖店自动化运营工作台 · 产品需求文档（PRD）

> 版本：v1.1　｜　状态：已评审定稿（决策见 §9）　｜　范围：运营前台（Operator Dashboard）信息架构重构 + 后端聚合/缓存数据架构
> 关联系统：FastAPI + Celery + PostgreSQL + Redis 后端；React + Vite 前端
> 文档目标：将现有 7 项平铺侧边栏，重构为「数据看板 / 店铺上架货品 / 选品和上货 / 客户反馈 / 设置」5 大职能区，给出每个区域的交互、数据、接口、状态机；并为长期数据增长设计后端汇总表 + 缓存 + 每日增量更新能力。

---

## 1. 背景与目标

### 1.1 背景
当前工作台侧边栏为功能平铺（仪表盘、反馈、商品、选品、履约、设计、设置），各模块相互独立，运营需要在多个页面间来回跳转才能完成「选品 → 上架 → 售卖 → 履约 → 售后」的完整闭环。后端已具备完整能力：选品打分（discovery）、1688 同源匹配与定价（fulfillment）、上架（product_upload）、设计素材（design_assets）、订单履约与物流（fulfillment）、客服反馈（feedback）。

随着运营时间拉长，`orders`、`logistics_tracks`、`feedback_events` 等流水表会持续累积，看板/列表若每次都实时 `group by` 聚合，将逐渐变慢。需要在后端引入**汇总表 + 缓存 + 每日增量更新**的数据架构（见 §8）。

### 1.2 目标
以**电商自动化的实际工作流**为主线，把"能力"重组为运营每天真正在做的"五件事"：

| 区域 | 运营心智 | 一句话定位 |
| --- | --- | --- |
| 1. 店铺数据看板 | "我今天经营得怎么样" | 经营全景：销售额、趋势、收益、健康度 |
| 2. 店铺上架货品 | "我在卖的货卖得怎么样" | 在架商品 + 每个商品的成交/物流明细 |
| 3. 选品和上货 | "我接下来要上什么货" | 选品到上架的全自动流水线 + 可视化节点 |
| 4. 客户反馈 | "买家在说什么、有没有要紧的" | 多渠道反馈聚合、情绪/紧急度、自动/人工回复 |
| 5. 设置 | "系统怎么配" | 凭证、规则、阈值、自动化开关 |

### 1.3 设计原则
- **行 + 抽屉（Drawer）**：列表用行展示密度信息，点击行从右侧滑出抽屉看深度信息，避免页面跳转、保留上下文。
- **流程可视化优先**：自动化最大的痛点是"黑盒"。选品到上架用自上而下的**节点流（Node Flow）**呈现，每一步可点开看最新数据，让运营对自动化"看得见、可介入"。
- **状态即语言**：所有实体都有清晰的状态机与统一色板的状态徽章，运营扫一眼就知道卡在哪。
- **人在环上（Human-in-the-loop）**：自动跑流水线，但关键节点（店主确认、人工回复）允许人工干预/放行/回退。
- **默认轻、按需深**：所有列表默认只拉**最新 20 条**，配合丰富 filter / 排序按需检索；深度数据延后到抽屉再加载。
- **读汇总、写流水**：前台读取走汇总表/缓存（快），业务写入仍走原始流水表（准），由每日增量任务对齐二者。

---

## 2. 信息架构（侧边栏重构）

```
运营工作台
├── 📊 店铺数据看板        /                (原 Dashboard 升级)
├── 📦 店铺上架货品        /listings         (融合 原 商品 + 履约-订单)
│      └─ 右侧抽屉：商品下所有买家订单（成交 + 物流 + 状态）
├── 🛒 选品和上货          /sourcing         (融合 原 选品 + 设计 + 履约-上架)
│      └─ 右侧抽屉：节点流（候选→货源→整合→确认→素材→上架）
├── 💬 客户反馈            /feedback         (原 Feedback 升为一级区)
│      └─ 右侧抽屉：单条反馈详情 + 回复（自动/人工）+ 同买家历史
└── ⚙️ 设置               /settings
```

### 2.1 旧→新映射（迁移说明）
| 旧菜单 | 去向 |
| --- | --- |
| 仪表盘 Dashboard | → 1 店铺数据看板（扩充经营指标） |
| 商品 Products | → 2 店铺上架货品（作为"在架商品列表"） |
| 履约 Fulfillment - 订单 | → 2 店铺上架货品（下沉为商品抽屉内的"买家订单"） |
| 选品 Discovery | → 3 选品和上货（作为流水线的"候选清单"节点） |
| 设计 Design | → 3 选品和上货（作为流水线的"创建广告资产"节点） |
| 履约 Fulfillment - 上架/物流 | → 3 选品和上货（"上架抖音"节点）+ 2（物流回写到订单） |
| 反馈 Feedback | → 4 客户反馈（升为一级职能区） |
| 设置 Settings | → 5 设置 |

---

## 3. 模块一：店铺数据看板

### 3.1 目标
运营进入系统的第一屏，30 秒内回答："今天赚了多少、趋势如何、有没有要紧的事"。

### 3.2 页面结构
1. **顶部 KPI 卡片区**（5 张，支持"今日 / 近7日 / 近30日"时间切换）
   - 销售额（GMV）、订单数、客单价、毛利额、毛利率
   - 每张卡显示环比（vs 上一周期）箭头与百分比
2. **趋势图区**（双图并排，响应式堆叠）
   - 销售趋势：GMV + 订单数 双轴折线（复用现有 recharts）
   - 收益趋势：毛利额面积图（含成本拆解 tooltip：进货价/运费/佣金/包装）
3. **经营健康度区**（横向卡片）
   - 在架商品数 / 选品流水线进行中数 / 待履约订单数 / 待处理客服反馈数
   - 异常预警：履约失败订单、上架失败商品、低毛利预警（< 保底毛利）、高紧急度反馈
4. **最近动态区**（活动流）
   - 自动化事件时间线：某商品上架成功、某订单已发货、某选品无同源货品、紧急反馈等
   - 每条可点击跳到对应实体（商品抽屉 / 流水线抽屉 / 反馈抽屉）

### 3.3 关键指标定义
| 指标 | 口径 |
| --- | --- |
| GMV | Σ `orders.buyer_paid_amount`（统计周期内，非取消） |
| 毛利额 | Σ (`buyer_paid_amount` − `supplier_orders.total_amount` − 佣金 − 运费 − 包装) |
| 毛利率 | 毛利额 / GMV |
| 待履约 | `orders.status ∈ {received, sourcing, fulfill_failed}` 计数 |
| 在途物流 | `supplier_orders.status ∈ {created, paid, shipped}` 计数 |
| 待处理反馈 | `feedback_events.status ∈ {pending, human_review}` 计数 |

### 3.4 数据来源（后端）
- 新增 `GET /api/v1/dashboard/overview?period=today|7d|30d` → **优先读汇总表 `daily_shop_metrics` + Redis 缓存**（见 §8），返回 KPI 与趋势序列；"今日"部分用"历史汇总 + 当天实时增量"拼接。
- 复用 `GET /api/v1/fulfillment/stats`（listings/orders 状态分布）。
- 当无真实数据时前端回退 mock（与现状一致），保证空库可演示。

### 3.5 交互细节
- 时间切换为分段控件（Segmented），切换即重拉数据并保留滚动位置。
- 预警卡为红/橙底，点击直接跳到筛选后的列表（如"履约失败"→ 货品区订单筛选；"高紧急度反馈"→ 反馈区筛选）。

---

## 4. 模块二：店铺上架货品

### 4.1 目标
管理"正在卖的货"，并能下钻到每个商品的**所有买家订单**（成交 + 物流 + 状态）。

### 4.2 列表（按行展示）
数据源：`SourcedListing` 关联 `Product`（以 `douyin_product_id` 为锚），即"已上架/在架"的货品。
**默认只展示最新 20 条**（按上架/更新时间倒序），其余通过分页加载或 filter 收敛。

每一行字段：
| 区块 | 字段 | 来源 |
| --- | --- | --- |
| 商品主图 | 缩略图（asset_urls / images 首图） | `SourcedListing.asset_urls` / `Product.images` |
| 商品信息 | 标题、类目、上架时间 | `title`、`category`、`listing_approved_at`/`created_at` |
| 状态 | 上架状态徽章 | `ListingStatus`（listed/listing/listing_failed…） |
| 售卖数据 | 售价、累计订单数、累计销量、累计 GMV、毛利率 | `sell_price`、**汇总表 `listing_sales_summary`**、`achieved_margin` |
| 货源信息 | 供应商名（带 1688 链接）、进货价、到手成本 | `supplier_name`、`supplier_url`、`wholesale_price`、`landed_cost` |
| 操作 | 查看详情、下架/重试、复制链接 | — |

**列表能力（filter 配置项）**：
- 默认展示最新 20 条；底部"加载更多"/分页。
- 顶部筛选：状态、类目、关键词搜索、毛利率区间、时间范围、是否有未履约订单。
- 排序：按销量 / GMV / 毛利率 / 上架时间。
- 行内"销量"用迷你进度条或趋势 sparkline 增强可读性。
- 空状态、加载骨架屏、分页/虚拟滚动（>500 行时启用虚拟滚动）。

### 4.3 右侧抽屉：商品的买家订单明细
点击任意商品行 → 右侧滑出 Drawer（宽度约 480~560px，背景半透明遮罩，ESC/点遮罩关闭）。

**抽屉头部**：商品缩略图 + 标题 + 状态 + 核心数据（售价/累计销量/毛利率）。

**抽屉 Tab 1 · 买家订单列表**（默认，首屏 20 条）
逐条展示该商品下 `Order`：
| 字段 | 来源 | 说明 |
| --- | --- | --- |
| 抖店订单号 | `Order.douyin_order_id` | 可复制 |
| 成交信息 | `quantity`、`buyer_paid_amount`、下单时间 | — |
| 订单状态 | `OrderStatus` 徽章 | received→sourcing→sourced→shipped→delivered |
| 1688 采购单 | `SupplierOrder.alibaba_order_id`、`total_amount`、状态 | 履约链路 |
| 物流信息 | `tracking_no`、`logistics_company`、最新轨迹节点 | 来自 `LogisticsTrack` |
| 操作 | 手动履约（received/fulfill_failed 时）、刷新物流、查看轨迹 | 调履约接口 |

**单订单展开 · 物流时间线**
点击订单 → 展开 `LogisticsTrack.trace_detail`（时间 + 描述）的竖向时间线，最新在上；标注是否已回写抖店（`synced_to_douyin`）。

**抽屉 Tab 2 · 商品概况**
- 价格构成（进货价 / 运费 / 佣金 / 包装 / 毛利）瀑布或堆叠条。
- SKU 映射（`sku_mapping`：抖店 SKU ↔ 1688 SKU）。
- 广告资产预览（`asset_urls` 图/视频）。
- 货源详情（供应商、匹配分、delivery_location）。

### 4.4 数据来源（后端）
- `GET /api/v1/fulfillment/listings?limit=20&offset=...&status=&category=&q=`（已存在，需补充分页与聚合字段；售卖数据读 `listing_sales_summary`）。
- `GET /api/v1/fulfillment/orders?listing_id=...&limit=20&offset=...`（按商品过滤；现有 orders 接口需支持该过滤与分页）。
- `POST /api/v1/fulfillment/orders/{id}/fulfill`（已存在）。
- 新增 `GET /api/v1/fulfillment/orders/{id}/tracks` → 返回 `LogisticsTrack` 列表。

### 4.5 状态机参考
```
商品(Listing):  matching → matched → listing → listed
                                   ↘ no_source / listing_failed
订单(Order):    received → sourcing → sourced → shipped → delivered
                        ↘ fulfill_failed        ↘ cancelled
采购单(Supplier): created → paid → shipped → success / failed / cancelled
```

---

## 5. 模块三：选品和上货

### 5.1 目标
把"从发现一个潜力品到它在抖店上架开卖"的**全自动流水线**可视化，让运营像看流程图一样掌控每一单货的进度，并能在关键节点介入。

### 5.2 列表（按行展示）
数据源：以一条"上货任务"为单位（一个 `SourcedListing` 即一条流水线实例；尚未匹配的可由 `TrendingProduct`/`SourceCandidate` 起头）。
**默认只展示最新 20 条**（按更新时间倒序）。

每一行字段：
| 字段 | 来源 | 说明 |
| --- | --- | --- |
| 候选品图 + 名称 | discovery/listing | — |
| 选品评分 | `TrendingProduct.score` | 趋势分 |
| 货源匹配 | `match_score`、供应商、进货价 | 1688 同源 |
| 预估毛利 | `achieved_margin` / `estimated_margin` | 目标 ≥ 10% |
| 当前所处节点 | 见 §5.3 节点枚举 | 高亮"卡在哪" |
| 整体状态 | 进行中 / 待确认 / 成功 / 失败 | — |
| 操作 | 进入流程、推进、重试、放弃 | — |

**列表能力（filter 配置项）**：默认最新 20 条；筛选（节点、状态、类目、评分区间、毛利区间）、排序（评分/毛利/更新时间）、批量操作（批量放行待确认项）。

### 5.3 右侧抽屉：节点流（Node Flow）
点击任意行 → 右侧抽屉，以**自上而下的竖向流程节点**呈现 6 个阶段，每个节点有状态点（待开始/进行中/成功/失败/待人工），节点间用连接线，当前节点高亮：

```
①  选品候选清单    Candidate Shortlist
        │
②  货源查询(1688)  Source Lookup
        │
③  信息整合        Info Aggregation   (SKU/价格/定价计算)
        │
④  店主确认        Owner Confirmation (Human-in-the-loop)
        │
⑤  创建广告资产    Ad Asset Generation
        │
⑥  上架抖音小店    List on 抖店
```

**每个节点的交互**：点击节点 → 弹出该节点最新信息浮层/子抽屉：

| 节点 | 点击后展示 | 数据来源 | 可执行动作 |
| --- | --- | --- | --- |
| ① 候选清单 | 趋势分、销量/增速、竞争度、推荐理由 | `TrendingProduct` + `ProductBrief` | 通过/拒绝候选 |
| ② 货源查询 | 图+文双通道匹配结果列表、各供应商匹配分/评分/成交额 | `SourceMatcher` 结果 / `SourceCandidate` | 选择/更换货源、重新匹配 |
| ③ 信息整合 | SKU 映射、价格构成、定价测算（售价/到手成本/毛利率） | `PricingEngine` / `sku_mapping` | 调整定价参数、重算 |
| ④ 店主确认 | 待确认摘要（货源+定价+毛利） | listing 快照 | **放行** / 退回② / 拒绝 |
| ⑤ 广告资产 | 生成中的主图/详情图/视频任务及预览 | `DesignTask` (design_assets) | 重新生成、选择素材 |
| ⑥ 上架抖店 | 上架请求与回执、抖店商品ID、审核状态 | `product_upload` / `douyin_product_id` | 重试上架、查看抖店链接 |

**节点状态映射**（由 `ListingStatus` 推导，叠加 design/upload 子状态）：
- ① 完成：存在已 APPROVED 的候选 / brief。
- ② 进行中=`matching`，完成=`matched`，失败=`no_source`。
- ③ 完成：`landed_cost`/`sell_price`/`achieved_margin` 已算出。
- ④ 待人工：等待 operator 放行（**默认手动**，可在设置改为按毛利阈值自动放行）。
- ⑤ 由 `DesignTask.status` 驱动（queued/generating/completed）。
- ⑥ 进行中=`listing`，完成=`listed`，失败=`listing_failed`。

### 5.4 触发与自动化
- 顶部"新建选品上货"按钮 → 表单（标题/类目/参考图/描述/是否审核后自动上架）→ `POST /api/v1/fulfillment/source-and-list`（已存在，异步走 Celery）。
- 流水线由后端 Celery 任务串联推进；前端抽屉**用 react-query 轮询（5~10s）刷新节点状态**（一期），二期再上 WebSocket。
- "店主确认"节点：**默认手动确认**；设置中可改为满足毛利阈值自动放行。

### 5.5 数据来源（后端）
- `POST /api/v1/fulfillment/source-and-list`（触发）。
- `GET /api/v1/fulfillment/listings` + `GET /listings/{id}`（流水线实例与详情）。
- 新增 `GET /api/v1/sourcing/{listing_id}/flow` → 返回 6 节点的状态与各自最新 payload（聚合 discovery/pricing/design/upload）。
- 新增 `POST /api/v1/sourcing/{listing_id}/confirm`（店主放行）、`/retry/{node}`（按节点重试）。

---

## 6. 模块四：客户反馈

### 6.1 目标
聚合多渠道（评价/IM/售后/问答/视频评论）买家反馈，按情绪与紧急度排序，支持自动回复 + 人工接管，闭环到"已解决"。这是与"卖货闭环"并行的售后闭环，升为一级区。

### 6.2 列表（按行展示）
数据源：`FeedbackEvent`。**默认只展示最新 20 条**（按时间倒序，高紧急度置顶可选）。

每一行字段：
| 字段 | 来源 | 说明 |
| --- | --- | --- |
| 渠道 | `FeedbackSource` | review/im/after_sale/qa/video_comment |
| 类型 | `FeedbackType` | 质量/物流/价格/客服/垃圾/其他 |
| 内容摘要 | `content`（截断） | — |
| 情绪 | `Sentiment` 徽章 | positive/neutral/negative/angry |
| 紧急度 | `urgency`（1~N，红橙黄） | 高亮高紧急 |
| 关联商品 | `product_id` | 可跳到商品抽屉 |
| 状态 | `FeedbackStatus` 徽章 | pending/auto_replied/human_review/resolved |
| 时间 | `timestamp` | — |
| 操作 | 自动回复/人工回复/标记解决 | — |

**列表能力（filter 配置项）**：默认最新 20 条；筛选（渠道、类型、情绪、状态、紧急度阈值、关联商品、时间范围、关键词）；排序（时间/紧急度）；批量（批量自动回复、批量标记解决）。

### 6.3 右侧抽屉：单条反馈详情
点击行 → 右侧抽屉：
- **头部**：渠道/类型/情绪/紧急度 + 关联商品（可跳商品抽屉）。
- **原文与上下文**：`content` 全文、买家 `user_id`、时间。
- **回复区**：
  - 自动回复内容（`auto_reply_content`）展示与"采用/编辑"。
  - 知识库命中建议（`KnowledgeBaseEntry`，按 category/product_id 匹配）+ 回复模板（`ResponseTemplate`，变量填充）。
  - 人工回复输入（`human_reply_content`），发送后置 `human_review`→`resolved`。
- **同买家历史**：该 `user_id` 的历史反馈（识别重复投诉/老客）。

### 6.4 数据来源（后端）
- `GET /api/v1/feedback?limit=20&offset=...&source=&type=&sentiment=&status=&urgency_gte=&product_id=&q=`（按现有 feedback 路由扩展 filter 与分页）。
- 自动回复/人工回复/标记解决相关写接口（复用现有 feedback 模块）。
- 看板"待处理反馈"数读**汇总表 `feedback_daily_stats`**（见 §8）。
- 知识库 / 模板查询接口（复用现有）。

### 6.5 状态机参考
```
反馈(Feedback): pending → auto_replied → human_review → resolved
                       ↘ human_review（命中需人工）↗
```

---

## 7. 模块五：设置

沿用并扩展现有设置，按 Tab 分组：

| Tab | 内容 |
| --- | --- |
| 通用 | 语言（中/英）、时区、默认时间范围、主题 |
| API 凭证 | 抖店 app_key/secret、1688 app_key/secret/access_token、Webhook 签名密钥；连通性测试按钮（脱敏显示，仅写入不回显明文） |
| 选品与定价规则 | 目标毛利率（默认 10%）、保底毛利率、最低匹配分阈值、最低店铺评分/成交额过滤 |
| 自动化开关 | 店主确认是否自动放行（默认手动）、审核通过后自动上架、订单 webhook/轮询兜底开关、物流刷新频率、反馈自动回复开关与情绪/紧急度阈值 |
| 类目与品牌 | 类目映射维护、品牌风格模板（供设计节点使用） |
| 数据与缓存 | 每日聚合任务执行时间、缓存 TTL、汇总表手动重算/回补入口（见 §8） |

落地建议：凭证类写入后端 `.env`/密钥管理，前端只做"是否已配置 + 测试连通"，绝不回显明文。

---

## 8. 后端数据架构：聚合、缓存与每日增量（应对长期数据增长）

### 8.1 问题
`orders`、`supplier_orders`、`logistics_tracks`、`feedback_events` 是持续增长的流水表。看板与列表若每次实时 `JOIN + group by` 全表聚合，随数据量增长会越来越慢，且重复计算历史不变的数据。

### 8.2 方案总览
**分层：流水表（写） → 汇总表（按天/按实体预聚合） → 缓存（热点结果） → 接口（优先读缓存/汇总表）**，由每日定时 Celery 任务做增量 upsert。

```
原始流水表  ──每日增量聚合(Celery beat)──▶  汇总表(PG)  ──读时缓存──▶  Redis  ──▶  API
(orders/...)                              (daily_*/*_summary)         (TTL)
```

### 8.3 新增汇总表（PostgreSQL）
> 均含 `created_at/updated_at`（继承 `Base`），以"自然键 + 唯一约束"支持每日 upsert。

1. **`daily_shop_metrics`** — 看板趋势与 KPI 的按天汇总
   - 字段：`stat_date`(date, unique)、`gmv`、`order_count`、`aov`、`gross_profit`、`gross_margin`、`new_listings`、`fulfilled_orders`、`failed_orders`、`cancelled_orders`
   - 用途：§3 看板趋势图与近 7/30 日 KPI 直接按 `stat_date` 范围查询求和/求均，无需触碰明细。

2. **`listing_sales_summary`** — 每个在架商品的售卖汇总
   - 字段：`listing_id`(unique FK)、`total_orders`、`total_sales_qty`、`total_gmv`、`achieved_margin`、`last_order_at`
   - 用途：§4 商品列表"售卖数据"列直接读，避免对 orders 实时 group by。

3. **`feedback_daily_stats`** — 反馈按天/维度汇总
   - 字段：`stat_date`、`source`、`type`、`sentiment`、`count`、`pending_count`、`resolved_count`、`avg_urgency`（按维度组合唯一）
   - 用途：§3 健康度"待处理反馈"、§6 反馈趋势/分布。

4.（可选，二期）**`sourcing_node_stats`** — 选品流水线各节点积压数，用于看板"流水线进行中"。

### 8.4 每日增量更新（Celery beat）
- 新增任务 `aggregate_daily_metrics_task`，每天凌晨（如 03:00）执行；并提供"当天滚动小时级刷新"任务（如每小时刷新当天 `stat_date` 行）。
- **增量边界**：按 `updated_at >= 上次水位` 或按 `stat_date = 昨天/今天` 重算受影响日期，避免全表扫描。历史日期数据稳定后不再重算。
- **upsert 语义**：`INSERT ... ON CONFLICT (自然键) DO UPDATE`，保证幂等可重跑。
- **回补**：设置页"数据与缓存"提供按日期区间手动重算入口（调 `POST /api/v1/dashboard/recompute?from=&to=`），用于历史回填或口径变更。
- 任务接入 `celery_app.py` 的 `include` 与 `task_routes`，beat 配置进 `scheduler.py`。

### 8.5 缓存层（Redis）
- 看板 `overview` 结果按 `period` 缓存（key 如 `dashboard:overview:{period}`，TTL 5~10min）；"今日"用更短 TTL（1~2min）或"汇总历史 + 实时增量"拼接。
- 列表类查询不强缓存（filter 组合多），靠汇总表加速即可；命中率高的默认查询（最新 20 条无 filter）可短 TTL 缓存。
- **失效策略**：订单/履约状态变更、每日聚合任务完成后，主动删除相关 key（或靠 TTL 自然过期，一期可只用 TTL）。

### 8.6 读取改造
- `GET /dashboard/overview`：先查 Redis → 未命中查汇总表 → 回写缓存。
- §4/§6 列表的"售卖数据/反馈统计"列读对应汇总表；明细（订单/物流/反馈原文）仍走流水表，仅在抽屉打开时按需加载。
- 兼容空库：汇总表为空时回退实时聚合或 mock，保证可演示。

---

## 9. 已评审决策记录

| # | 议题 | 决策 |
| --- | --- | --- |
| 1 | 客服反馈（Feedback）归属 | **升为一级职能区**（§6 模块四 `/feedback`），共 5 大区 |
| 2 | 节点流刷新方式 | 一期 **react-query 轮询（5~10s）**，二期 WebSocket |
| 3 | 店主确认默认行为 | **默认手动放行**，设置可改为按毛利阈值自动 |
| 4 | 列表数据量 | 所有列表**默认展示最新 20 条** + 丰富 filter / 排序 / 分页；>500 行启用虚拟滚动 |
| 5 | 销量/GMV 聚合 | 采用**汇总表 + 缓存 + 每日增量**（§8），不做长期实时全表聚合 |
| 6 | 长期数据增长 | 后端建汇总表（`daily_shop_metrics` / `listing_sales_summary` / `feedback_daily_stats`），每日 Celery 增量 upsert + Redis 缓存，详见 §8 |

---

## 10. 非功能性需求
- **性能**：列表首屏（20 条）< 1.5s；抽屉打开 < 300ms；看板聚合接口（走汇总表/缓存）< 500ms。
- **空/错/载**：所有列表与抽屉具备空状态、错误重试、骨架屏；无凭证/空库时优雅降级（沿用后端"未配置不崩溃"策略）。
- **一致性**：状态徽章统一色板（复用 `StatusBadge`）；金额统一 ¥ 两位小数；时间本地化。
- **国际化**：所有文案走 `i18n`，中英双语。
- **可观测**：关键自动化事件落"最近动态"，失败可追溯到具体节点与错误信息（`error_message`）；每日聚合任务有执行日志与失败告警。
- **数据准确性**：汇总表与流水表口径一致；提供回补/重算入口校正历史。

---

## 11. 分期建议（落地路线）

**Phase 1（结构重构，1~2 周）**
- 侧边栏改 5 项；商品列表（默认 20 条 + filter）+ 买家订单抽屉（复用现有 fulfillment 接口）；选品上货列表 + 节点流抽屉（静态聚合，节点点击看详情）；反馈列表 + 反馈抽屉（复用现有 feedback 接口）；设置 Tab 化。

**Phase 2（数据闭环 + 后端聚合）**
- 建汇总表（`daily_shop_metrics`/`listing_sales_summary`/`feedback_daily_stats`）+ 每日 Celery 增量任务 + Redis 缓存；看板/列表读改造；节点流后端 `/flow` 聚合与按节点重试/确认；物流轨迹接口。

**Phase 3（体验增强）**
- WebSocket 实时节点刷新；批量放行/批量回复；虚拟滚动；汇总回补入口与缓存失效精细化。

---

## 12. 附录：核心数据实体速查
| 实体 | 表 | 作用 |
| --- | --- | --- |
| TrendingProduct / ProductBrief / SourceCandidate | discovery | 选品候选与货源候选 |
| SourcedListing | sourced_listings | 一条"选品→上架"流水线实例（含定价快照） |
| Product / ProductSKU | products | 抖店在架商品与 SKU |
| Order | orders | 抖店买家订单 |
| SupplierOrder | supplier_orders | 1688 采购单 |
| LogisticsTrack | logistics_tracks | 物流轨迹快照 |
| DesignTask | design_assets | 广告素材生成任务 |
| FeedbackEvent / KnowledgeBaseEntry / ResponseTemplate | feedback | 客户反馈、知识库、回复模板 |
| **daily_shop_metrics**（新增） | 汇总 | 看板按天 KPI/趋势 |
| **listing_sales_summary**（新增） | 汇总 | 商品售卖汇总 |
| **feedback_daily_stats**（新增） | 汇总 | 反馈按天/维度汇总 |

> 文档结束。本版已纳入 6 项评审决策；如确认，我据此进入 Phase 1 前端重构 + Phase 2 后端汇总表与每日聚合任务的实现。
