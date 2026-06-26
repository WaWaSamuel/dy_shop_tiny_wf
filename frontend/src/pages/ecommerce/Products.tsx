import { useState } from 'react';
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
  Image,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { Product } from '@/types';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const mockProducts: Product[] = [
  {
    id: '1',
    name: '无线蓝牙耳机 TWS 入耳式',
    sku: 'BT-EAR-001',
    image: 'https://via.placeholder.com/60',
    price: 29.99,
    cost: 8.5,
    stock: 520,
    status: 'active',
    platform: 'TikTok Shop',
    category: '数码配件',
    createdAt: '2024-05-01',
  },
  {
    id: '2',
    name: 'LED 智能化妆镜带灯',
    sku: 'LED-MIR-002',
    image: 'https://via.placeholder.com/60',
    price: 15.99,
    cost: 4.2,
    stock: 380,
    status: 'active',
    platform: 'Temu',
    category: '美妆工具',
    createdAt: '2024-05-05',
  },
  {
    id: '3',
    name: '高腰提臀瑜伽裤',
    sku: 'YG-PNT-003',
    image: 'https://via.placeholder.com/60',
    price: 24.99,
    cost: 6.8,
    stock: 0,
    status: 'out_of_stock',
    platform: 'TikTok Shop',
    category: '运动服饰',
    createdAt: '2024-05-10',
  },
  {
    id: '4',
    name: '多功能手机支架车载',
    sku: 'PH-STD-004',
    image: 'https://via.placeholder.com/60',
    price: 9.99,
    cost: 2.1,
    stock: 1200,
    status: 'active',
    platform: '独立站',
    category: '数码配件',
    createdAt: '2024-05-12',
  },
  {
    id: '5',
    name: '20000mAh 便携充电宝',
    sku: 'PW-BNK-005',
    image: 'https://via.placeholder.com/60',
    price: 35.99,
    cost: 12.5,
    stock: 65,
    status: 'low_stock',
    platform: 'TikTok Shop',
    category: '数码配件',
    createdAt: '2024-05-15',
  },
];

const statusMap: Record<string, { label: string; color: string }> = {
  active: { label: '在售', color: 'green' },
  inactive: { label: '下架', color: 'default' },
  out_of_stock: { label: '缺货', color: 'red' },
  low_stock: { label: '低库存', color: 'orange' },
};

export default function Products() {
  const navigate = useNavigate();
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  const filteredProducts = mockProducts.filter((p) => {
    const matchSearch =
      !searchText ||
      p.name.toLowerCase().includes(searchText.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchText.toLowerCase());
    const matchStatus = !statusFilter || p.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const columns: ColumnsType<Product> = [
    {
      title: '商品',
      key: 'product',
      width: 300,
      render: (_, record) => (
        <Space>
          <Image
            src={record.image}
            width={48}
            height={48}
            style={{ borderRadius: 6, objectFit: 'cover' }}
            preview={false}
          />
          <div>
            <div style={{ fontWeight: 500 }}>{record.name}</div>
            <div style={{ fontSize: 12, color: '#999' }}>{record.sku}</div>
          </div>
        </Space>
      ),
    },
    {
      title: '售价',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (v: number) => `$${v.toFixed(2)}`,
      sorter: (a, b) => a.price - b.price,
    },
    {
      title: '成本',
      dataIndex: 'cost',
      key: 'cost',
      width: 100,
      render: (v: number) => `$${v.toFixed(2)}`,
    },
    {
      title: '利润率',
      key: 'margin',
      width: 100,
      render: (_, record) => {
        const margin = ((record.price - record.cost) / record.price) * 100;
        return <span style={{ color: margin > 50 ? '#52c41a' : '#faad14' }}>{margin.toFixed(1)}%</span>;
      },
      sorter: (a, b) =>
        (a.price - a.cost) / a.price - (b.price - b.cost) / b.price,
    },
    {
      title: '库存',
      dataIndex: 'stock',
      key: 'stock',
      width: 80,
      sorter: (a, b) => a.stock - b.stock,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => (
        <Tag color={statusMap[s]?.color}>{statusMap[s]?.label}</Tag>
      ),
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      width: 120,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Space>
          <Tooltip title="查看全链路">
            <Button
              type="link"
              icon={<StickerIcon src={stickers.actionFlow} alt="查看全链路" size="sm" />}
              onClick={() => navigate(`/project/ecommerce/flow/${record.id}`)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 24 }}>
        <Button type="primary" icon={<StickerIcon src={stickers.actionAdd} alt="添加商品" size="sm" />}>
          添加商品
        </Button>
      </div>

      <Card>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col flex="auto">
            <Input
              placeholder="搜索商品名称或 SKU..."
              prefix={<StickerIcon src={stickers.actionSearch} alt="搜索商品" size="sm" />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
              style={{ width: 320 }}
            />
          </Col>
          <Col>
            <Space>
              <Select
                placeholder="状态筛选"
                allowClear
                style={{ width: 120 }}
                value={statusFilter}
                onChange={setStatusFilter}
                options={Object.entries(statusMap).map(([k, v]) => ({
                  value: k,
                  label: v.label,
                }))}
              />
              <Button icon={<StickerIcon src={stickers.actionFilter} alt="更多筛选" size="sm" />}>更多筛选</Button>
            </Space>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={filteredProducts}
          rowKey="id"
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 件商品` }}
          size="middle"
        />
      </Card>
    </div>
  );
}
