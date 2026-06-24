import { useState } from 'react';
import {
  Globe,
  Key,
  Tag,
  Zap,
  Palette,
  Save,
  Eye,
  EyeOff,
} from 'lucide-react';
import { useLanguage, type Language } from '../i18n';

interface ApiCredential {
  name: string;
  key: string;
  connected: boolean;
}

export default function Settings() {
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState<
    'general' | 'credentials' | 'categories' | 'auto_reply' | 'brand'
  >('general');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('settings.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">
          {t('settings.subtitle')}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b">
        <TabButton
          active={activeTab === 'general'}
          onClick={() => setActiveTab('general')}
          icon={Globe}
          label={t('settings.general')}
        />
        <TabButton
          active={activeTab === 'credentials'}
          onClick={() => setActiveTab('credentials')}
          icon={Key}
          label={t('settings.apiCredentials')}
        />
        <TabButton
          active={activeTab === 'categories'}
          onClick={() => setActiveTab('categories')}
          icon={Tag}
          label={t('settings.categories')}
        />
        <TabButton
          active={activeTab === 'auto_reply'}
          onClick={() => setActiveTab('auto_reply')}
          icon={Zap}
          label={t('settings.autoReply')}
        />
        <TabButton
          active={activeTab === 'brand'}
          onClick={() => setActiveTab('brand')}
          icon={Palette}
          label={t('settings.brandStyle')}
        />
      </div>

      {/* Tab Content */}
      <div className="card p-6">
        {activeTab === 'general' && <GeneralTab />}
        {activeTab === 'credentials' && <CredentialsTab />}
        {activeTab === 'categories' && <CategoriesTab />}
        {activeTab === 'auto_reply' && <AutoReplyTab />}
        {activeTab === 'brand' && <BrandStyleTab />}
      </div>
    </div>
  );
}

function GeneralTab() {
  const { language, setLanguage, t } = useLanguage();

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">{t('settings.generalTitle')}</h3>
        <p className="text-sm text-gray-500">
          {t('settings.generalSubtitle')}
        </p>
      </div>

      <div className="rounded-lg border p-4">
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="text-sm font-medium text-gray-900">{t('settings.language')}</p>
            <p className="text-sm text-gray-500 mt-1">
              {t('settings.languageHelp')}
            </p>
          </div>
          <select
            className="input-field w-48"
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value as Language);
            }}
          >
            <option value="zh">{t('settings.languageChinese')}</option>
            <option value="en">{t('settings.languageEnglish')}</option>
          </select>
        </div>
      </div>

      <p className="text-sm text-green-600">{t('settings.languageImmediate')}</p>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof Key;
  label: string;
}) {
  return (
    <button
      className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-brand-primary text-brand-primary'
          : 'border-transparent text-gray-500 hover:text-gray-700'
      }`}
      onClick={onClick}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

function CredentialsTab() {
  const [credentials, setCredentials] = useState<ApiCredential[]>([
    { name: 'Douyin Shop API', key: 'dy_sk_****7a2b', connected: true },
    { name: 'Chanmama API', key: 'cm_****e4f1', connected: true },
    { name: 'Feigua API', key: '', connected: false },
    { name: '1688 Supplier API', key: '1688_****9c3d', connected: true },
  ]);
  const [showKeys, setShowKeys] = useState<Record<number, boolean>>({});

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">API Credentials</h3>
        <p className="text-sm text-gray-500">
          Manage your platform integrations and API keys
        </p>
      </div>
      <div className="space-y-4">
        {credentials.map((cred, index) => (
          <div key={index} className="flex items-center gap-4 p-4 border rounded-lg">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-gray-900">{cred.name}</p>
                <span
                  className={`w-2 h-2 rounded-full ${
                    cred.connected ? 'bg-green-500' : 'bg-gray-300'
                  }`}
                />
              </div>
              <div className="flex items-center gap-2 mt-1">
                <input
                  type={showKeys[index] ? 'text' : 'password'}
                  className="input-field max-w-xs text-sm"
                  placeholder="Enter API key"
                  value={cred.key}
                  onChange={(e) => {
                    const updated = [...credentials];
                    updated[index] = { ...cred, key: e.target.value };
                    setCredentials(updated);
                  }}
                />
                <button
                  className="p-2 rounded-lg hover:bg-gray-100"
                  onClick={() =>
                    setShowKeys({ ...showKeys, [index]: !showKeys[index] })
                  }
                >
                  {showKeys[index] ? (
                    <EyeOff className="w-4 h-4 text-gray-400" />
                  ) : (
                    <Eye className="w-4 h-4 text-gray-400" />
                  )}
                </button>
              </div>
            </div>
            <span
              className={`text-xs font-medium px-2 py-1 rounded-full ${
                cred.connected
                  ? 'bg-green-50 text-green-700'
                  : 'bg-gray-100 text-gray-500'
              }`}
            >
              {cred.connected ? 'Connected' : 'Not Connected'}
            </span>
          </div>
        ))}
      </div>
      <button className="btn-primary flex items-center gap-2 text-sm">
        <Save className="w-4 h-4" />
        Save Credentials
      </button>
    </div>
  );
}

function CategoriesTab() {
  const [categories, setCategories] = useState([
    { name: 'Women Clothing', enabled: true },
    { name: 'Men Clothing', enabled: false },
    { name: 'Accessories', enabled: true },
    { name: 'Shoes', enabled: true },
    { name: 'Bags', enabled: true },
    { name: 'Beauty & Skincare', enabled: true },
    { name: 'Home & Living', enabled: false },
    { name: 'Electronics', enabled: false },
    { name: 'Sports & Outdoor', enabled: false },
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Category Filters</h3>
        <p className="text-sm text-gray-500">
          Select which product categories to monitor for discovery and trending alerts
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {categories.map((cat, index) => (
          <label
            key={index}
            className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
          >
            <input
              type="checkbox"
              className="w-4 h-4 rounded border-gray-300 text-brand-primary focus:ring-brand-primary/20"
              checked={cat.enabled}
              onChange={() => {
                const updated = [...categories];
                updated[index] = { ...cat, enabled: !cat.enabled };
                setCategories(updated);
              }}
            />
            <span className="text-sm text-gray-700">{cat.name}</span>
          </label>
        ))}
      </div>
      <button className="btn-primary flex items-center gap-2 text-sm">
        <Save className="w-4 h-4" />
        Save Categories
      </button>
    </div>
  );
}

function AutoReplyTab() {
  const [rules, setRules] = useState([
    {
      name: 'Auto-reply to positive reviews',
      description: 'Automatically send thank-you replies to 4-5 star reviews',
      enabled: true,
    },
    {
      name: 'Auto-reply to shipping inquiries',
      description: 'Send tracking info when customers ask about delivery status',
      enabled: true,
    },
    {
      name: 'Escalate complaints to human',
      description: 'Route negative-sentiment feedback to human operator immediately',
      enabled: true,
    },
    {
      name: 'Auto-reply to size questions',
      description: 'Send size chart and recommendation based on product category',
      enabled: false,
    },
    {
      name: 'Weekend auto-acknowledgement',
      description: 'Send acknowledgement during non-business hours with ETA',
      enabled: true,
    },
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Auto-Reply Rules</h3>
        <p className="text-sm text-gray-500">
          Configure when AI should automatically respond to customer messages
        </p>
      </div>
      <div className="space-y-3">
        {rules.map((rule, index) => (
          <div key={index} className="flex items-center gap-4 p-4 border rounded-lg">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">{rule.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">{rule.description}</p>
            </div>
            <button
              className={`relative w-11 h-6 rounded-full transition-colors ${
                rule.enabled ? 'bg-brand-primary' : 'bg-gray-200'
              }`}
              onClick={() => {
                const updated = [...rules];
                updated[index] = { ...rule, enabled: !rule.enabled };
                setRules(updated);
              }}
            >
              <span
                className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                  rule.enabled ? 'left-[22px]' : 'left-0.5'
                }`}
              />
            </button>
          </div>
        ))}
      </div>
      <button className="btn-primary flex items-center gap-2 text-sm">
        <Save className="w-4 h-4" />
        Save Rules
      </button>
    </div>
  );
}

function BrandStyleTab() {
  const [brandColors, setBrandColors] = useState({
    primary: '#fe2c55',
    secondary: '#25f4ee',
    accent: '#161823',
  });
  const [fonts, setFonts] = useState({
    heading: 'Inter',
    body: 'Inter',
  });

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Brand Style Guide</h3>
        <p className="text-sm text-gray-500">
          Define brand colors and fonts for AI-generated design assets
        </p>
      </div>

      {/* Colors */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">Brand Colors</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Primary</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                className="w-10 h-10 rounded-lg border cursor-pointer"
                value={brandColors.primary}
                onChange={(e) =>
                  setBrandColors({ ...brandColors, primary: e.target.value })
                }
              />
              <input
                type="text"
                className="input-field text-sm"
                value={brandColors.primary}
                onChange={(e) =>
                  setBrandColors({ ...brandColors, primary: e.target.value })
                }
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Secondary</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                className="w-10 h-10 rounded-lg border cursor-pointer"
                value={brandColors.secondary}
                onChange={(e) =>
                  setBrandColors({ ...brandColors, secondary: e.target.value })
                }
              />
              <input
                type="text"
                className="input-field text-sm"
                value={brandColors.secondary}
                onChange={(e) =>
                  setBrandColors({ ...brandColors, secondary: e.target.value })
                }
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Accent</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                className="w-10 h-10 rounded-lg border cursor-pointer"
                value={brandColors.accent}
                onChange={(e) =>
                  setBrandColors({ ...brandColors, accent: e.target.value })
                }
              />
              <input
                type="text"
                className="input-field text-sm"
                value={brandColors.accent}
                onChange={(e) =>
                  setBrandColors({ ...brandColors, accent: e.target.value })
                }
              />
            </div>
          </div>
        </div>
      </div>

      {/* Fonts */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">Typography</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Heading Font</label>
            <select
              className="input-field"
              value={fonts.heading}
              onChange={(e) => setFonts({ ...fonts, heading: e.target.value })}
            >
              <option value="Inter">Inter</option>
              <option value="Poppins">Poppins</option>
              <option value="Noto Sans SC">Noto Sans SC</option>
              <option value="Source Han Sans">Source Han Sans</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Body Font</label>
            <select
              className="input-field"
              value={fonts.body}
              onChange={(e) => setFonts({ ...fonts, body: e.target.value })}
            >
              <option value="Inter">Inter</option>
              <option value="Poppins">Poppins</option>
              <option value="Noto Sans SC">Noto Sans SC</option>
              <option value="Source Han Sans">Source Han Sans</option>
            </select>
          </div>
        </div>
      </div>

      {/* Preview */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">Preview</h4>
        <div
          className="p-6 rounded-lg border-2 border-dashed"
          style={{ borderColor: brandColors.primary }}
        >
          <div className="flex items-center gap-4">
            <div
              className="w-12 h-12 rounded-lg"
              style={{ backgroundColor: brandColors.primary }}
            />
            <div
              className="w-12 h-12 rounded-lg"
              style={{ backgroundColor: brandColors.secondary }}
            />
            <div
              className="w-12 h-12 rounded-lg"
              style={{ backgroundColor: brandColors.accent }}
            />
          </div>
          <p className="mt-3 text-sm text-gray-600" style={{ fontFamily: fonts.heading }}>
            Sample heading text in {fonts.heading}
          </p>
          <p className="text-xs text-gray-400" style={{ fontFamily: fonts.body }}>
            Sample body text in {fonts.body}
          </p>
        </div>
      </div>

      <button className="btn-primary flex items-center gap-2 text-sm">
        <Save className="w-4 h-4" />
        Save Brand Style
      </button>
    </div>
  );
}
