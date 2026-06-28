import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Input,
  Button,
  Space,
  Tag,
  Select,
  Row,
  Col,
  Tooltip,
  Upload,
  Typography,
  Statistic,
  message,
  Alert,
  List,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadProps } from 'antd';
import type { ImportedCatalogItem } from '@/types';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';
import {
  CATALOG_UPDATED_EVENT,
  clearStoredCatalog,
  getCatalogMetrics,
  getStoredCatalog,
  parseCatalogExcel,
  saveCatalog,
} from '@/services/douzhangguiCatalog';
import { buildCatalogKey } from '@/services/workflowAssets';
import { buildCatalogResultSnapshot, getGuardStatus } from '@/services/resultConsoleApi';

const { Text } = Typography;

const demoProducts: ImportedCatalogItem[] = [
  {
    id: 'hachiware 数码店::bt-ear-001::无线蓝牙耳机 tws 入耳式',
    catalogKey: 'hachiware 数码店::bt-ear-001::无线蓝牙耳机 tws 入耳式',
    workflowAssetId: 'wf:hachiware 数码店::bt-ear-001::无线蓝牙耳机 tws 入耳式',
    name: '无线蓝牙耳机 TWS 入耳式',
    sku: 'BT-EAR-001',
    shopName: 'Hachiware 数码店',
    category: '数码配件',
    supplier: '深圳市通达电子有限公司',
    source: '抖掌柜 Excel 示例',
    price: 29.99,
    cost: 8.5,
    stock: 520,
    statusText: '已上架',
    listingStatus: 'active',
    updatedAt: '2026-06-26 09:10',
    raw: {},
  },
  {
    id: 'usagi beauty::led-mir-002::led 智能化妆镜带灯',
    catalogKey: 'usagi beauty::led-mir-002::led 智能化妆镜带灯',
    workflowAssetId: 'wf:usagi beauty::led-mir-002::led 智能化妆镜带灯',
    name: 'LED 智能化妆镜带灯',
    sku: 'LED-MIR-002',
    shopName: 'Usagi Beauty',
    category: '美妆工具',
    supplier: '义乌市美亮电器厂',
    source: '抖掌柜 Excel 示例',
    price: 15.99,
    cost: 4.2,
    stock: 380,
    statusText: '待上架',
    listingStatus: 'pending',
    updatedAt: '2026-06-26 09:30',
    raw: {},
  },
  {
    id: 'momonga active::yg-pnt-003::高腰提臀瑜伽裤',
    catalogKey: 'momonga active::yg-pnt-003::高腰提臀瑜伽裤',
    workflowAssetId: 'wf:momonga active::yg-pnt-003::高腰提臀瑜伽裤',
    name: '高腰提臀瑜伽裤',
    sku: 'YG-PNT-003',
    shopName: 'Momonga Active',
    category: '运动服饰',
    supplier: '义乌运动服饰旗舰店',
    source: '抖掌柜 Excel 示例',
    price: 24.99,
    cost: 6.8,
    stock: 6,
    statusText: '已上架',
    listingStatus: 'active',
    updatedAt: '2026-06-26 10:10',
    raw: {},
  },
];

const statusMap: Record<ImportedCatalogItem['listingStatus'], { label: string; color: string }> = {
  active: { label: '已上架', color: 'green' },
  pending: { label: '待上架', color: 'orange' },
  inactive: { label: '已下架', color: 'default' },
  unknown: { label: '待确认', color: 'blue' },
};

export default function Products() {
  const navigate = useNavigate();
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [catalogItems, setCatalogItems] = useState<ImportedCatalogItem[]>(() => getStoredCatalog());
  const [guardStatus, setGuardStatus] = useState<Awaited<ReturnType<typeof getGuardStatus>> | null>(null);
  const [catalogResultSnapshot, setCatalogResultSnapshot] = useState<Awaited<ReturnType<typeof buildCatalogResultSnapshot>> | null>(null);
  const [guardLoading, setGuardLoading] = useState(false);
  const [catalogResultLoading, setCatalogResultLoading] = useState(false);

  useEffect(() => {
    const syncCatalog = () => setCatalogItems(getStoredCatalog());
    window.addEventListener(CATALOG_UPDATED_EVENT, syncCatalog);
    return () => window.removeEventListener(CATALOG_UPDATED_EVENT, syncCatalog);
  }, []);

  const loadGuardStatus = async (refresh = false) => {
    setGuardLoading(true);
    try {
      const result = await getGuardStatus(refresh);
      setGuardStatus(result);
    } catch (error) {
      console.error(error);
      message.error('守门状态获取失败');
    } finally {
      setGuardLoading(false);
    }
  };

  useEffect(() => {
    void loadGuardStatus(false);
  }, []);

  const usingImportedCatalog = catalogItems.length > 0;
  const dataSource = usingImportedCatalog ? catalogItems : demoProducts;
  const metrics = useMemo(() => getCatalogMetrics(dataSource), [dataSource]);

  const loadCatalogResultSnapshot = async () => {
    setCatalogResultLoading(true);
    try {
      const result = await buildCatalogResultSnapshot(dataSource);
      setCatalogResultSnapshot(result);
    } catch (error) {
      console.error(error);
      message.error('结果快照获取失败');
    } finally {
      setCatalogResultLoading(false);
    }
  };

  useEffect(() => {
    void loadCatalogResultSnapshot();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataSource]);

  const resultViewMap = useMemo(
    () => new Map((catalogResultSnapshot?.workItems || []).map((item) => [item.catalogKey, item])),
    [catalogResultSnapshot]
  );

  const filteredProducts = dataSource.filter((p) => {
    const matchSearch =
      !searchText ||
      p.name.toLowerCase().includes(searchText.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchText.toLowerCase()) ||
      p.shopName.toLowerCase().includes(searchText.toLowerCase());
    const matchStatus = !statusFilter || p.listingStatus === statusFilter;
    return matchSearch && matchStatus;
  });

  const uploadProps: UploadProps = {
    accept: '.xlsx,.xls',
    showUploadList: false,
    beforeUpload: async (file) => {
      try {
        const items = await parseCatalogExcel(file);
        if (!items.length) {
          message.warning('没有识别到有效货品，请检查 Excel 第一张表和表头。');
          return Upload.LIST_IGNORE;
        }

        saveCatalog(items);
        setCatalogItems(items);
        message.success(`已导入 ${items.length} 条抖掌柜货品`);
      } catch (error) {
        console.error(error);
        message.error('Excel 解析失败，请检查文件格式是否正确。');
      }

      return Upload.LIST_IGNORE;
    },
  };

  const columns: ColumnsType<ImportedCatalogItem> = [
    {
      title: '商品',
      key: 'product',
      width: 280,
      render: (_, record) => (
        <Space align="start">
          <div className="metric-badge" style={{ width: 42, height: 42, borderRadius: 14 }}>
              <StickerIcon src={stickers.nav.catalog} alt={record.name} size="md" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 500 }}>{record.name}</div>
            <div style={{ fontSize: 12, color: '#999' }}>{record.sku}</div>
            <div style={{ fontSize: 12, color: '#999' }}>{record.shopName}</div>
          </div>
        </Space>
      ),
    },
    {
      title: '类目 / 供应商',
      key: 'category',
      width: 180,
      render: (_, record) => (
        <div>
          <div>{record.category}</div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.supplier}
          </Text>
        </div>
      ),
    },
    {
      title: '售价',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (v: ImportedCatalogItem['price']) => (v !== null ? `¥${v.toFixed(2)}` : '-'),
      sorter: (a, b) => (a.price ?? 0) - (b.price ?? 0),
    },
    {
      title: '成本',
      dataIndex: 'cost',
      key: 'cost',
      width: 100,
      render: (v: ImportedCatalogItem['cost']) => (v !== null ? `¥${v.toFixed(2)}` : '-'),
    },
    {
      title: '利润率',
      key: 'margin',
      width: 100,
      render: (_, record) => {
        if (record.price === null || record.cost === null || record.price === 0) {
          return <Text type="secondary">-</Text>;
        }

        const margin = ((record.price - record.cost) / record.price) * 100;
        return <span style={{ color: margin > 50 ? '#52c41a' : '#faad14' }}>{margin.toFixed(1)}%</span>;
      },
      sorter: (a, b) => ((a.price ?? 0) - (a.cost ?? 0)) - ((b.price ?? 0) - (b.cost ?? 0)),
    },
    {
      title: '库存',
      dataIndex: 'stock',
      key: 'stock',
      width: 80,
      render: (v: ImportedCatalogItem['stock']) => (v !== null ? v : '-'),
      sorter: (a, b) => (a.stock ?? 0) - (b.stock ?? 0),
    },
    {
      title: '结果阶段',
      key: 'resultStage',
      width: 220,
      render: (_, record) => {
        const catalogKey = record.catalogKey || buildCatalogKey(record);
        const resultView = resultViewMap.get(catalogKey);
        return (
          <div>
            <div>{resultView?.currentStageLabel || '等待结果写入'}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {resultView?.latestResult || '当前没有结构化结果摘要'}
            </Text>
          </div>
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'listingStatus',
      key: 'status',
      width: 120,
      render: (s: ImportedCatalogItem['listingStatus'], record) => (
        <Space direction="vertical" size={2}>
          <Tag color={statusMap[s]?.color}>{statusMap[s]?.label}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.statusText}
          </Text>
        </Space>
      ),
    },
    {
      title: '来源 / 更新时间',
      key: 'meta',
      width: 180,
      render: (_, record) => (
        <div>
          <div>{record.source}</div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.updatedAt}
          </Text>
        </div>
      ),
    },
    {
      title: '风险 / 建议',
      key: 'focus',
      width: 200,
      render: (_, record) => {
        const catalogKey = record.catalogKey || buildCatalogKey(record);
        const resultView = resultViewMap.get(catalogKey);
        const riskColor = resultView?.riskLevel === 'high' ? 'red' : resultView?.riskLevel === 'medium' ? 'gold' : 'green';
        return (
          <Space direction="vertical" size={2}>
            <Tag color={riskColor}>风险：{resultView?.riskLevel || 'low'}</Tag>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {resultView?.recommendedFocus || '当前可继续观察结果变化'}
            </Text>
          </Space>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          {record.link ? (
            <Tooltip title="打开货品链接">
              <Button
                type="link"
                  icon={<StickerIcon src={stickers.actions.link} alt="打开货品链接" size="sm" />}
                href={record.link}
                target="_blank"
              />
            </Tooltip>
          ) : null}
          <Tooltip title="查看全链路">
            <Button
              type="link"
              icon={<StickerIcon src={stickers.actions.flow} alt="查看全链路" size="sm" />}
              onClick={() => navigate(`/project/ecommerce/flow/${encodeURIComponent(record.catalogKey || record.id)}`)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card className="surface-card" style={{ marginBottom: 24 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} lg={12}>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Text strong style={{ fontSize: 18 }}>抖掌柜货盘读取</Text>
              <Text type="secondary">
                1688 物流跟踪和抖店上架在抖掌柜完成，这里只读取导出的 Excel，
                统一展示货品、库存、状态和结果摘要，不在当前页面直接承担业务执行。
              </Text>
              <Alert
                type="info"
                showIcon={false}
                message="建议使用抖掌柜导出的第一张工作表，常见表头如 商品名称 / 货号 / 店铺 / 状态 / 售价 / 成本 / 库存 / 更新时间 都可自动识别。"
              />
            </Space>
          </Col>
          <Col xs={24} lg={12}>
            <Row gutter={[12, 12]}>
              <Col xs={12} sm={6}>
                <Card size="small">
                  <Statistic title="货品总数" value={metrics.total} />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small">
                  <Statistic title="已上架" value={metrics.activeCount} />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small">
                  <Statistic title="待整理" value={metrics.pendingCount} />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small">
                  <Statistic title="低库存" value={metrics.lowStockCount} />
                </Card>
              </Col>
            </Row>
          </Col>
        </Row>
      </Card>

      {guardStatus && (
        <Card className="surface-card" style={{ marginBottom: 24 }}>
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} lg={15}>
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Text strong style={{ fontSize: 16 }}>守门与结果读取状态</Text>
                <Alert
                  type={guardStatus.guardLevel === 'ready' ? 'success' : guardStatus.guardLevel === 'warning' ? 'warning' : 'error'}
                  showIcon
                  message={guardStatus.summary}
                  description={
                    guardStatus.blockingReasons.length
                      ? guardStatus.blockingReasons.join('；')
                      : `开发链：${guardStatus.allowDevelopmentFlow ? '可继续' : '阻断'}；业务链：${guardStatus.allowBusinessFlow ? '可继续' : '阻断'}；外部链：${guardStatus.allowExternalFlow ? '可继续' : '建议先恢复登录态'}`
                  }
                />
              </Space>
            </Col>
            <Col xs={24} lg={9}>
              <Space wrap style={{ width: '100%', justifyContent: 'flex-end' }}>
                <Button
                  icon={<StickerIcon src={stickers.actions.retry} alt="刷新守门状态" size="sm" />}
                  loading={guardLoading}
                  onClick={() => void loadGuardStatus(true)}
                >
                  刷新守门状态
                </Button>
                <Button
                  type="primary"
                  icon={<StickerIcon src={stickers.actions.retry} alt="刷新结果快照" size="sm" />}
                  loading={catalogResultLoading}
                  onClick={() => void loadCatalogResultSnapshot()}
                >
                  刷新结果快照
                </Button>
              </Space>
            </Col>
          </Row>
        </Card>
      )}

      {catalogResultSnapshot && (
        <Card className="surface-card" style={{ marginBottom: 24 }} title="货盘结果快照">
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={10}>
              <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.58)' }}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Text strong>结果接收质量</Text>
                  <Text>{catalogResultSnapshot.qualityReview.summary}</Text>
                  <Space wrap>
                    <Tag color={catalogResultSnapshot.qualityReview.riskLevel === 'low' ? 'green' : catalogResultSnapshot.qualityReview.riskLevel === 'medium' ? 'gold' : 'red'}>
                      风险：{catalogResultSnapshot.qualityReview.riskLevel}
                    </Tag>
                    <Tag color="blue">稳定结果：{catalogResultSnapshot.healthyItems}</Tag>
                    <Tag color="orange">待关注：{catalogResultSnapshot.attentionCount}</Tag>
                  </Space>
                  <Space size={[8, 8]} wrap>
                    {catalogResultSnapshot.qualityReview.findings.map((item) => (
                      <Tag key={item.label}>{item.label} {item.count}</Tag>
                    ))}
                  </Space>
                </Space>
              </Card>
            </Col>
            <Col xs={24} lg={14}>
              <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.58)' }}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Text strong>候选亮点与关注建议</Text>
                  <Text>{catalogResultSnapshot.candidateHighlights.summary}</Text>
                  <List
                    size="small"
                    dataSource={catalogResultSnapshot.candidateHighlights.items.slice(0, 3)}
                    locale={{ emptyText: '当前没有候选亮点' }}
                    renderItem={(item) => (
                      <List.Item>
                        <Space direction="vertical" size={2} style={{ width: '100%' }}>
                          <Space wrap>
                            <Text strong>{item.name}</Text>
                            <Tag color={catalogResultSnapshot.candidateHighlights.recommendedCatalogKey === item.catalogKey ? 'green' : 'default'}>
                              {catalogResultSnapshot.candidateHighlights.recommendedCatalogKey === item.catalogKey ? '优先复看' : '候选'}
                            </Tag>
                            <Tag>分数 {item.score}</Tag>
                          </Space>
                          <Text type="secondary">{item.category} · {item.sku}</Text>
                          <Space size={[6, 6]} wrap>
                            {item.reasons.map((reason) => (
                              <Tag key={reason}>{reason}</Tag>
                            ))}
                          </Space>
                        </Space>
                      </List.Item>
                    )}
                  />
                  <Space size={[6, 6]} wrap>
                    {catalogResultSnapshot.recommendedFocus.map((item) => (
                      <Tag key={item}>{item}</Tag>
                    ))}
                  </Space>
                </Space>
              </Card>
            </Col>
            <Col xs={24}>
              <Alert
                type="info"
                showIcon
                message={catalogResultSnapshot.summary}
                description={`结果快照生成时间：${catalogResultSnapshot.generatedAt}`}
              />
            </Col>
          </Row>
        </Card>
      )}

      <Card>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col flex="auto">
            <Space size={[12, 12]} wrap>
              <Input
                placeholder="搜索商品名称 / SKU / 店铺..."
                prefix={<StickerIcon src={stickers.actions.search} alt="搜索商品" size="sm" />}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                allowClear
                style={{ width: 340 }}
              />
              <Select
                placeholder="状态筛选"
                allowClear
                style={{ width: 140 }}
                value={statusFilter}
                onChange={setStatusFilter}
                options={Object.entries(statusMap).map(([k, v]) => ({
                  value: k,
                  label: v.label,
                }))}
              />
            </Space>
          </Col>
          <Col>
            <Space wrap>
              <Upload {...uploadProps}>
                <Button type="primary" icon={<StickerIcon src={stickers.actions.import} alt="导入 Excel" size="sm" />}>
                  导入抖掌柜 Excel
                </Button>
              </Upload>
              {usingImportedCatalog ? (
                <Button
                  icon={<StickerIcon src={stickers.actions.retry} alt="清空导入" size="sm" />}
                  onClick={() => {
                    clearStoredCatalog();
                    setCatalogItems([]);
                    message.success('已清空当前导入货盘');
                  }}
                >
                  清空导入
                </Button>
              ) : (
                <Tag color="default">当前展示示例数据</Tag>
              )}
            </Space>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={filteredProducts}
          rowKey="id"
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 件货品` }}
          size="middle"
          scroll={{ x: 1280 }}
        />
      </Card>
    </div>
  );
}
