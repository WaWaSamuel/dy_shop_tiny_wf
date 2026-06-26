import { useState } from 'react';
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
} from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

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
}

const mockVersions: VersionCard[] = [
  { id: 'v1', thumbnail: 'https://via.placeholder.com/200x200/667eea/fff?text=V1', prompt: '简约风格产品主图，白色背景', engine: 'DALL-E 3', timestamp: '2024-06-01 10:30', starred: true, status: 'completed' },
  { id: 'v2', thumbnail: 'https://via.placeholder.com/200x200/764ba2/fff?text=V2', prompt: '生活场景使用图，温馨家居风', engine: 'Midjourney v6', timestamp: '2024-06-01 11:15', starred: false, status: 'completed' },
  { id: 'v3', thumbnail: 'https://via.placeholder.com/200x200/f093fb/fff?text=V3', prompt: '户外运动场景，活力青年', engine: 'Stable Diffusion XL', timestamp: '2024-06-01 14:00', starred: false, status: 'completed' },
  { id: 'v4', thumbnail: 'https://via.placeholder.com/200x200/4facfe/fff?text=V4', prompt: '节日促销海报，红色喜庆', engine: 'DALL-E 3', timestamp: '2024-06-01 15:30', starred: true, status: 'completed' },
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

export default function CreativeStudio() {
  const [selectedCategory, setSelectedCategory] = useState<string>('main_image');
  const [selectedPipeline, setSelectedPipeline] = useState<string>('text2img');
  const [selectedEngine, setSelectedEngine] = useState<string>('dalle3');
  const [prompt, setPrompt] = useState('');
  const [selectedWords, setSelectedWords] = useState<string[]>(['高清', '白色背景']);
  const [versions, setVersions] = useState<VersionCard[]>(mockVersions);
  const [selectedVersion, setSelectedVersion] = useState<string>('v1');

  const handleGenerate = () => {
    const fullPrompt = [...selectedWords, prompt].filter(Boolean).join('，');
    console.log('Generating with:', { selectedCategory, selectedPipeline, selectedEngine, fullPrompt });
  };

  const toggleStar = (id: string) => {
    setVersions((prev) =>
      prev.map((v) => (v.id === id ? { ...v, starred: !v.starred } : v))
    );
  };

  return (
    <div>
      <Card className="surface-card" style={{ marginBottom: 24 }}>
        <Alert
          type="info"
          showIcon={false}
          message="建议先在抖掌柜完成上架，再把货品 Excel 导入工作台；素材工坊负责为这些已确认货品补图、详情页和广告素材。"
        />
      </Card>

      <Row gutter={24}>
        {/* Left config panel */}
        <Col xs={24} lg={7}>
          <Card title="生成配置" size="small">
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
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
                  生成管线
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
                  AI 引擎
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
                  创意描述
                </Text>
                <TextArea
                  rows={4}
                  placeholder="描述你想要生成的素材内容..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                />
              </div>

              <Button
                type="primary"
                icon={<StickerIcon src={stickers.actions.generate} alt="生成素材" size="sm" />}
                block
                size="large"
                onClick={handleGenerate}
              >
                生成素材
              </Button>
            </Space>
          </Card>
        </Col>

        {/* Center preview area */}
        <Col xs={24} lg={17}>
          <Card
            title="版本预览"
            extra={
              <Space>
                <Tag icon={<StickerIcon src={stickers.actions.image} alt="版本预览" size="xs" />} color="blue">
                  {versions.length} 个版本
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
          </Card>

          {/* Bottom version timeline */}
          <Card
            title="生成历史"
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
