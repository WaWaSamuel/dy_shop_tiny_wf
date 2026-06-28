import { useEffect, useMemo, useState } from 'react';
import { Row, Col, Card, Statistic, Table, Tag, Button, Space, Typography, Empty, Alert, List, Avatar } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';
import { CATALOG_UPDATED_EVENT, getCatalogMetrics, getStoredCatalog } from '@/services/douzhangguiCatalog';
import type { ImportedCatalogItem } from '@/types';
import { buildCatalogResultSnapshot } from '@/services/resultConsoleApi';

const { Text } = Typography;

export default function Overview() {
  const [catalogItems, setCatalogItems] = useState<ImportedCatalogItem[]>(() => getStoredCatalog());
  const [catalogResultSnapshot, setCatalogResultSnapshot] = useState<Awaited<ReturnType<typeof buildCatalogResultSnapshot>> | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);

  useEffect(() => {
    const syncCatalog = () => setCatalogItems(getStoredCatalog());
    window.addEventListener(CATALOG_UPDATED_EVENT, syncCatalog);
    return () => window.removeEventListener(CATALOG_UPDATED_EVENT, syncCatalog);
  }, []);

  const metrics = useMemo(() => getCatalogMetrics(catalogItems), [catalogItems]);
  const latestUpdatedLabel = catalogItems[0]?.updatedAt ?? '暂未导入';

  const loadSnapshot = async () => {
    setSnapshotLoading(true);
    try {
      const result = await buildCatalogResultSnapshot(catalogItems);
      setCatalogResultSnapshot(result);
    } catch (error) {
      console.error(error);
    } finally {
      setSnapshotLoading(false);
    }
  };

  useEffect(() => {
    void loadSnapshot();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalogItems]);

  const workItemColumns: ColumnsType<NonNullable<typeof catalogResultSnapshot>['workItems'][number]> = [
    {
      title: '货品 / 店铺',
      key: 'product',
      render: (_, record) => (
        <div>
          <div style={{ fontWeight: 500 }}>{record.name}</div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.shopName}
          </Text>
        </div>
      ),
    },
    {
      title: '当前结果阶段',
      dataIndex: 'currentStageLabel',
      key: 'currentStageLabel',
      width: 180,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    {
      title: '风险',
      dataIndex: 'riskLevel',
      key: 'riskLevel',
      width: 100,
      render: (value: 'low' | 'medium' | 'high') => (
        <Tag color={value === 'high' ? 'red' : value === 'medium' ? 'gold' : 'green'}>
          {value}
        </Tag>
      ),
    },
    {
      title: '最近结果',
      dataIndex: 'latestResult',
      key: 'latestResult',
      width: 220,
    },
    {
      title: '更新时间',
      dataIndex: 'updatedAt',
      key: 'updatedAt',
      width: 160,
    },
    {
      title: '操作',
      key: 'action',
      width: 110,
      render: (_, record) => (
        <Button type="link" onClick={() => window.location.assign(`/project/ecommerce/flow/${encodeURIComponent(record.catalogKey)}`)}>
          查看轨迹
        </Button>
      ),
    },
  ];

  const stageColumns: ColumnsType<NonNullable<typeof catalogResultSnapshot>['stageBreakdown'][number]> = [
    {
      title: '结果阶段',
      dataIndex: 'label',
      key: 'label',
    },
    {
      title: '数量',
      dataIndex: 'count',
      key: 'count',
      width: 90,
    },
  ];

  return (
    <div className="page-shell">
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.imported} alt="已接收结果" size="lg" />
              </div>
              <Statistic
                title="已接收结果"
                value={catalogResultSnapshot?.totalItems ?? metrics.total}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.listed} alt="稳定结果" size="lg" />
              </div>
              <Statistic
                title="稳定结果"
                value={catalogResultSnapshot?.healthyItems ?? metrics.activeCount}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.pending} alt="待关注" size="lg" />
              </div>
              <Statistic
                title="待关注"
                value={catalogResultSnapshot?.attentionCount ?? metrics.pendingCount + metrics.lowStockCount}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.workflow} alt="低库存关注" size="lg" />
              </div>
              <Statistic
                title="低库存关注"
                value={metrics.lowStockCount}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={15}>
          <Card className="surface-card overview-hero-card">
            <Alert
              type={catalogResultSnapshot?.attentionCount ? 'warning' : 'success'}
              showIcon
              message={catalogResultSnapshot?.summary || '当前还没有结果快照，先导入货盘结果。'}
              description={catalogResultSnapshot ? `快照生成时间：${catalogResultSnapshot.generatedAt}` : '导入后会自动生成结果摘要。'}
            />
            <Row gutter={[18, 18]} align="middle" style={{ marginTop: 16 }}>
              <Col xs={24} lg={15}>
                <Space align="start" size={16}>
                  <Avatar
                    src={stickers.dashboard.ecommerce}
                    size={72}
                    shape="square"
                    style={{ borderRadius: 24, background: 'linear-gradient(135deg, rgba(255,236,244,0.96), rgba(255,249,215,0.95))', padding: 10 }}
                  />
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Text strong style={{ fontSize: 20 }}>电商结果总览</Text>
                    <Text type="secondary" style={{ lineHeight: 1.7 }}>
                      这里优先展示当前最值得复看的货品、结果阶段和下一步关注点，让你先知道该看哪里，而不是先进入执行动作。
                    </Text>
                    <Space size={[8, 8]} wrap>
                      <Tag color="magenta">结果台主入口</Tag>
                      <Tag color={catalogResultSnapshot?.attentionCount ? 'gold' : 'green'}>
                        {catalogResultSnapshot?.attentionCount ? '存在待关注结果' : '整体较稳定'}
                      </Tag>
                      <Tag>最近更新：{latestUpdatedLabel}</Tag>
                    </Space>
                    <Text type="secondary">
                      主链入口：
                      <a href="/project/ecommerce/products" style={{ marginLeft: 6 }}>
                        直接进入货盘结果页
                      </a>
                    </Text>
                  </Space>
                </Space>
              </Col>
              <Col xs={24} lg={9}>
                <div className="overview-action-grid">
                  <a
                    className="result-nav-button result-nav-button--primary"
                    href="/project/ecommerce/products"
                  >
                    <img src={stickers.actions.import} alt="" />
                    <span>进入货盘结果页</span>
                  </a>
                  <button
                    type="button"
                    className="result-nav-button"
                    onClick={() => void loadSnapshot()}
                    disabled={snapshotLoading}
                  >
                    <img src={stickers.actions.retry} alt="" />
                    <span>{snapshotLoading ? '正在刷新结果' : '刷新结果快照'}</span>
                  </button>
                </div>
              </Col>
            </Row>
            <div className="overview-hero-kv">
              <div className="ops-kv-row">
                <Text type="secondary">货盘估算售价总和</Text>
                <Text strong>
                  {metrics.totalValue ? `¥${metrics.totalValue.toFixed(2)}` : '待导入'}
                </Text>
              </div>
              <div className="ops-kv-row">
                <Text type="secondary">结果接收质量</Text>
                <Text strong>
                  {catalogResultSnapshot ? `${catalogResultSnapshot.qualityReview.score}/100` : '待生成'}
                </Text>
              </div>
              <div className="ops-kv-row">
                <Text type="secondary">优先复看对象</Text>
                <Text strong>
                  {catalogResultSnapshot?.candidateHighlights.items[0]?.name || '等待结果写入'}
                </Text>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={9}>
          <Card className="surface-card" title="当前建议">
            {catalogResultSnapshot?.recommendedFocus?.length ? (
              <List
                size="small"
                dataSource={catalogResultSnapshot.recommendedFocus}
                renderItem={(item) => <List.Item>{item}</List.Item>}
              />
            ) : (
              <Empty description="先导入结果数据" image={Empty.PRESENTED_IMAGE_SIMPLE}>
                <Button type="primary" onClick={() => window.location.assign('/project/ecommerce/products')}>
                  去货盘页
                </Button>
              </Empty>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={15}>
          <Card className="surface-card" title="最近工作对象">
            {catalogResultSnapshot?.workItems?.length ? (
              <Table
                columns={workItemColumns}
                dataSource={catalogResultSnapshot.workItems}
                rowKey="catalogKey"
                pagination={false}
                size="middle"
              />
            ) : (
              <Empty description="还没有工作对象结果" image={Empty.PRESENTED_IMAGE_SIMPLE}>
                <Button type="primary" onClick={() => window.location.assign('/project/ecommerce/products')}>
                  去货盘页
                </Button>
              </Empty>
            )}
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card className="surface-card" title="结果分布与候选亮点">
            {catalogResultSnapshot ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Row gutter={[12, 12]}>
                  <Col span={12}>
                    <Card size="small">
                      <Statistic title="待上架" value={catalogResultSnapshot.statusBreakdown.find((item) => item.key === 'pending')?.count || 0} />
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card size="small">
                      <Statistic title="已上架" value={catalogResultSnapshot.statusBreakdown.find((item) => item.key === 'active')?.count || 0} />
                    </Card>
                  </Col>
                </Row>
                <Table
                  columns={stageColumns}
                  dataSource={catalogResultSnapshot.stageBreakdown}
                  rowKey="key"
                  pagination={false}
                  size="small"
                />
                <div className="overview-spotlight">
                  <Text strong>候选亮点</Text>
                  <List
                    size="small"
                    dataSource={catalogResultSnapshot.candidateHighlights.items.slice(0, 3)}
                    locale={{ emptyText: '暂无候选亮点' }}
                    renderItem={(item) => (
                      <List.Item>
                        <Space direction="vertical" size={2}>
                          <Space wrap>
                            <Text strong>{item.name}</Text>
                            <Tag color={catalogResultSnapshot.candidateHighlights.recommendedCatalogKey === item.catalogKey ? 'green' : 'default'}>
                              {catalogResultSnapshot.candidateHighlights.recommendedCatalogKey === item.catalogKey ? '优先复看' : '候选'}
                            </Tag>
                          </Space>
                          <Text type="secondary">{item.category} · 分数 {item.score}</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                </div>
              </Space>
            ) : (
              <Empty description="暂无结果分布数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
