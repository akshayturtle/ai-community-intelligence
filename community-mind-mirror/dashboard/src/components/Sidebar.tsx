import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, TrendingUp, Users, Newspaper,
  Globe, Search, ChevronLeft, ChevronRight, Brain, Lightbulb,
  Radar, Settings, Briefcase, FlaskConical,
} from "lucide-react";
import { cn } from "../lib/utils";

const links = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/topics", icon: TrendingUp, label: "Topics" },
  { to: "/people", icon: Users, label: "People" },
  { to: "/intelligence", icon: Lightbulb, label: "Intelligence" },
  { to: "/gig-board", icon: Briefcase, label: "Gig Board" },
  { to: "/research", icon: FlaskConical, label: "Research" },
  { to: "/signals", icon: Radar, label: "Signals" },
  { to: "/news", icon: Newspaper, label: "News & Research" },
  { to: "/system", icon: Settings, label: "System" },
  { to: "/geo", icon: Globe, label: "Geo" },
  { to: "/search", icon: Search, label: "Search" },
];

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

export default function Sidebar({ collapsed, onToggle }: Props) {
  return (
    <aside
      className={cn(
        "fixed left-0 top-0 h-screen bg-bg-primary border-r border-border-primary z-40 flex flex-col transition-all duration-200",
        collapsed ? "w-16" : "w-56"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-14 border-b border-border-primary">
        <Brain className="w-6 h-6 text-info shrink-0" />
        {!collapsed && (
          <span className="font-semibold text-sm text-text-primary whitespace-nowrap">
            Mind Mirror
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 space-y-1 px-2">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-bg-info text-txt-info"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
              )
            }
          >
            <l.icon className="w-5 h-5 shrink-0" />
            {!collapsed && <span>{l.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="flex items-center justify-center h-10 border-t border-border-primary text-text-tertiary hover:text-text-primary transition-colors"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}
