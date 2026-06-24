import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type Language = 'en' | 'zh';

const messages: Record<Language, Record<string, string>> = {
  en: {
    'sidebar.dashboard': 'Dashboard',
    'sidebar.feedback': 'Feedback',
    'sidebar.products': 'Products',
    'sidebar.discovery': 'Discovery',
    'sidebar.design': 'Design',
    'sidebar.settings': 'Settings',
    'sidebar.brand.name': 'Douyin Shop',
    'sidebar.brand.subtitle': 'Operator Dashboard',
    'sidebar.user.role': 'Operator',
    'sidebar.user.title': 'Shop Manager',

    'dashboard.title': 'Dashboard',
    'dashboard.todayFeedback': "Today's Feedback",
    'dashboard.pendingResponses': 'Pending Responses',
    'dashboard.newListings': 'New Listings',
    'dashboard.trendAlerts': 'Trend Alerts',
    'dashboard.feedbackVolume': 'Feedback Volume (Last 7 Days)',
    'dashboard.salesPerformance': 'Sales Performance (Last 7 Days)',
    'dashboard.recentActivity': 'Recent Activity',

    'feedback.title': 'Feedback Queue',
    'feedback.subtitle': 'Manage customer feedback and AI-assisted responses',
    'feedback.avgResponseTime': 'Avg Response Time',
    'feedback.autoReplyRate': 'Auto-Reply Rate',
    'feedback.positiveSentiment': 'Positive Sentiment',
    'feedback.pendingToday': 'Pending Today',
    'filters.allStatus': 'All Status',
    'filters.allTypes': 'All Types',
    'filters.allSources': 'All Sources',
    'filters.allUrgency': 'All Urgency',
    'feedback.customer': 'Customer',
    'feedback.type': 'Type',
    'feedback.source': 'Source',
    'feedback.status': 'Status',
    'feedback.urgency': 'Urgency',
    'feedback.actions': 'Actions',
    'feedback.noItems': 'No feedback items match filters',

    'products.title': 'Products',
    'products.subtitle': 'Manage product listings and uploads',
    'products.batchUpload': 'Batch Upload',
    'products.newProduct': 'New Product',
    'products.searchPlaceholder': 'Search products...',
    'products.product': 'Product',
    'products.category': 'Category',
    'products.price': 'Price',
    'products.skus': 'SKUs',
    'products.status': 'Status',
    'products.actions': 'Actions',
    'products.noItems': 'No products match filters',

    'discovery.title': 'Product Discovery',
    'discovery.subtitle': 'AI-curated trending products and sourcing recommendations',
    'discovery.triggerScan': 'Trigger Scan',
    'discovery.scanning': 'Scanning...',
    'discovery.shortlist': "Today's Shortlist",
    'discovery.trending': 'Trending Products',
    'discovery.trendScore': 'Trend Score',
    'discovery.margin': 'Margin',
    'discovery.dailySales': 'Daily Sales',
    'discovery.supplier': 'Supplier',
    'discovery.approve': 'Approve',
    'discovery.reject': 'Reject',
    'discovery.score': 'Score',

    'design.title': 'Design Assets',
    'design.subtitle': 'AI-generated product images and marketing assets',
    'design.newTask': 'New Task',
    'design.allStatus': 'All Status',
    'design.noItems': 'No design tasks match the filter',
    'design.generating': 'Generating...',
    'design.approve': 'Approve',
    'design.regenerate': 'Regenerate',

    'settings.title': 'Settings',
    'settings.subtitle': 'Configure integrations, filters, and automation rules',
    'settings.general': 'General',
    'settings.apiCredentials': 'API Credentials',
    'settings.categories': 'Categories',
    'settings.autoReply': 'Auto-Reply',
    'settings.brandStyle': 'Brand Style',
    'settings.generalTitle': 'General Settings',
    'settings.generalSubtitle': 'Configure global preferences for the dashboard',
    'settings.language': 'Language',
    'settings.languageHelp': 'Choose the display language for the operator dashboard',
    'settings.languageEnglish': 'English',
    'settings.languageChinese': 'Chinese',
    'settings.languageImmediate': 'Changes apply immediately.',

    'status.pending': 'Pending',
    'status.ai_drafted': 'AI Drafted',
    'status.approved': 'Approved',
    'status.replied': 'Replied',
    'status.escalated': 'Escalated',
    'status.rejected': 'Rejected',
    'status.draft': 'Draft',
    'status.uploading': 'Uploading',
    'status.under_review': 'Under Review',
    'status.online': 'Online',
    'status.queued': 'Queued',
    'status.generating': 'Generating',
    'status.completed': 'Completed',
    'status.low': 'Low',
    'status.medium': 'Medium',
    'status.high': 'High',
    'status.critical': 'Critical',
    'status.complaint': 'Complaint',
    'status.inquiry': 'Inquiry',
    'status.review': 'Review',
    'status.return_request': 'Return Request',
    'status.douyin': 'Douyin',
    'status.im': 'IM',
    'status.phone': 'Phone',
  },
  zh: {
    'sidebar.dashboard': '仪表盘',
    'sidebar.feedback': '反馈',
    'sidebar.products': '商品',
    'sidebar.discovery': '选品',
    'sidebar.design': '设计',
    'sidebar.settings': '设置',
    'sidebar.brand.name': '抖店',
    'sidebar.brand.subtitle': '运营工作台',
    'sidebar.user.role': '运营员',
    'sidebar.user.title': '店铺管理员',

    'dashboard.title': '仪表盘',
    'dashboard.todayFeedback': '今日反馈',
    'dashboard.pendingResponses': '待处理回复',
    'dashboard.newListings': '新增上架',
    'dashboard.trendAlerts': '趋势提醒',
    'dashboard.feedbackVolume': '近 7 日反馈量',
    'dashboard.salesPerformance': '近 7 日销售表现',
    'dashboard.recentActivity': '最近活动',

    'feedback.title': '反馈队列',
    'feedback.subtitle': '管理客户反馈与 AI 辅助回复',
    'feedback.avgResponseTime': '平均响应时间',
    'feedback.autoReplyRate': '自动回复率',
    'feedback.positiveSentiment': '正向情绪占比',
    'feedback.pendingToday': '今日待处理',
    'filters.allStatus': '全部状态',
    'filters.allTypes': '全部类型',
    'filters.allSources': '全部来源',
    'filters.allUrgency': '全部紧急度',
    'feedback.customer': '客户',
    'feedback.type': '类型',
    'feedback.source': '来源',
    'feedback.status': '状态',
    'feedback.urgency': '紧急度',
    'feedback.actions': '操作',
    'feedback.noItems': '没有符合筛选条件的反馈',

    'products.title': '商品',
    'products.subtitle': '管理商品上架与上传',
    'products.batchUpload': '批量上传',
    'products.newProduct': '新建商品',
    'products.searchPlaceholder': '搜索商品...',
    'products.product': '商品',
    'products.category': '类目',
    'products.price': '价格',
    'products.skus': 'SKU 数',
    'products.status': '状态',
    'products.actions': '操作',
    'products.noItems': '没有符合筛选条件的商品',

    'discovery.title': '商品发现',
    'discovery.subtitle': 'AI 精选趋势商品与货源推荐',
    'discovery.triggerScan': '触发扫描',
    'discovery.scanning': '扫描中...',
    'discovery.shortlist': '今日候选清单',
    'discovery.trending': '趋势商品',
    'discovery.trendScore': '趋势分',
    'discovery.margin': '利润率',
    'discovery.dailySales': '日销量',
    'discovery.supplier': '供应商',
    'discovery.approve': '通过',
    'discovery.reject': '拒绝',
    'discovery.score': '评分',

    'design.title': '设计素材',
    'design.subtitle': 'AI 生成商品图片与营销素材',
    'design.newTask': '新建任务',
    'design.allStatus': '全部状态',
    'design.noItems': '没有符合筛选条件的设计任务',
    'design.generating': '生成中...',
    'design.approve': '通过',
    'design.regenerate': '重新生成',

    'settings.title': '设置',
    'settings.subtitle': '配置集成、筛选项与自动化规则',
    'settings.general': '通用',
    'settings.apiCredentials': 'API 凭证',
    'settings.categories': '类目',
    'settings.autoReply': '自动回复',
    'settings.brandStyle': '品牌风格',
    'settings.generalTitle': '通用设置',
    'settings.generalSubtitle': '配置工作台的全局偏好',
    'settings.language': '语言',
    'settings.languageHelp': '选择运营工作台的显示语言',
    'settings.languageEnglish': '英文',
    'settings.languageChinese': '中文',
    'settings.languageImmediate': '修改会立即生效。',

    'status.pending': '待处理',
    'status.ai_drafted': 'AI 草稿',
    'status.approved': '已通过',
    'status.replied': '已回复',
    'status.escalated': '已升级',
    'status.rejected': '已拒绝',
    'status.draft': '草稿',
    'status.uploading': '上传中',
    'status.under_review': '审核中',
    'status.online': '在线',
    'status.queued': '排队中',
    'status.generating': '生成中',
    'status.completed': '已完成',
    'status.low': '低',
    'status.medium': '中',
    'status.high': '高',
    'status.critical': '紧急',
    'status.complaint': '投诉',
    'status.inquiry': '咨询',
    'status.review': '评价',
    'status.return_request': '退货请求',
    'status.douyin': '抖音',
    'status.im': 'IM',
    'status.phone': '电话',
  },
};

interface I18nContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    const storedLanguage = localStorage.getItem('settings.language');
    return storedLanguage === 'en' ? 'en' : 'zh';
  });

  useEffect(() => {
    localStorage.setItem('settings.language', language);
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  }, [language]);

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage: setLanguageState,
      t: (key: string) => messages[language][key] ?? messages.en[key] ?? key,
    }),
    [language]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useLanguage() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider');
  }
  return context;
}
