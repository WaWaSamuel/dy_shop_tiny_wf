import { useMemo, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Typography,
  Select,
  Input,
  Button,
  Checkbox,
  Space,
  Tag,
  Divider,
  Image,
  Timeline,
  Tooltip,
  Alert,
  Descriptions,
  message,
} from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';
import { mockGenerateCreative } from '@/services/creativeApi';

const { Text } = Typography;
const { TextArea } = Input;

interface VersionCard {
  id: string;
  thumbnail: string;
  prompt: string;
  engine: string;
  timestamp: string;
  starred: boolean;
  status: 'generating' | 'completed' | 'failed';
  category: string;
  pipeline: string;
}

const mockVersions: VersionCard[] = [
  { id: 'v1', thumbnail: 'https://via.placeholder.com/200x200/667eea/fff?text=V1', prompt: '简约风格产品主图，白色背景', engine: 'DALL-E 3', timestamp: '2024-06-01 10:30', starred: true, status: 'completed', category: 'main_image', pipeline: 'text2img' },
  { id: 'v2', thumbnail: 'https://via.placeholder.com/200x200/764ba2/fff?text=V2', prompt: '生活场景使用图，温馨家居风', engine: 'Midjourney v6', timestamp: '2024-06-01 11:15', starred: false, status: 'completed', category: 'detail_page', pipeline: 'img2img' },
  { id: 'v3', thumbnail: 'https://via.placeholder.com/200x200/f093fb/fff?text=V3', prompt: '户外运动场景，活力青年', engine: 'Stable Diffusion XL', timestamp: '2024-06-01 14:00', starred: false, status: 'completed', category: 'social_post', pipeline: 'text2img' },
  { id: 'v4', thumbnail: 'https://via.placeholder.com/200x200/4facfe/fff?text=V4', prompt: '节日促销海报，红色喜庆', engine: 'DALL-E 3', timestamp: '2024-06-01 15:30', starred: true, status: 'completed', category: 'ad_banner', pipeline: 'text2img' },
];

const categoryOptions = [
  { value: 'main_image', label: '商品主图' },
  { value: 'detail_page', label: '详情页' },
  { value: 'video_cover', label: '视频封面' },
  { value: 'ad_banner', label: '广告素材' },
  { value: 'social_post', label: '社媒图文' },
];

const pipelineOptions = [
  { value: 'text2img', label: '文生图' },
  { value: 'img2img', label: '图生图' },
  { value: 'inpaint', label: '局部重绘' },
  { value: 'upscale', label: '超分辨率' },
  { value: 'video', label: '视频生成' },
];

const engineOptions = [
  { value: 'dalle3', label: 'DALL-E 3' },
  { value: 'midjourney', label: 'Midjourney v6' },
  { value: 'sdxl', label: 'Stable Diffusion XL' },
  { value: 'flux', label: 'Flux.1 Pro' },
];

const systemWords = [
  '高清', '4K', '专业摄影', '白色背景', '柔光',
  '产品特写', '生活场景', '模特展示', '俯拍', '侧拍',
];

const statusTagColor: Record<VersionCard['status'], string> = {
  generating: 'processing',
  completed: 'success',
  failed: 'error',
};

export default function CreativeStudio() {
  const [selectedCategory, setSelectedCategory] = useState<string>('main_image');
  const [selectedPipeline, setSelectedPipeline] = useState<string>('text2img');
  const [selectedEngine, setSelectedEngine] = useState<string>('dalle3');
  const [prompt, setPrompt] = useState('');
  const [selectedWords, setSelectedWords] = useState<string[]>(['高清', '白色背景']);
  const [versions, setVersions] = useState<VersionCard[]>(mockVersions);
  const [selectedVersion, setSelectedVersion] = useState<string>('v1');
  const [isGenerating, setIsGenerating] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  const categoryLabelMap = useMemo(
    () => Object.fromEntries(categoryOptions.map((item) => [item.value, item.label])),
    []
  );
  const pipelineLabelMap = useMemo(
    () => Object.fromEntries(pipelineOptions.map((item) => [item.value, item.label])),
    []
  );
  const engineLabelMap = useMemo(
    () => Object.fromEntries(engineOptions.map((item) => [item.value, item.label])),
    []
  );
  const selectedVersionDetail = useMemo(
    () => versions.find((item) => item.id === selectedVersion) || null,
    [selectedVersion, versions]
  );
  const resultSummary = useMemo(() => {
    const completed = versions.filter((item) => item.status === 'completed').length;
    const starred = versions.filter((item) => item.starred).length;
    const latest = versions[0];
    return {
      total: versions.length,
      completed,
      starred,
      latestLabel: latest ? `${latest.engine} · ${latest.timestamp}` : '暂无结果',
    };
  }, [versions]);

  const handleRefreshCreativeResults = async () => {
    const fullPrompt = [...selectedWords, prompt].filter(Boolean).join('，');
    if (!fullPrompt) {
      messageApi.warning('请先补充筛选描述或选择关键词');
      return;
    }

    setIsGenerating(true);
    const engineLabel = engineLabelMap[selectedEngine] || selectedEngine;
    try {
      const response = await mockGenerateCreative({
        category: selectedCategory,
        pipeline: selectedPipeline,
        engine: engineLabel,
        prompt,
        systemWords: selectedWords,
      });

      const drafts: VersionCard[] = response.versions.map((item) => ({
        id: item.id,
        thumbnail: item.thumbnail,
        prompt: item.prompt,
        engine: item.engine,
        timestamp: new Date(item.timestamp).toLocaleString('zh-CN', {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        }),
        starred: item.starred,
        status: item.status,
        category: item.category,
        pipeline: item.pipeline,
      }));

      setVersions((prev) => [...drafts, ...prev]);
      setSelectedVersion(drafts[0]?.id || selectedVersion);
      messageApi.success(`已同步最新素材结果：${response.summary}`);
    } catch (error) {
      console.error(error);
      messageApi.error('素材结果同步失败');
    } finally {
      setIsGenerating(false);
    }
  };

  const toggleStar = (id: string) => {
    setVersions((prev) =>
      prev.map((v) => (v.id === id ? { ...v, starred: !v.starred } : v))
    );
  };

  return (
    <div>
      {contextHolder}
      <Card className="surface-card" style={{ marginBottom: 24 }}>
        <Alert
          type="info"
          showIcon={false}
          message="素材工坊现在按结果展示台来使用：这里主要查看已回流的素材结果、挑选可用版本、补充复看备注，而不是在页面里直接承担生成执行。"
        />
      </Card>

      <Row gutter={24}>
        <Col xs={24} lg={7}>
          <Card title="结果筛选与同步" size="small">
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Card size="small" bordered={false} style={{ background: 'rgba(255,240,246,0.72)', borderRadius: 18 }}>
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Text strong>当前素材结果摘要</Text>
                  <Text type="secondary">已回流结果 {resultSummary.total} 份，已完成 {resultSummary.completed} 份，收藏 {resultSummary.starred} 份。</Text>
                  <Tag color="magenta" style={{ width: 'fit-content', borderRadius: 999 }}>
                    最近结果：{resultSummary.latestLabel}
                  </Tag>
                </Space>
              </Card>

              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                  素材类别
                </Text>
                <Select
                  style={{ width: '100%' }}
                  value={selectedCategory}
                  onChange={setSelectedCategory}
                  options={categoryOptions}
                />
              </div>

              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                  结果来源管线
                </Text>
                <Select
                  style={{ width: '100%' }}
                  value={selectedPipeline}
                  onChange={setSelectedPipeline}
                  options={pipelineOptions}
                />
              </div>

              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                  结果引擎
                </Text>
                <Select
                  style={{ width: '100%' }}
                  value={selectedEngine}
                  onChange={setSelectedEngine}
                  options={engineOptions}
                />
              </div>

              <Divider style={{ margin: '8px 0' }} />

              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                  系统关键词
                </Text>
                <Checkbox.Group
                  value={selectedWords}
                  onChange={(vals) => setSelectedWords(vals as string[])}
                >
                  <Row gutter={[8, 8]}>
                    {systemWords.map((word) => (
                      <Col span={12} key={word}>
                        <Checkbox value={word}>{word}</Checkbox>
                      </Col>
                    ))}
                  </Row>
                </Checkbox.Group>
              </div>

              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                  复看备注 / 筛选描述
                </Text>
                <TextArea
                  rows={4}
                  placeholder="写下你想优先复看的素材方向，例如：更柔和、更像主图、更适合详情页..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                />
              </div>

              <Button
                type="primary"
                icon={<StickerIcon src={stickers.actions.retry} alt="同步素材结果" size="sm" />}
                block
                size="large"
                loading={isGenerating}
                onClick={handleRefreshCreativeResults}
              >
                同步最新素材结果
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={17}>
          <Card
            title="素材结果预览"
            extra={
              <Space>
                <Tag icon={<StickerIcon src={stickers.actions.image} alt="素材结果预览" size="xs" />} color="blue">
                  {versions.length} 份结果
                </Tag>
              </Space>
            }
          >
            <Row gutter={[16, 16]}>
              {versions.map((ver) => (
                <Col xs={12} sm={8} md={6} key={ver.id}>
                  <Card
                    hoverable
                    size="small"
                    style={{
                      borderColor: selectedVersion === ver.id ? '#1677ff' : undefined,
                      borderWidth: selectedVersion === ver.id ? 2 : 1,
                    }}
                    onClick={() => setSelectedVersion(ver.id)}
                    cover={
                      <div style={{ position: 'relative' }}>
                        <Image
                          src={ver.thumbnail}
                          preview={false}
                          style={{ width: '100%', aspectRatio: '1', objectFit: 'cover' }}
                        />
                        <Tag
                          color={statusTagColor[ver.status]}
                          style={{ position: 'absolute', top: 8, left: 8, margin: 0 }}
                        >
                          {ver.status === 'generating' ? '生成中' : ver.status === 'completed' ? '已完成' : '失败'}
                        </Tag>
                        <Tooltip title={ver.starred ? '取消收藏' : '收藏'}>
                          <Button
                            type="text"
                            size="small"
                            icon={<StickerIcon src={stickers.actions.star} alt="收藏" size="sm" />}
                            style={{ position: 'absolute', top: 4, right: 4 }}
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleStar(ver.id);
                            }}
                          />
                        </Tooltip>
                      </div>
                    }
                  >
                    <Card.Meta
                      title={<Text style={{ fontSize: 12 }}>{ver.engine}</Text>}
                      description={
                        <Text type="secondary" style={{ fontSize: 11 }} ellipsis>
                          {ver.prompt}
                        </Text>
                      }
                    />
                  </Card>
                </Col>
              ))}
            </Row>

            {selectedVersionDetail && (
              <Card size="small" style={{ marginTop: 16, background: 'rgba(255,255,255,0.58)' }}>
                <Descriptions size="small" column={2} bordered>
                  <Descriptions.Item label="当前结果">{selectedVersionDetail.id}</Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color={statusTagColor[selectedVersionDetail.status]}>
                      {selectedVersionDetail.status === 'generating' ? '生成中' : selectedVersionDetail.status === 'completed' ? '已完成' : '失败'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="素材类别">
                    {categoryLabelMap[selectedVersionDetail.category] || selectedVersionDetail.category}
                  </Descriptions.Item>
                  <Descriptions.Item label="生成管线">
                    {pipelineLabelMap[selectedVersionDetail.pipeline] || selectedVersionDetail.pipeline}
                  </Descriptions.Item>
                  <Descriptions.Item label="引擎">{selectedVersionDetail.engine}</Descriptions.Item>
                  <Descriptions.Item label="时间">{selectedVersionDetail.timestamp}</Descriptions.Item>
                  <Descriptions.Item label="提示词" span={2}>
                    {selectedVersionDetail.prompt}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            )}
          </Card>

          {/* Bottom version timeline */}
          <Card
            title="结果时间线"
            size="small"
            style={{ marginTop: 16 }}
            extra={<StickerIcon src={stickers.actions.history} alt="生成历史" size="sm" />}
          >
            <Timeline
              mode="left"
              items={versions.map((ver) => ({
                color: ver.status === 'completed' ? 'green' : ver.status === 'generating' ? 'blue' : 'red',
                label: ver.timestamp,
                children: (
                  <Space>
                    <Tag>{ver.engine}</Tag>
                    <Text style={{ fontSize: 12 }}>{ver.prompt}</Text>
                  </Space>
                ),
              }))}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
