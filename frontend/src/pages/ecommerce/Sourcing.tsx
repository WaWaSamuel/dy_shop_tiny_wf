import { useEffect, useMemo, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Typography,
  Tabs,
  Input,
  Tag,
  Space,
  Avatar,
  Rate,
  Alert,
  Empty,
  message,
} from 'antd';
import SourceBadge from '@/components/common/SourceBadge';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const { Text } = Typography;

interface SourceProduct {
  id: string;
  name: string;
  image: string;
  price: number;
  minOrder: number;
  category: 'audio' | 'beauty' | 'fashion' | 'automotive' | 'power';
  source: 'alibaba_1688' | 'pinduoduo' | 'taobao' | 'direct_factory';
  supplier: string;
  rating: number;
  sold: number;
  tags: string[];
}

interface RankedProduct {
  product: SourceProduct;
  score: number;
  reasons: string[];
}

interface SourcingInsight {
  comparedAt: string;
  sampleSize: number;
  recommended: RankedProduct;
  lowestPrice: SourceProduct;
  highestRating: SourceProduct;
  rankings: RankedProduct[];
}

const mockSourceProducts: SourceProduct[] = [
  {
    id: 's1',
    name: 'TWS真无线蓝牙耳机 入耳式降噪',
    image: 'https://via.placeholder.com/120/1677ff/fff?text=BT',
    price: 28.5,
    minOrder: 50,
    category: 'audio',
    source: 'alibaba_1688',
    supplier: '深圳市通达电子有限公司',
    rating: 4.8,
    sold: 12560,
    tags: ['工厂直供', '支持定制', '7天发货'],
  },
  {
    id: 's2',
    name: 'LED化妆镜 智能触控三色光',
    image: 'https://via.placeholder.com/120/ff6b35/fff?text=LED',
    price: 12.8,
    minOrder: 100,
    category: 'beauty',
    source: 'alibaba_1688',
    supplier: '义乌市美亮电器厂',
    rating: 4.6,
    sold: 8900,
    tags: ['源头工厂', '价格优势'],
  },
  {
    id: 's3',
    name: '高腰收腹提臀瑜伽裤 速干面料',
    image: 'https://via.placeholder.com/120/52c41a/fff?text=YG',
    price: 18.9,
    minOrder: 30,
    category: 'fashion',
    source: 'pinduoduo',
    supplier: '义乌运动服饰旗舰店',
    rating: 4.5,
    sold: 25000,
    tags: ['热销爆款', '一件代发'],
  },
  {
    id: 's4',
    name: '车载手机支架 磁吸式',
    image: 'https://via.placeholder.com/120/722ed1/fff?text=PH',
    price: 5.6,
    minOrder: 200,
    category: 'automotive',
    source: 'direct_factory',
    supplier: '东莞市精密模具厂',
    rating: 4.9,
    sold: 45000,
    tags: ['工厂直供', '专利产品', '价格最低'],
  },
  {
    id: 's5',
    name: '20000mAh充电宝 快充 PD协议',
    image: 'https://via.placeholder.com/120/faad14/fff?text=PW',
    price: 38.0,
    minOrder: 20,
    category: 'power',
    source: 'taobao',
    supplier: '品胜数码专营店',
    rating: 4.7,
    sold: 6700,
    tags: ['品牌授权', '正品保障'],
  },
  {
    id: 's6',
    name: '无线充电器 15W 兼容多机型',
    image: 'https://via.placeholder.com/120/13c2c2/fff?text=WC',
    price: 9.9,
    minOrder: 100,
    category: 'power',
    source: 'alibaba_1688',
    supplier: '惠州市能达科技',
    rating: 4.4,
    sold: 18200,
    tags: ['工厂直供', '可OEM'],
  },
];

function formatComparedAt() {
  return new Date().toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function buildScoreReasons(product: SourceProduct, lowestPrice: number): string[] {
  const reasons: string[] = [];

  if (product.price === lowestPrice) reasons.push('当前列表最低价');
  if (product.rating >= 4.8) reasons.push('店铺评分高');
  if (product.sold >= 20000) reasons.push('销量验证充分');
  if (product.minOrder <= 50) reasons.push('起订门槛低');
  if (product.tags.some((tag) => tag.includes('工厂') || tag.includes('源头'))) reasons.push('供货链路短');

  return reasons.length ? reasons : ['价格与供货条件均衡'];
}

function buildCompareInsight(products: SourceProduct[]): SourcingInsight | null {
  if (!products.length) return null;

  const lowestPrice = [...products].sort((a, b) => a.price - b.price)[0];
  const highestRating = [...products].sort((a, b) => b.rating - a.rating || b.sold - a.sold)[0];
  const rankings = products
    .map((product) => {
      const score =
        100
        - product.price * 1.8
        - product.minOrder * 0.05
        + product.rating * 12
        + Math.min(product.sold / 1000, 30)
        + product.tags.length * 2;

      return {
        product,
        score: Number(score.toFixed(1)),
        reasons: buildScoreReasons(product, lowestPrice.price),
      };
    })
    .sort((a, b) => b.score - a.score);

  return {
    comparedAt: formatComparedAt(),
    sampleSize: products.length,
    recommended: rankings[0],
    lowestPrice,
    highestRating,
    rankings,
  };
}

export default function Sourcing() {
  const [activeSource, setActiveSource] = useState<string>('all');
  const [searchText, setSearchText] = useState('');
  const [insight, setInsight] = useState<SourcingInsight | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  const filtered = useMemo(
    () =>
      mockSourceProducts.filter((p) => {
        const matchSource = activeSource === 'all' || p.source === activeSource;
        const matchSearch =
          !searchText || p.name.toLowerCase().includes(searchText.toLowerCase());
        return matchSource && matchSearch;
      }),
    [activeSource, searchText]
  );

  const tabItems = [
    { key: 'all', label: '全部来源' },
    { key: 'alibaba_1688', label: '1688' },
    { key: 'pinduoduo', label: '拼多多' },
    { key: 'taobao', label: '淘宝' },
    { key: 'direct_factory', label: '工厂直联' },
  ];

  const rankingMap = useMemo(
    () => new Map(insight?.rankings.map((item) => [item.product.id, item]) || []),
    [insight]
  );
  const topCandidate = insight?.recommended.product;

  const handleRefreshRecommendationSnapshot = () => {
    setInsight(buildCompareInsight(filtered));
    messageApi.success('已刷新候选结果快照');
  };

  useEffect(() => {
    setInsight(buildCompareInsight(filtered));
  }, [activeSource, searchText]);

  return (
    <div>
      {contextHolder}
      <Card className="surface-card" style={{ marginBottom: 24 }}>
        <Alert
          type="info"
          showIcon={false}
          message="这里现在主要查看候选结果和供货对比快照。真正的选品执行、物流跟踪和上架动作仍在抖掌柜完成，当前页面只负责回看结果与判断是否值得继续推进。"
        />
      </Card>

      <Card className="surface-card sourcing-hero-card" style={{ marginBottom: 24 }}>
        <Row gutter={[18, 18]} align="middle">
          <Col xs={24} lg={15}>
            <Space align="start" size={16}>
              <Avatar
                shape="square"
                size={72}
                src={stickers.dashboard.ecommerce}
                style={{ borderRadius: 24, background: 'linear-gradient(135deg, rgba(232,248,255,0.94), rgba(255,239,246,0.95))', padding: 10 }}
              />
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Text strong style={{ fontSize: 20 }}>候选结果快照</Text>
                <Text type="secondary" style={{ lineHeight: 1.7 }}>
                  当前页优先回答三个问题：谁最值得复看、谁价格最轻、谁验证最充分。先看结果，再决定要不要继续推进到外部执行。
                </Text>
                <Space size={[8, 8]} wrap>
                  <Tag color="blue">当前候选 {filtered.length}</Tag>
                  <Tag color="green">优先复看：{topCandidate?.name || '等待筛选'}</Tag>
                  <Tag>更新时间：{insight?.comparedAt || formatComparedAt()}</Tag>
                </Space>
                <Text type="secondary">当前优先复看对象：{topCandidate?.name || '等待结果刷新后展示'}</Text>
              </Space>
            </Space>
          </Col>
          <Col xs={24} lg={9}>
            <div className="overview-action-grid">
              <button
                type="button"
                className="result-nav-button result-nav-button--primary"
                onClick={handleRefreshRecommendationSnapshot}
                disabled={!filtered.length}
              >
                <img src={stickers.actions.retry} alt="" />
                <span>刷新候选结果</span>
              </button>
              <label className="result-filter-box">
                <span>搜索商品</span>
                <Input
                  placeholder="搜索商品..."
                  prefix={<StickerIcon src={stickers.actions.search} alt="搜索商品" size="sm" />}
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  allowClear
                />
              </label>
            </div>
          </Col>
        </Row>
      </Card>

      {insight && (
        <Card className="surface-card" style={{ marginBottom: 24 }} title="候选结果快照">
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={8}>
              <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.55)' }}>
                <Space direction="vertical" size={6}>
                  <Tag color="green">优先复看</Tag>
                  <Text strong>{insight.recommended.product.name}</Text>
                  <Text type="secondary">{insight.recommended.product.supplier}</Text>
                      <Text>推荐分 {insight.recommended.score}</Text>
                  <Space size={[4, 4]} wrap>
                    {insight.recommended.reasons.map((reason) => (
                      <Tag key={reason}>{reason}</Tag>
                    ))}
                  </Space>
                </Space>
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.55)' }}>
                <Space direction="vertical" size={6}>
                  <Tag color="blue">最低价</Tag>
                  <Text strong>{insight.lowestPrice.name}</Text>
                  <Text>¥{insight.lowestPrice.price}</Text>
                  <Text type="secondary">起订 {insight.lowestPrice.minOrder} 件</Text>
                </Space>
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.55)' }}>
                <Space direction="vertical" size={6}>
                  <Tag color="gold">高评分</Tag>
                  <Text strong>{insight.highestRating.name}</Text>
                  <Text>评分 {insight.highestRating.rating.toFixed(1)}</Text>
                  <Text type="secondary">已售 {insight.highestRating.sold.toLocaleString()}</Text>
                </Space>
              </Card>
            </Col>
          </Row>

          <div style={{ marginTop: 16 }}>
            <Text type="secondary">
              本次结果覆盖 {insight.sampleSize} 个候选，生成时间：{insight.comparedAt}
            </Text>
            <Row gutter={[16, 16]} style={{ marginTop: 12 }}>
              {insight.rankings.slice(0, 3).map((item, index) => (
                <Col xs={24} md={8} key={item.product.id}>
                  <Card size="small" className="result-mini-card">
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      <Space wrap>
                        <Tag color={index === 0 ? 'green' : 'default'}>TOP {index + 1}</Tag>
                        <SourceBadge source={item.product.source} />
                      </Space>
                      <Text strong>{item.product.name}</Text>
                        <Text type="secondary">推荐分 {item.score}</Text>
                      <Space size={[4, 4]} wrap>
                        {item.reasons.map((reason) => (
                          <Tag key={reason}>{reason}</Tag>
                        ))}
                      </Space>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </div>
        </Card>
      )}

      <Card>
        <Tabs
          activeKey={activeSource}
          onChange={setActiveSource}
          items={tabItems}
          style={{ marginBottom: 16 }}
        />

        {!filtered.length ? (
          <Empty description="当前筛选条件下暂无商品" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <Row gutter={[16, 16]}>
            {filtered.map((product) => {
              const ranked = rankingMap.get(product.id);

              return (
                <Col xs={24} sm={12} lg={8} key={product.id}>
                  <Card hoverable size="small" className="result-mini-card">
                    <Space align="start" style={{ width: '100%' }}>
                      <Avatar
                        shape="square"
                        size={80}
                        src={product.image}
                        style={{ borderRadius: 8, flexShrink: 0 }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <Text strong ellipsis style={{ flex: 1 }}>
                            {product.name}
                          </Text>
                          <SourceBadge source={product.source} />
                        </div>
                        <div style={{ margin: '8px 0' }}>
                          <Text style={{ fontSize: 18, color: '#ff4d4f', fontWeight: 600 }}>
                            ¥{product.price}
                          </Text>
                          <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                            起订 {product.minOrder} 件
                          </Text>
                        </div>
                        <div style={{ marginBottom: 8 }}>
                          <Space size={4}>
                            <Rate disabled value={product.rating} allowHalf style={{ fontSize: 12 }} />
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              已售 {product.sold.toLocaleString()}
                            </Text>
                          </Space>
                        </div>
                        {ranked ? (
                          <div style={{ marginBottom: 8 }}>
                            <Space size={[4, 4]} wrap>
                              <Tag color="processing">推荐分 {ranked.score}</Tag>
                              {ranked.reasons.map((reason) => (
                                <Tag key={reason} style={{ fontSize: 11, borderRadius: 4 }}>
                                  {reason}
                                </Tag>
                              ))}
                            </Space>
                          </div>
                        ) : null}
                        <Space size={[4, 4]} wrap>
                          {product.tags.map((tag) => (
                            <Tag key={tag} style={{ fontSize: 11, borderRadius: 4 }}>
                              {tag}
                            </Tag>
                          ))}
                        </Space>
                        <div style={{ marginTop: 8 }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            <StickerIcon src={stickers.actions.supplier} alt="供应商" size="xs" /> {product.supplier}
                          </Text>
                        </div>
                      </div>
                    </Space>
                  </Card>
                </Col>
              );
            })}
          </Row>
        )}
      </Card>
    </div>
  );
}
