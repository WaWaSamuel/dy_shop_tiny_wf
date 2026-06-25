import { useState } from 'react';
import {
  Card,
  Table,
  Typography,
  Tag,
  Space,
  Button,
  Input,
  Select,
  DatePicker,
  Row,
  Col,
  Statistic,
  Tooltip,
} from 'antd';
import {
  SearchOutlined,
  ExportOutlined,
  EyeOutlined,
  TruckOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { Order } from '@/types';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const mockOrders: Order[] = [
  {
    id: '1',
    orderId: 'ORD-20240601001',
    productName: '无线蓝牙耳机 TWS',
    buyerName: 'John Smith',
    amount: 29.99,
    quantity: 1,
    status: 'shipped',
    platform: 'TikTok Shop',
    trackingNo: 'YT2024060100001',
    createdAt: '2024-06-01 14:30:00',
    shippedAt: '2024-06-02 09:00:00',
  },
  {
    id: '2',
    orderId: 'ORD-20240601002',
    productName: 'LED智能化妆镜',
    buyerName: 'Emily Chen',
    amount: 15.99,
    quantity: 2,
    status: 'pending',
    platform: 'Temu',
    trackingNo: '',
    createdAt: '2024-06-01 15:20:00',
    shippedAt: '',
  },
  {
    id: '3',
    orderId: 'ORD-20240601003',
    productName: '高腰瑜伽裤',
    buyerName: 'Sarah Johnson',
    amount: 24.99,
    quantity: 1,
    status: 'delivered',
    platform: 'TikTok Shop',
    trackingNo: 'YT2024060100003',
    createdAt: '2024-06-01 09:10:00',
    shippedAt: '2024-06-01 15:00:00',
  },
  {
    id: '4',
    orderId: 'ORD-20240601004',
    productName: '车载手机支架',
    buyerName: 'Mike Wilson',
    amount: 9.99,
    quantity: 3,
    status: 'processing',
    platform: '独立站',
    trackingNo: '',
    createdAt: '2024-06-01 16:45:00',
    shippedAt: '',
  },
  {
    id: '5',
    orderId: 'ORD-20240601005',
    productName: '20000mAh充电宝',
    buyerName: 'Lisa Wang',
    amount: 35.99,
    quantity: 1,
    status: 'shipped',
    platform: 'TikTok Shop',
    trackingNo: 'YT2024060100005',
    createdAt: '2024-06-01 11:00:00',
    shippedAt: '2024-06-02 10:30:00',
  },
  {
    id: '6',
    orderId: 'ORD-20240601006',
    productName: '无线充电器',
    buyerName: 'David Lee',
    amount: 12.99,
    quantity: 1,
    status: 'cancelled',
    platform: 'Temu',
    trackingNo: '',
    createdAt: '2024-06-01 18:20:00',
    shippedAt: '',
  },
];

const statusMap: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: '待处理', color: 'orange', icon: <ClockCircleOutlined /> },
  processing: { label: '处理中', color: 'blue', icon: <ClockCircleOutlined /> },
  shipped: { label: '已发货', color: 'cyan', icon: <TruckOutlined /> },
  delivered: { label: '已签收', color: 'green', icon: <CheckCircleOutlined /> },
  cancelled: { label: '已取消', color: 'default', icon: null },
  refunded: { label: '已退款', color: 'red', icon: null },
};

export default function Orders() {
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const filtered = mockOrders.filter((o) => {
    const matchSearch =
      !searchText ||
      o.orderId.toLowerCase().includes(searchText.toLowerCase()) ||
      o.productName.toLowerCase().includes(searchText.toLowerCase()) ||
      o.buyerName.toLowerCase().includes(searchText.toLowerCase());
    const matchStatus = !statusFilter || o.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const columns: ColumnsType<Order> = [
    {
      title: '订单号',
      dataIndex: 'orderId',
      key: 'orderId',
      width: 160,
      render: (text: string) => <Text copyable={{ text }}>{text}</Text>,
    },
    { title: '商品', dataIndex: 'productName', key: 'productName', width: 180 },
    { title: '买家', dataIndex: 'buyerName', key: 'buyerName', width: 120 },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 100,
      render: (v: number) => `$${v.toFixed(2)}`,
      sorter: (a, b) => a.amount - b.amount,
    },
    { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 70 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => (
        <Tag color={statusMap[s]?.color} icon={statusMap[s]?.icon}>
          {statusMap[s]?.label}
        </Tag>
      ),
    },
    { title: '平台', dataIndex: 'platform', key: 'platform', width: 120 },
    {
      title: '物流单号',
      dataIndex: 'trackingNo',
      key: 'trackingNo',
      width: 160,
      render: (v: string) => v || <Text type="secondary">-</Text>,
    },
    { title: '下单时间', dataIndex: 'createdAt', key: 'createdAt', width: 160 },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: () => (
        <Tooltip title="查看详情">
          <Button type="link" icon={<EyeOutlined />} size="small" />
        </Tooltip>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>
          订单管理
        </Title>
        <Button icon={<ExportOutlined />}>导出订单</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="总订单" value={mockOrders.length} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="待处理" value={mockOrders.filter((o) => o.status === 'pending').length} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="已发货" value={mockOrders.filter((o) => o.status === 'shipped').length} valueStyle={{ color: '#13c2c2' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="总营收" value={mockOrders.reduce((sum, o) => sum + o.amount * o.quantity, 0)} precision={2} prefix="$" valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
      </Row>

      <Card>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col flex="auto">
            <Space>
              <Input
                placeholder="搜索订单号/商品/买家..."
                prefix={<SearchOutlined />}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                allowClear
                style={{ width: 280 }}
              />
              <Select
                placeholder="订单状态"
                allowClear
                style={{ width: 120 }}
                value={statusFilter}
                onChange={setStatusFilter}
                options={Object.entries(statusMap).map(([k, v]) => ({
                  value: k,
                  label: v.label,
                }))}
              />
              <RangePicker placeholder={['开始日期', '结束日期']} />
            </Space>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 条订单` }}
          size="middle"
          scroll={{ x: 1200 }}
        />
      </Card>
    </div>
  );
}
