import { Row, Col, Card, Statistic, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

interface RecentOrder {
  key: string;
  orderId: string;
  product: string;
  amount: number;
  status: string;
  platform: string;
  time: string;
}

const recentOrders: RecentOrder[] = [
  { key: '1', orderId: 'ORD-20240601001', product: '无线蓝牙耳机', amount: 29.99, status: 'shipped', platform: 'TikTok Shop', time: '2024-06-01 14:30' },
  { key: '2', orderId: 'ORD-20240601002', product: 'LED化妆镜', amount: 15.99, status: 'pending', platform: 'Temu', time: '2024-06-01 15:20' },
  { key: '3', orderId: 'ORD-20240601003', product: '瑜伽裤', amount: 24.99, status: 'delivered', platform: 'TikTok Shop', time: '2024-06-01 09:10' },
  { key: '4', orderId: 'ORD-20240601004', product: '手机支架', amount: 9.99, status: 'processing', platform: '独立站', time: '2024-06-01 16:45' },
  { key: '5', orderId: 'ORD-20240601005', product: '便携充电宝', amount: 35.99, status: 'shipped', platform: 'TikTok Shop', time: '2024-06-01 11:00' },
];

const statusMap: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'orange' },
  processing: { label: '处理中', color: 'blue' },
  shipped: { label: '已发货', color: 'cyan' },
  delivered: { label: '已签收', color: 'green' },
};

const columns: ColumnsType<RecentOrder> = [
  { title: '订单号', dataIndex: 'orderId', key: 'orderId', width: 160 },
  { title: '商品', dataIndex: 'product', key: 'product' },
  { title: '金额($)', dataIndex: 'amount', key: 'amount', render: (v: number) => `$${v.toFixed(2)}` },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.label}</Tag>,
  },
  { title: '平台', dataIndex: 'platform', key: 'platform' },
  { title: '时间', dataIndex: 'time', key: 'time', width: 160 },
];

export default function Overview() {
  return (
    <div className="page-shell">
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.overviewInventory} alt="在售商品" size="lg" />
              </div>
              <Statistic
                title="在售商品总数"
                value={1286}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.overviewOrders} alt="今日订单" size="lg" />
              </div>
              <Statistic
                title="今日订单"
                value={87}
                valueStyle={{ color: 'var(--text-main)' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.overviewRevenue} alt="今日营收" size="lg" />
              </div>
              <Statistic
                title="今日营收"
                value={3562.8}
                precision={2}
                valueStyle={{ color: 'var(--text-main)' }}
                suffix="USD"
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.overviewGrowth} alt="利润率" size="lg" />
              </div>
              <Statistic
                title="利润率"
                value={32.5}
                precision={1}
                valueStyle={{ color: 'var(--text-main)' }}
                suffix="%"
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Card className="surface-card" title="最近订单" extra={<a href="#">查看全部</a>}>
        <Table
          columns={columns}
          dataSource={recentOrders}
          pagination={false}
          size="middle"
        />
      </Card>
    </div>
  );
}
