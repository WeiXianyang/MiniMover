import { NavLink, useLocation } from 'react-router-dom';
import { Activity, Flame } from 'lucide-react';

const navItems = [
  { to: '/', label: '告警总览', icon: Activity, end: true },
];

export default function Sidebar() {
  const location = useLocation();
  const isDetail = location.pathname.startsWith('/alarm/');

  return (
    <aside className="w-[252px] min-h-screen flex-shrink-0 border-r border-line bg-surface flex flex-col">
      {/* Brand */}
      <div className="px-5 pt-6 pb-4 flex items-center gap-3">
        <div className="w-[42px] h-[42px] rounded-lg bg-panel-2 border border-accent/30 flex items-center justify-center">
          <Flame className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-text tracking-wide">FireGuard Cloud</h1>
          <p className="text-[11px] text-muted">烟火告警云平台</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active =
            item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);

          return (
            <NavLink
              key={item.label}
              to={item.to}
              end={item.end}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] transition-colors ${
                active || isDetail
                  ? 'bg-accent/10 text-accent'
                  : 'text-muted hover:text-text hover:bg-panel-2'
              }`}
            >
              <Icon className="w-[17px] h-[17px]" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* API info */}
      <div className="px-4 py-4 mx-3 mb-4 rounded-lg bg-panel border border-line">
        <div className="flex items-center gap-2 mb-1.5">
          <Flame className="w-3.5 h-3.5 text-accent" />
          <span className="text-[11px] font-medium text-muted uppercase tracking-wider">API</span>
        </div>
        <p className="text-[12px] text-text font-mono">8.140.28.233:8000</p>
        <p className="text-[11px] text-muted-2 font-mono mt-0.5">GET /api/v1/fire-alarms</p>
      </div>
    </aside>
  );
}
