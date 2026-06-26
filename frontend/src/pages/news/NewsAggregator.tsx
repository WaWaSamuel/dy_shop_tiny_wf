import { useEffect, useMemo, useState } from 'react';
import dayjs from 'dayjs';
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Col,
  Drawer,
  Empty,
  Flex,
  List,
  Row,
  Skeleton,
  Select,
  Space,
  Statistic,
  Tag,
  Typography,
  message,
} from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';
import { getNewsDigest, pushNewsDigest, refreshNewsDigest } from '@/services/newsApi';
import { getSessionSources } from '@/services/sessionSourceApi';
import type { NewsDigest, NewsDigestItem, NewsSource, NewsTopic, SessionSource } from '@/types';

const { Title, Paragraph, Text } = Typography;
const DATA_STALE_HOURS = 6;

const sourceStatusMeta: Record<string, { label: string; color: string }> = {
  ok: { label: '正常', color: 'green' },
  configured: { label: '已配置', color: 'blue' },
  error: { label: '失败', color: 'red' },
};

const formatDateTime = (value?: string | null, fallback = '--') => {
  if (!value) {
    return fallback;
  }
  return dayjs(value).format('MM-DD HH:mm');
};

const buildTopicSummary = (topic: NewsTopic) => (
  `关联 ${topic.count} 篇文章，覆盖 ${topic.sources.length} 个来源：${topic.sources.join('、') || '未识别来源'}`
);

const matchesTopic = (item: NewsDigestItem, topic: string) => {
  if (!topic) {
    return true;
  }
  const lower = topic.toLowerCase();
  return [
    item.title,
    item.summary,
    item.excerpt,
    ...item.highlights,
  ].some((segment) => segment?.toLowerCase().includes(lower));
};

export default function NewsAggregator() {
  const [digest, setDigest] = useState<NewsDigest | null>(null);
  const [sessionSources, setSessionSources] = useState<SessionSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSourceId, setSelectedSourceId] = useState<string>('all');
  const [selectedTopic, setSelectedTopic] = useState<string>('all');
  const [selectedArticle, setSelectedArticle] = useState<NewsDigestItem | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  const loadDigest = async (forceRefresh = false) => {
    const setBusy = forceRefresh ? setRefreshing : setLoading;
    setBusy(true);
    setError(null);
    try {
      const data = forceRefresh ? await refreshNewsDigest() : await getNewsDigest();
      setDigest(data);
      try {
        const sessionData = await getSessionSources(forceRefresh);
        setSessionSources(sessionData);
      } catch (sessionError) {
        console.error('Failed to load session sources', sessionError);
      }
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

  const wereadSession = useMemo(
    () => sessionSources.find((source) => source.id === 'weread') ?? null,
    [sessionSources]
  );

  const isDigestStale = useMemo(() => {
    if (!digest?.refreshedAt) {
      return true;
    }
    return dayjs().diff(dayjs(digest.refreshedAt), 'hour', true) >= DATA_STALE_HOURS;
  }, [digest?.refreshedAt]);

  const visibleItems = useMemo(() => {
    if (!digest) {
      return [];
    }
    return digest.items.filter((item) => {
      const sourceMatched = selectedSourceId === 'all' || item.sourceId === selectedSourceId;
      const topicMatched = selectedTopic === 'all' || matchesTopic(item, selectedTopic);
      return sourceMatched && topicMatched;
    });
  }, [digest, selectedSourceId, selectedTopic]);

  const visibleTopicCards = useMemo(() => {
    if (!digest) {
      return [];
    }
    if (selectedSourceId === 'all') {
      return digest.topics.slice(0, 6);
    }
    return digest.topics
      .filter((topic) => topic.sources.includes(digest.sources.find((source) => source.id === selectedSourceId)?.name || ''))
      .slice(0, 6);
  }, [digest, selectedSourceId]);

  const sourceOptions = useMemo(() => {
    if (!digest) {
      return [];
    }
    return [
      { label: '全部来源', value: 'all' },
      ...digest.sources.map((source) => ({ label: source.name, value: source.id })),
    ];
  }, [digest]);

  const topicOptions = useMemo(() => {
    if (!digest) {
      return [];
    }
    return [
      { label: '全部热点', value: 'all' },
      ...digest.topics.map((topic) => ({ label: `${topic.topic} (${topic.count})`, value: topic.topic })),
    ];
  }, [digest]);

  const heroStatusTone = wereadSession?.healthy ? (isDigestStale ? 'warning' : 'success') : 'danger';
  const heroStatusText = !wereadSession
    ? '尚未读取登录态'
    : wereadSession.healthy
      ? (isDigestStale ? '数据待刷新' : '抓取链路正常')
      : '微信读书需要重新登录';

  const openSourceSite = (source: NewsSource) => {
    window.open(source.homepageUrl || source.feedUrl, '_blank', 'noopener,noreferrer');
  };

  const handlePushToFeishu = async () => {
    if (!digest) {
      messageApi.warning('当前还没有可推送的日报数据');
      return;
    }

    const pushItems = visibleItems.slice(0, 10).map((item) => ({
      title: item.title,
      url: item.url,
      summary: item.summary,
    }));

    if (!pushItems.length) {
      messageApi.warning('当前筛选条件下没有可推送的文章');
      return;
    }

    const scopeParts: string[] = [];
    if (selectedSourceId !== 'all') {
      const sourceName = digest.sources.find((source) => source.id === selectedSourceId)?.name;
      if (sourceName) {
        scopeParts.push(`来源：${sourceName}`);
      }
    }
    if (selectedTopic !== 'all') {
      scopeParts.push(`热点：${selectedTopic}`);
    }

    const contentParts = [
      `时间窗口：${digest.window.label}`,
      `推送条数：${pushItems.length}`,
      ...scopeParts,
    ];

    setPushing(true);
    try {
      const result = await pushNewsDigest({
        title: scopeParts.length > 0
          ? `资讯聚合日报 · ${scopeParts.join(' / ')}`
          : '资讯聚合日报',
        content: contentParts.join('｜'),
        items: pushItems,
      });
      messageApi.success(`已推送到飞书：${result.target_hint}`);
    } catch (pushError) {
      console.error('Failed to push digest to Feishu', pushError);
      const detail = pushError instanceof Error ? pushError.message : '飞书推送失败';
      messageApi.error(detail);
    } finally {
      setPushing(false);
    }
  };

  return (
    <div className="page-shell news-aggregator-page">
      {contextHolder}
      <Card className="surface-card news-hero-card">
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={15}>
            <Space align="start" size={16}>
              <StickerIcon src={stickers.dashboard.news} alt="资讯聚合引擎" size="xl" />
              <div>
                <Title level={3} style={{ margin: 0 }}>
                  资讯聚合引擎
                </Title>
                <Paragraph style={{ margin: '8px 0 0', maxWidth: 760 }}>
                  这里不是简单列表，而是每天的资讯工作台。它会按固定时间窗口聚合公众号内容，
                  先告诉你哪些源正常、哪些热点值得看，再把文章按可读顺序铺开。
                </Paragraph>
                <Space size={[8, 8]} wrap>
                  {digest?.window ? <Tag color="blue">窗口：{digest.window.label}</Tag> : null}
                  {digest?.window?.timezone ? <Tag>{digest.window.timezone}</Tag> : null}
                  <Tag color={heroStatusTone === 'success' ? 'green' : heroStatusTone === 'warning' ? 'gold' : 'red'}>
                    {heroStatusText}
                  </Tag>
                </Space>
              </div>
            </Space>
          </Col>
          <Col xs={24} xl={9}>
            <Flex justify="flex-end" align="center" gap={12} wrap="wrap">
              <div className="news-hero-kv">
                <span className="news-hero-kv-label">微信读书</span>
                <span className={`news-hero-kv-value ${wereadSession?.healthy ? 'is-healthy' : 'is-danger'}`}>
                  {wereadSession?.healthy ? '已连接' : '待登录'}
                </span>
              </div>
              <div className="news-hero-kv">
                <span className="news-hero-kv-label">最近刷新</span>
                <span className="news-hero-kv-value">{formatDateTime(digest?.refreshedAt)}</span>
              </div>
              <Button
                type="default"
                loading={pushing}
                disabled={!digest || visibleItems.length === 0}
                onClick={() => void handlePushToFeishu()}
              >
                推送飞书
              </Button>
              <Button
                icon={<StickerIcon src={stickers.actions.retry} alt="刷新聚合" size="sm" />}
                loading={refreshing}
                onClick={() => loadDigest(true)}
              >
                立即刷新
              </Button>
            </Flex>
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
              title="今日文章"
              value={digest?.totalArticles ?? 0}
              prefix={<StickerIcon src={stickers.metrics.imported} alt="聚合文章" size="md" />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="surface-card">
            <Statistic
              title="覆盖来源"
              value={digest?.totalSources ?? 0}
              prefix={<StickerIcon src={stickers.metrics.workflow} alt="资讯源" size="md" />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="surface-card">
            <Statistic
              title="异常来源"
              value={sourceHealth.error}
              prefix={<StickerIcon src={stickers.status.completed} alt="抓取正常" size="md" />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="surface-card">
            <Statistic
              title="数据状态"
              value={isDigestStale ? '待刷新' : '最新'}
              prefix={<StickerIcon src={stickers.actions.history} alt="最近刷新" size="md" />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 0 }}>
        <Col xs={24} xl={7}>
          <Card className="surface-card" title="信息源状态">
            {loading ? (
              <Skeleton active paragraph={{ rows: 5 }} />
            ) : digest?.sources.length ? (
              <List
                dataSource={digest.sources}
                renderItem={(source) => (
                  <List.Item className="news-source-item">
                    <div
                      role="button"
                      tabIndex={0}
                      className={`news-source-card ${selectedSourceId === source.id ? 'is-active' : ''}`}
                      onClick={() => setSelectedSourceId((prev) => (prev === source.id ? 'all' : source.id))}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          setSelectedSourceId((prev) => (prev === source.id ? 'all' : source.id));
                        }
                      }}
                    >
                      <div className="news-source-card-head">
                        <Space size={10} align="center">
                          <Avatar shape="square" size={40} className="news-source-avatar">
                            <StickerIcon src={stickers.nav.overview} alt={source.name} size="md" />
                          </Avatar>
                          <div>
                            <div className="news-source-name">{source.name}</div>
                            <Text type="secondary">文章 {source.articleCount}</Text>
                          </div>
                        </Space>
                        <Tag color={sourceStatusMeta[source.status]?.color || 'red'}>
                          {sourceStatusMeta[source.status]?.label || '异常'}
                        </Tag>
                      </div>
                      <div className="news-source-card-body">
                        <Text type="secondary">抓取时间：{formatDateTime(source.fetchedAt, '暂无记录')}</Text>
                        {source.lastError ? (
                          <Text type="danger" className="news-source-error">{source.lastError}</Text>
                        ) : (
                          <Text type="secondary">当前源可参与今日聚合。</Text>
                        )}
                      </div>
                      <div className="news-source-card-actions">
                        <Button
                          type="link"
                          size="small"
                          icon={<StickerIcon src={stickers.actions.link} alt="打开源站" size="sm" />}
                          onClick={(event) => {
                            event.stopPropagation();
                            openSourceSite(source);
                          }}
                        >
                          打开源站
                        </Button>
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="还没有配置可用的信息源" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={6}>
          <Card className="surface-card" title="热点提炼">
            {loading ? (
              <Skeleton active paragraph={{ rows: 5 }} />
            ) : visibleTopicCards.length ? (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {visibleTopicCards.map((topic) => {
                  const active = selectedTopic === topic.topic;
                  return (
                    <button
                      type="button"
                      key={topic.topic}
                      className={`news-topic-card ${active ? 'is-active' : ''}`}
                      onClick={() => setSelectedTopic((prev) => (prev === topic.topic ? 'all' : topic.topic))}
                    >
                      <div className="news-topic-card-head">
                        <span className="news-topic-name">{topic.topic}</span>
                        <Badge
                          count={topic.count}
                          color={active ? '#ff8eb8' : '#7fcbff'}
                          className="news-topic-badge"
                        />
                      </div>
                      <Text type="secondary" className="news-topic-summary">
                        {buildTopicSummary(topic)}
                      </Text>
                    </button>
                  );
                })}
              </Space>
            ) : (
              <Empty description="当前窗口没有可用热点" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={11}>
          <Card
            className="surface-card"
            title="文章流"
            extra={(
              <Space size={8} wrap>
                <Select
                  size="small"
                  value={selectedSourceId}
                  options={sourceOptions}
                  onChange={setSelectedSourceId}
                  style={{ width: 140 }}
                />
                <Select
                  size="small"
                  value={selectedTopic}
                  options={topicOptions}
                  onChange={setSelectedTopic}
                  style={{ width: 140 }}
                />
              </Space>
            )}
          >
            {loading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : visibleItems.length ? (
              <List
                dataSource={visibleItems}
                itemLayout="vertical"
                renderItem={(item) => (
                  <List.Item className="news-article-list-item">
                    <button
                      type="button"
                      className="news-article-card"
                      onClick={() => setSelectedArticle(item)}
                    >
                      <Space size={[8, 8]} wrap style={{ marginBottom: 10 }}>
                        <Tag color="blue">{item.sourceName}</Tag>
                        <Tag>{dayjs(item.publishedAt).format('MM-DD HH:mm')}</Tag>
                        {item.highlights.slice(0, 3).map((highlight) => (
                          <Tag key={highlight} color="purple">
                            {highlight}
                          </Tag>
                        ))}
                      </Space>
                      <Title level={5} style={{ marginTop: 0, marginBottom: 8 }}>
                        {item.title}
                      </Title>
                      <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 8 }}>
                        {item.summary}
                      </Paragraph>
                      {item.excerpt ? (
                        <Text type="secondary" ellipsis>
                          {item.excerpt}
                        </Text>
                      ) : null}
                    </button>
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="当前筛选条件下没有文章" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>

      <Drawer
        title={selectedArticle?.title || '文章详情'}
        open={Boolean(selectedArticle)}
        onClose={() => setSelectedArticle(null)}
        width={640}
      >
        {selectedArticle ? (
          <Space direction="vertical" size={18} style={{ width: '100%' }}>
            <Space size={[8, 8]} wrap>
              <Tag color="blue">{selectedArticle.sourceName}</Tag>
              <Tag>{dayjs(selectedArticle.publishedAt).format('MM-DD HH:mm')}</Tag>
              {selectedArticle.highlights.map((highlight) => (
                <Tag key={highlight} color="purple">
                  {highlight}
                </Tag>
              ))}
            </Space>

            <div>
              <Text strong>AI 摘要</Text>
              <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
                {selectedArticle.summary}
              </Paragraph>
            </div>

            {selectedArticle.excerpt ? (
              <div>
                <Text strong>原文摘录</Text>
                <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
                  {selectedArticle.excerpt}
                </Paragraph>
              </div>
            ) : null}

            <Space>
              <Button
                type="primary"
                icon={<StickerIcon src={stickers.actions.link} alt="查看原文" size="sm" />}
                onClick={() => window.open(selectedArticle.url, '_blank', 'noopener,noreferrer')}
              >
                查看原文
              </Button>
              <Button onClick={() => setSelectedArticle(null)}>关闭</Button>
            </Space>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
