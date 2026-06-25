import { useState } from 'react';
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
} from 'antd';
import {
  SearchOutlined,
  ShopOutlined,
} from '@ant-design/icons';
import SourceBadge from '@/components/common/SourceBadge';

const { Title, Text } = Typography;

interface SourceProduct {
  id: string;
  name: string;
  image: string;
  price: number;
  minOrder: number;
  source: 'alibaba_1688' | 'pinduoduo' | 'taobao' | 'direct_factory';
  supplier: string;
  rating: number;
  sold: number;
  tags: string[];
}

const mockSourceProducts: SourceProduct[] = [
  {
    id: 's1',
    name: 'TWS真无线蓝牙耳机 入耳式降噪',
    image: 'https://via.placeholder.com/120/1677ff/fff?text=BT',
    price: 28.5,
    minOrder: 50,
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
    source: 'alibaba_1688',
    supplier: '惠州市能达科技',
    rating: 4.4,
    sold: 18200,
    tags: ['工厂直供', '可OEM'],
  },
];

export default function Sourcing() {
  const [activeSource, setActiveSource] = useState<string>('all');
  const [searchText, setSearchText] = useState('');

  const filtered = mockSourceProducts.filter((p) => {
    const matchSource = activeSource === 'all' || p.source === activeSource;
    const matchSearch =
      !searchText || p.name.toLowerCase().includes(searchText.toLowerCase());
    return matchSource && matchSearch;
  });

  const tabItems = [
    { key: 'all', label: '全部来源' },
    { key: 'alibaba_1688', label: '1688' },
    { key: 'pinduoduo', label: '拼多多' },
    { key: 'taobao', label: '淘宝' },
    { key: 'direct_factory', label: '工厂直联' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>
          选品中心
        </Title>
        <Input
          placeholder="搜索商品..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ width: 280 }}
        />
      </div>

      <Card>
        <Tabs
          activeKey={activeSource}
          onChange={setActiveSource}
          items={tabItems}
          style={{ marginBottom: 16 }}
        />

        <Row gutter={[16, 16]}>
          {filtered.map((product) => (
            <Col xs={24} sm={12} lg={8} key={product.id}>
              <Card hoverable size="small">
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
                        <Rate disabled defaultValue={product.rating} style={{ fontSize: 12 }} />
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          已售 {product.sold.toLocaleString()}
                        </Text>
                      </Space>
                    </div>
                    <Space size={[4, 4]} wrap>
                      {product.tags.map((tag) => (
                        <Tag key={tag} style={{ fontSize: 11, borderRadius: 4 }}>
                          {tag}
                        </Tag>
                      ))}
                    </Space>
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        <ShopOutlined /> {product.supplier}
                      </Text>
                    </div>
                  </div>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
}
