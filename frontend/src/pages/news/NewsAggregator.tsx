import { useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  List,
  Row,
  Skeleton,
  Space,
  Statistic,
  Tag,
  Typography,
} from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';
import { getNewsDigest, refreshNewsDigest } from '@/services/newsApi';
import type { NewsDigest } from '@/types';

const { Title, Paragraph, Text } = Typography;

export default function NewsAggregator() {
  const [digest, setDigest] = useState<NewsDigest | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDigest = async (forceRefresh = false) => {
    const setBusy = forceRefresh ? setRefreshing : setLoading;
    setBusy(true);
    setError(null);
    try {
      const data = forceRefresh ? await refreshNewsDigest() : await getNewsDigest();
      setDigest(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : '资讯聚合加载失败';
      setError(message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    loadDigest();
  }, []);

  const sourceHealth = useMemo(() => {
    if (!digest) return { ok: 0, error: 0 };
    return digest.sources.reduce(
      (acc, source) => {
        if (source.status === 'ok' || source.status === 'configured') acc.ok += 1;
        else acc.error += 1;
        return acc;
      },
      { ok: 0, error: 0 }
    );
  }, [digest]);

  return (
    <div className="page-shell">
      <Card className="surface-card">
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={16}>
            <Space align="start" size={16}>
              <StickerIcon src={stickers.dashboard.news} alt="资讯聚合引擎" size="xl" />
              <div>
                <Title level={3} style={{ margin: 0 }}>
                  资讯聚合引擎
                </Title>
                <Paragraph style={{ margin: '8px 0 0', maxWidth: 760 }}>
                  聚合你配置的公众号镜像源，默认按最近一个完整窗口汇总：
                  <Text strong> 前一日 21:00 到当日 09:00 </Text>
                  的文章内容，输出提炼摘要和原文跳转链接。
                </Paragraph>
                {digest?.window ? (
                  <Text type="secondary">
                    当前窗口：{digest.window.label} · {digest.window.timezone}
                  </Text>
                ) : null}
              </div>
            </Space>
          </Col>
          <Col xs={24} xl={8}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }} wrap>
              <Button
                icon={<StickerIcon src={stickers.actions.retry} alt="刷新聚合" size="sm" />}
                loading={refreshing}
                onClick={() => loadDigest(true)}
              >
                立即刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {error ? (
        <Alert
          style={{ marginTop: 16 }}
          type="error"
          showIcon
          message="资讯聚合请求失败"
          description={error}
        />
      ) : null}

      {digest?.notes?.length ? (
        <Alert
          style={{ marginTop: 16 }}
          type="info"
          showIcon
          message="配置提示"
          description={
            <Space direction="vertical" size={4}>
              {digest.notes.map((note) => (
                <Text key={note}>{note}</Text>
              ))}
            </Space>
          }
        />
      ) : null}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12} xl={6}>
          <Card className="surface-card">
            <Statistic
              title="聚合文章"
              value={digest?.totalArticles ?? 0}
              prefix={<StickerIcon src={stickers.metrics.imported} alt="聚合文章" size="md" />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="surface-card">
            <Statistic
              title="资讯源"
              value={digest?.totalSources ?? 0}
              prefix={<StickerIcon src={stickers.metrics.workflow} alt="资讯源" size="md" />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="surface-card">
            <Statistic
              title="抓取正常"
              value={sourceHealth.ok}
              prefix={<StickerIcon src={stickers.status.completed} alt="抓取正常" size="md" />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="surface-card">
            <Statistic
              title="最近刷新"
              value={digest?.refreshedAt ? dayjs(digest.refreshedAt).format('MM-DD HH:mm') : '--'}
              prefix={<StickerIcon src={stickers.actions.history} alt="最近刷新" size="md" />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 0 }}>
        <Col xs={24} xl={8}>
          <Card className="surface-card" title="信息源状态">
            {loading ? (
              <Skeleton active paragraph={{ rows: 5 }} />
            ) : digest?.sources.length ? (
              <List
                dataSource={digest.sources}
                renderItem={(source) => (
                  <List.Item
                    actions={[
                      source.homepageUrl ? (
                        <Button
                          key="open"
                          type="link"
                          icon={<StickerIcon src={stickers.actions.link} alt="打开源站" size="sm" />}
                          onClick={() => window.open(source.homepageUrl || source.feedUrl, '_blank', 'noopener,noreferrer')}
                        >
                          打开
                        </Button>
                      ) : null,
                    ].filter(Boolean)}
                  >
                    <List.Item.Meta
                      avatar={<StickerIcon src={stickers.nav.overview} alt={source.name} size="md" />}
                      title={
                        <Space size={8} wrap>
                          <span>{source.name}</span>
                          <Tag color={source.status === 'ok' ? 'green' : source.status === 'configured' ? 'blue' : 'red'}>
                            {source.status === 'ok' ? '正常' : source.status === 'configured' ? '已配置' : '失败'}
                          </Tag>
                        </Space>
                      }
                      description={
                        <Space direction="vertical" size={2}>
                          <Text type="secondary">文章数：{source.articleCount}</Text>
                          {source.lastError ? <Text type="danger">{source.lastError}</Text> : null}
                          {source.fetchedAt ? (
                            <Text type="secondary">抓取时间：{dayjs(source.fetchedAt).format('MM-DD HH:mm:ss')}</Text>
                          ) : null}
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="还没有配置可用的信息源" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card className="surface-card" title="热点提炼">
            {loading ? (
              <Skeleton active paragraph={{ rows: 5 }} />
            ) : digest?.topics.length ? (
              <Space size={[8, 8]} wrap>
                {digest.topics.map((topic) => (
                  <Tag key={topic.topic} color="gold" style={{ padding: '6px 10px', borderRadius: 999 }}>
                    {topic.topic} · {topic.count}
                  </Tag>
                ))}
              </Space>
            ) : (
              <Empty description="当前窗口没有可用热点" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>

          <Card className="surface-card" title="每日聚合信息" style={{ marginTop: 16 }}>
            {loading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : digest?.items.length ? (
              <List
                dataSource={digest.items}
                itemLayout="vertical"
                renderItem={(item) => (
                  <List.Item
                    key={item.id}
                    extra={
                      <Button
                        type="link"
                        icon={<StickerIcon src={stickers.actions.link} alt="查看原文" size="sm" />}
                        onClick={() => window.open(item.url, '_blank', 'noopener,noreferrer')}
                      >
                        查看原文
                      </Button>
                    }
                  >
                    <Space size={[8, 8]} wrap style={{ marginBottom: 8 }}>
                      <Tag color="blue">{item.sourceName}</Tag>
                      <Tag>{dayjs(item.publishedAt).format('MM-DD HH:mm')}</Tag>
                      {item.highlights.slice(0, 2).map((highlight) => (
                        <Tag key={highlight} color="purple">
                          {highlight}
                        </Tag>
                      ))}
                    </Space>
                    <Title level={5} style={{ marginTop: 0, marginBottom: 8 }}>
                      {item.title}
                    </Title>
                    <Paragraph style={{ marginBottom: 8 }}>{item.summary}</Paragraph>
                    {item.excerpt ? (
                      <Text type="secondary">{item.excerpt}</Text>
                    ) : null}
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="当前时间窗口没有抓到新文章" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
