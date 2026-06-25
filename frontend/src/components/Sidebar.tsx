import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  Package,
  Compass,
  Palette,
  Truck,
  Settings,
  ShoppingBag,
} from 'lucide-react';
import { useLanguage } from '../i18n';

const navItems = [
  { to: '/', icon: LayoutDashboard, labelKey: 'sidebar.dashboard' },
  { to: '/feedback', icon: MessageSquare, labelKey: 'sidebar.feedback' },
  { to: '/products', icon: Package, labelKey: 'sidebar.products' },
  { to: '/discovery', icon: Compass, labelKey: 'sidebar.discovery' },
  { to: '/fulfillment', icon: Truck, labelKey: 'sidebar.fulfillment' },
  { to: '/design', icon: Palette, labelKey: 'sidebar.design' },
  { to: '/settings', icon: Settings, labelKey: 'sidebar.settings' },
];

export default function Sidebar() {
  const { t } = useLanguage();

  return (
    <aside className="flex h-[calc(100vh-2rem)] w-72 shrink-0 flex-col rounded-[32px] border border-white/10 bg-sidebar-bg/80 shadow-[0_30px_80px_rgba(8,6,26,0.4)] backdrop-blur-2xl">
      {/* Logo */}
      <div className="flex items-center gap-3 border-b border-white/10 px-6 py-6">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-primary to-brand-secondary shadow-[0_12px_30px_rgba(38,232,224,0.35)]">
          <ShoppingBag className="h-5 w-5 text-slate-950" />
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-[0.18em] text-white/90">{t('sidebar.brand.name')}</h1>
          <p className="mt-1 text-xs uppercase tracking-[0.22em] text-white/45">{t('sidebar.brand.subtitle')}</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-2 px-4 py-6">
        {navItems.map(({ to, icon: Icon, labelKey }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'border-white/15 bg-white/14 text-white shadow-[0_10px_30px_rgba(38,232,224,0.18)]'
                  : 'border-transparent text-white/58 hover:border-white/10 hover:bg-white/8 hover:text-white/88'
              }`
            }
          >
            <Icon className="h-5 w-5 text-brand-secondary transition-transform duration-200 group-hover:scale-110" />
            <span>{t(labelKey)}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-white/10 px-5 py-5">
        <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-white/35 to-white/10">
            <span className="text-xs font-semibold text-white">OP</span>
          </div>
          <div>
            <p className="text-sm font-medium text-white/92">{t('sidebar.user.role')}</p>
            <p className="text-xs text-white/45">{t('sidebar.user.title')}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
