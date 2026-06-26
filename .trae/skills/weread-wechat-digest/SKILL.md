---
name: "weread-wechat-digest"
description: "Extracts WeRead shelf公众号 articles within a time window, reads and summarizes them, and outputs Markdown. Invoke when user asks to pull 微信读书/公众号文章, filter by time range, or generate summaries/links."
---

# WeRead WeChat Digest

这个 Skill 用于复用当前项目里已经验证过的一套流程：从微信读书书架中的“公众号书籍”抓取指定时间窗内的文章，读取正文，提炼一句话摘要，并整理成 Markdown 文件。

## 适用场景

在以下场景调用：

- 用户要求进入 `https://weread.qq.com/web/shelf`
- 用户要求从书架里的公众号来源抓文章
- 用户要求按时间窗口筛选文章，例如“昨天早 9 点到今天早 9 点”
- 用户要求对每篇文章读取正文并生成一句话摘要
- 用户要求导出为 Markdown，并把链接做成超链接

不适用场景：

- 普通网页新闻抓取，不经过微信读书书架
- 只需要单篇文章摘要，不需要批量书架扫描
- 需要原始 `mp.weixin.qq.com` 链接且当前工具链无法稳定暴露原链时

## 已验证工作流

### 1. 进入微信读书书架

- 优先复用用户当前 Chrome 会话和登录态
- 打开 `https://weread.qq.com/web/shelf`
- 识别书架中的公众号来源卡片

已验证可通过书架页拿到公众号“书籍”入口。

### 2. 识别公众号 bookId

公众号来源在微信读书里本质上是 `MP_WXS_*` 形式的 book：

- 可从书架链接、页面资源或 `/web/book/info` 推导 `bookId`
- 例如：`MP_WXS_3271041950`

必要时可调用：

- `/web/book/info?bookId=<bookId>`

用于确认公众号名称、更新时间、编码信息。

### 3. 拉取文章目录

核心目录接口：

```text
/web/mp/articles?bookId=<bookId>&offset=<offset>
```

规则：

- 必须在有微信读书登录态的浏览器上下文中调用
- `offset` 从 `0` 开始，按返回分组条目数量递增
- 每次响应里主要关注：
  - `reviews`
  - `createTime`
  - `subReviews`
  - `subReviews[].reviewId`
  - `subReviews[].review.mpInfo.title`
  - `subReviews[].review.mpInfo.time`

分页停止条件：

- 返回 `reviews` 为空
- 或最后一组的时间已经早于目标时间窗起点
- 或用户只要求最新一批文章

## 时间窗筛选规范

默认做法：

- 统一按北京时间处理
- 时间窗使用左闭右开：`[start, end)`
- 优先使用 `mpInfo.time`
- 如果缺失，再回退到 `review.createTime` 或组级 `createTime`

例子：

- “前一天早 9 点到今早 9 点” 对应：
  - `start = 昨天 09:00:00 +08:00`
  - `end = 今天 09:00:00 +08:00`

注意：

- 同一批多图文下多篇文章通常共享同一个推送时间
- 输出里应明确写明“时间为微信读书目录里的推送时间”

## 4. 读取文章正文

正文页接口：

```text
/web/mp/content?reviewId=<reviewId>
```

读取策略：

- 在微信读书同源环境中请求 HTML
- 从 HTML 中提取：
  - 标题：`msg_title` 或 `og:title`
  - 时间：`ct`
  - 正文主内容：`#img-content`、`.rich_media_content`、`#js_content`、`article` 等容器
- 需要清洗：
  - 连续空白
  - 阅读器提示文案
  - 多余脚本和样式节点

## 5. 一句话摘要规范

摘要要求：

- 每篇只写一句
- 先交代核心对象，再交代核心动作或结论
- 不复述标题，不堆砌形容词
- 能看出“这篇文章讲了什么”，不是只说“文章介绍了”

推荐句式：

- “文章以 X 为例，说明 Y 如何 Z。”
- “文章从 A、B、C 出发，分析 D 的可能性/影响。”
- “这是一篇招聘帖，核心是在 X 背景下招募 Y 岗位。”

质量要求：

- 摘要必须来源于正文，不凭空补事实
- 如果是招聘帖、纪要、论文介绍，要显式写明类型
- 对投资/产业信息，优先保留公司、技术路线、商业化结论

## 6. 链接规范

优先级：

1. 微信读书可稳定访问链接  
   `https://weread.qq.com/web/mp/content?reviewId=<reviewId>`
2. 如果工具链能稳定抽到原始公众号链接，再补充原始链接字段

在当前项目里，默认使用微信读书链接，因为它稳定且不受当前输出脱敏影响。

Markdown 超链接规范：

- 若用户要求“超链接文本用摘要”，则用一句话摘要作为链接文本
- 若用户要求“保留原标题方便扫读”，则使用两行结构：

```md
- 2026-06-25 12:04 | 原标题
  [一句话摘要。](https://weread.qq.com/web/mp/content?reviewId=...)
```

- 若用户要求更紧凑，可只保留：

```md
- 2026-06-25 12:04 | [一句话摘要。](https://weread.qq.com/web/mp/content?reviewId=...)
```

## 7. 输出规范

默认输出文件为项目根目录下的 Markdown，例如：

```text
weread_articles_<start>_to_<end>.md
```

建议文件结构：

```md
# 微信读书公众号文章汇总

时间范围：`...` 到 `...`

说明：下列时间为微信读书目录里的`推送时间`；同一批多图文推送下的多篇文章，时间会相同。

## 公众号 A

- 时间 | 原标题
  [一句话摘要超链接](...)

共 N 篇。
```

收尾应包含：

- 每个公众号的篇数
- 总篇数

## 当前项目里已经验证过的输出能力

这套流程已经完成过以下任务：

- 从微信读书书架识别公众号来源
- 获取各公众号的 `bookId`
- 按时间窗拉取公众号文章目录
- 读取正文并生成一句话摘要
- 输出 Markdown 文件
- 支持把超链接文本改成摘要而不是原标题

## 操作注意事项

- 不要依赖普通 `curl` 直拉目录接口，通常会失去微信读书登录态
- 优先使用浏览器上下文中的请求能力
- Tab ID 可能失效，必要时先重新枚举当前 Chrome 窗口和标签页
- 如果 `mp.weixin.qq.com` 原链被工具脱敏，不要伪造；直接回退到微信读书稳定链接
- 修改 Markdown 时，如果 Unicode 上下文导致补丁失败，可删除后按最终内容重建文件

## 最小执行清单

1. 连接用户当前微信读书登录态
2. 打开书架并确认公众号来源
3. 获取每个来源的 `bookId`
4. 用 `/web/mp/articles` 分页拉取目录
5. 依据目标时间窗筛选文章
6. 用 `/web/mp/content` 读取正文
7. 生成一句话摘要
8. 按用户指定格式输出 Markdown

## 示例触发词

- “进入微信读书书架，抓昨天到今天的公众号文章”
- “把每个公众号在某个时间窗内的文章导出来”
- “读取这些微信读书公众号文章并总结成一句话”
- “把链接做成摘要超链接，输出到 md”
