import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Card, Statistic, Table, Tag, Button, Space, Steps, Typography, Progress, Empty } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';
import { CATALOG_UPDATED_EVENT, getCatalogMetrics, getStoredCatalog } from '@/services/douzhangguiCatalog';
import { buildWorkflowAssetFromCatalog, getStoredWorkflowAssets } from '@/services/workflowAssets';
import type { ImportedCatalogItem, WorkflowAsset } from '@/types';

const { Text } = Typography;

export default function Overview() {
  const navigate = useNavigate();
  const [catalogItems, setCatalogItems] = useState<ImportedCatalogItem[]>(() => getStoredCatalog());

  useEffect(() => {
    const syncCatalog = () => setCatalogItems(getStoredCatalog());
    window.addEventListener(CATALOG_UPDATED_EVENT, syncCatalog);
    return () => window.removeEventListener(CATALOG_UPDATED_EVENT, syncCatalog);
  }, []);

  const metrics = useMemo(() => getCatalogMetrics(catalogItems), [catalogItems]);
  const latestUpdatedLabel = catalogItems[0]?.updatedAt ?? '暂未导入';
  const workflowAssets = useMemo<WorkflowAsset[]>(
    () => {
      const stored = getStoredWorkflowAssets();
      if (stored.length) return stored;
      return catalogItems.map((item) => buildWorkflowAssetFromCatalog(item));
    },
    [catalogItems]
  );

  const workflowSummary = useMemo(() => {
    const totals = {
      total: workflowAssets.length,
      archived: workflowAssets.filter((asset) => asset.currentStageKey === 'douzhanggui_bind').length,
      producing: workflowAssets.filter((asset) => asset.currentStageKey === 'creative_prepare').length,
      sourcing: workflowAssets.filter((asset) => asset.currentStageKey === 'candidate_discovery' || asset.currentStageKey === 'supplier_lookup').length,
    };

    const stageCountMap = workflowAssets.reduce<Record<string, number>>((acc, asset) => {
      const key = asset.currentStageKey;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});

    const stageRows = Object.entries(stageCountMap)
      .map(([stage, count]) => ({
        key: stage,
        stage,
        count,
      }))
      .sort((a, b) => b.count - a.count);

    return { totals, stageRows };
  }, [workflowAssets]);

  const assetColumns: ColumnsType<WorkflowAsset> = [
    {
      title: '货品 / 店铺',
      key: 'product',
      render: (_, record) => (
        <div>
          <div style={{ fontWeight: 500 }}>{record.productSnapshot.name}</div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.productSnapshot.shopName} · {record.productSnapshot.sku}
          </Text>
        </div>
      ),
    },
    {
      title: '当前阶段',
      key: 'stage',
      width: 180,
      render: (_, record) => {
        const stage = record.stages.find((item) => item.key === record.currentStageKey);
        return <Tag color={stage?.status === 'completed' ? 'green' : stage?.status === 'running' ? 'blue' : 'default'}>{stage?.label || '未开始'}</Tag>;
      },
    },
    {
      title: '进度',
      key: 'progress',
      width: 220,
      render: (_, record) => {
        const completed = record.stages.filter((stage) => stage.status === 'completed').length;
        const percent = Math.round((completed / record.stages.length) * 100);
        return (
          <div>
            <Progress percent={percent} size="small" showInfo={false} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {completed}/{record.stages.length} 已完成
            </Text>
          </div>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 110,
      render: (_, record) => (
        <Button type="link" onClick={() => navigate(`/project/ecommerce/flow/${encodeURIComponent(record.catalogKey)}`)}>
          查看流程
        </Button>
      ),
    },
  ];

  const stageColumns: ColumnsType<{ key: string; stage: string; count: number }> = [
    {
      title: '流程阶段',
      dataIndex: 'stage',
      key: 'stage',
      render: (stage: string) => {
        const matched = workflowAssets
          .flatMap((asset) => asset.stages)
          .find((item) => item.key === stage);
        return matched?.label || stage;
      },
    },
    {
      title: '货品数',
      dataIndex: 'count',
      key: 'count',
      width: 100,
    },
  ];

  return (
    <div className="page-shell">
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.imported} alt="已导入货品" size="lg" />
              </div>
              <Statistic
                title="已导入货品"
                value={metrics.total}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.listed} alt="已上架货品" size="lg" />
              </div>
              <Statistic
                title="已上架货品"
                value={metrics.activeCount}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.pending} alt="待整理货品" size="lg" />
              </div>
              <Statistic
                title="待上架 / 待整理"
                value={metrics.pendingCount}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.workflow} alt="工作流资产" size="lg" />
              </div>
              <Statistic
                title="工作流资产数"
                value={workflowSummary.totals.total}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={15}>
          <Card
            className="surface-card"
            title="当前协同流程"
            extra={
              <Space>
                <Button
                  type="primary"
                  icon={<StickerIcon src={stickers.actions.import} alt="查看货盘导入" size="sm" />}
                  onClick={() => navigate('/project/ecommerce/products')}
                >
                  查看货盘导入
                </Button>
              </Space>
            }
          >
            <Steps
              current={3}
              size="small"
              items={[
                { title: '筛候选品并 IM 确认' },
                { title: '1688 Top5 货源筛选并 IM 确认' },
                { title: '整理资料并制作上架素材' },
                { title: '上架抖店并和抖掌柜导入绑定' },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={9}>
          <Card className="surface-card" title="看板摘要">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <div className="ops-kv-row">
                <Text type="secondary">最近一次更新时间</Text>
                <Text strong>{latestUpdatedLabel}</Text>
              </div>
              <div className="ops-kv-row">
                <Text type="secondary">货盘估算售价总和</Text>
                <Text strong>
                  {metrics.totalValue ? `¥${metrics.totalValue.toFixed(2)}` : '待导入'}
                </Text>
              </div>
              <div className="ops-kv-row">
                <Text type="secondary">低库存风险</Text>
                <Text strong>{metrics.lowStockCount} 个</Text>
              </div>
              <div className="ops-kv-row">
                <Text type="secondary">当前建议</Text>
                <Text strong>
                  {metrics.total > 0 ? '先看卡在哪个流程阶段，再处理待上架和素材准备。' : '先从抖掌柜导出 Excel，再导入货盘页。'}
                </Text>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={15}>
          <Card className="surface-card" title="工作流资产总览">
            {workflowAssets.length === 0 ? (
              <Empty
                description="还没有工作流资产，先导入抖掌柜货盘或创建单品流程。"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button type="primary" onClick={() => navigate('/project/ecommerce/products')}>
                  去货盘页
                </Button>
              </Empty>
            ) : (
              <Table
                columns={assetColumns}
                dataSource={workflowAssets}
                rowKey="id"
                pagination={false}
                size="middle"
              />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card className="surface-card" title="当前卡点分布">
            {workflowSummary.stageRows.length === 0 ? (
              <Empty description="暂无流程阶段数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Row gutter={[12, 12]}>
                  <Col span={8}>
                    <Card size="small">
                      <Statistic title="已归档" value={workflowSummary.totals.archived} />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small">
                      <Statistic title="做素材中" value={workflowSummary.totals.producing} />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small">
                      <Statistic title="选品/找货源" value={workflowSummary.totals.sourcing} />
                    </Card>
                  </Col>
                </Row>
                <Table
                  columns={stageColumns}
                  dataSource={workflowSummary.stageRows}
                  rowKey="key"
                  pagination={false}
                  size="small"
                />
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
