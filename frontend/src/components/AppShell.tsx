import { useState, useEffect } from "react";
import {
  Home, MessageSquare, Zap, ClipboardList,
  BookOpen, Monitor, Terminal, BarChart3, Settings,
  LogOut, Clock, User as UserIcon, Sparkles, Bell, ChevronRight,
  Menu, X
} from "lucide-react";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────
interface AppShellProps {
  user: any;
  activeView: string;
  setActiveView: (view: any) => void;
  handleLogout: () => void;
  currentTime: string;
  children: React.ReactNode;
}

type NavEntry =
  | { type: "item"; key: string; label: string; icon: React.ReactNode; badge?: string }
  | { type: "divider"; label?: string };

// ─────────────────────────────────────────────────────────────
// Navigation definitions
// ─────────────────────────────────────────────────────────────
const CORE: NavEntry[] = [
  { type: "item", key: "dashboard",  label: "Home",       icon: <Home        className="w-3.5 h-3.5" /> },
  { type: "item", key: "support",    label: "IT Support",  icon: <MessageSquare className="w-3.5 h-3.5" /> },
  { type: "item", key: "actions",    label: "IT Actions",  icon: <Zap         className="w-3.5 h-3.5" /> },
  { type: "item", key: "my_tickets", label: "My Tickets",  icon: <ClipboardList className="w-3.5 h-3.5" /> },
];

const ADMIN_TOOLS: NavEntry[] = [
  { type: "item", key: "kb",               label: "Knowledge Base",    icon: <BookOpen  className="w-3.5 h-3.5" /> },
  { type: "item", key: "devices",          label: "Enterprise Devices", icon: <Monitor   className="w-3.5 h-3.5" /> },
  { type: "item", key: "execution_center", label: "Execution Center",  icon: <Terminal  className="w-3.5 h-3.5" /> },
];

const manager_portal: NavEntry = {
  type: "item", key: "manager_portal", label: "Manager Portal", icon: <Sparkles className="w-3.5 h-3.5" />
};

const itsm_queue: NavEntry = {
  type: "item", key: "itsm_queue", label: "ITSM Queue", icon: <ClipboardList className="w-3.5 h-3.5" />
};

const analytics: NavEntry = { type: "item", key: "analytics", label: "Analytics", icon: <BarChart3 className="w-3.5 h-3.5" /> };
const settings:  NavEntry = { type: "item", key: "settings",  label: "Settings",  icon: <Settings  className="w-3.5 h-3.5" /> };

function getNavEntries(role: string): NavEntry[] {
  const r = role?.toLowerCase();

  if (r === "admin") {
    return [
      ...CORE,
      { type: "divider", label: "Administration" },
      manager_portal,
      itsm_queue,
      ...ADMIN_TOOLS,
      { type: "divider", label: "System" },
      analytics,
      settings,
    ];
  }
  if (r === "manager") {
    return [
      ...CORE,
      { type: "divider", label: "Management" },
      manager_portal,
      { type: "divider", label: "System" },
      analytics,
    ];
  }
  return CORE;
}

// Role badge styling
function roleBadgeCls(role?: string): string {
  const r = (role || "").toLowerCase();
  if (r === "admin")   return "bg-red-50 text-red-700 border border-red-200";
  if (r === "manager") return "bg-purple-50 text-purple-700 border border-purple-200";
  return "bg-blue-50 text-blue-700 border border-blue-200";
}

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────
export default function AppShell({
  user,
  activeView,
  setActiveView,
  handleLogout,
  currentTime,
  children,
}: AppShellProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setIsCollapsed(true);
      } else {
        setIsCollapsed(false);
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const entries = getNavEntries(user?.role || "employee");
  const displayName = user?.username
    ? user.username.charAt(0).toUpperCase() + user.username.slice(1)
    : "User";

  const renderNav = (isExpanded: boolean, onSelect?: () => void) => {
    return (
      <nav className="flex flex-col gap-0.5 px-2 overflow-y-auto" aria-label="Main navigation">
        {entries.map((entry, idx) => {
          if (entry.type === "divider") {
            if (!isExpanded) return <div key={`divider-${idx}`} className="border-t border-[#F1F5F9] my-2 mx-2" />;
            return (
              <div key={`divider-${idx}`} className="mx-2 mt-3 mb-1.5">
                {entry.label ? (
                  <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-[#94A3B8] px-1">
                    {entry.label}
                  </span>
                ) : (
                  <div className="border-t border-[#F1F5F9]" />
                )}
              </div>
            );
          }

          const isActive = activeView === entry.key;
          return (
            <button
              key={entry.key}
              onClick={() => {
                setActiveView(entry.key as any);
                if (onSelect) onSelect();
              }}
              aria-current={isActive ? "page" : undefined}
              title={!isExpanded ? entry.label : undefined}
              className={`
                w-full flex items-center rounded-lg py-2 transition-all duration-100 cursor-pointer
                focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#E30613]
                ${isExpanded ? "px-3 gap-2.5 text-left" : "justify-center px-0"}
                ${isActive
                  ? "bg-[#FEF2F2] text-[#E30613] font-semibold"
                  : "text-[#475569] hover:bg-[#F8FAFC] hover:text-[#1E293B]"
                }
              `}
            >
              <span className={`flex-shrink-0 transition-colors ${isActive ? "text-[#E30613]" : "text-[#94A3B8]"}`} aria-hidden>
                {entry.icon}
              </span>

              {isExpanded && (
                <>
                  <span className="truncate flex-1 text-[12px] font-medium">{entry.label}</span>
                  {isActive && (
                    <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-[#E30613]" aria-hidden />
                  )}
                </>
              )}
            </button>
          );
        })}
      </nav>
    );
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#F8FAFC] font-sans">

      {/* ════════════════════════════════════════════════════════
          TOP HEADER
          ════════════════════════════════════════════════════════ */}
      <header className="flex-shrink-0 h-[52px] bg-white border-b border-[#E2E8F0] flex items-center justify-between px-5 z-20 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">

        {/* Brand & Toggle */}
        <div className="flex items-center gap-2">
          {/* Hamburger Menu (Mobile only) */}
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="md:hidden p-1.5 rounded-lg text-[#64748B] hover:text-[#1E293B] hover:bg-[#F1F5F9] transition-all cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#E30613]"
            aria-label="Open navigation"
          >
            <Menu className="w-4 h-4" />
          </button>
          
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[#E30613] flex items-center justify-center shadow-sm">
              <Sparkles className="w-3.5 h-3.5 text-white" />
            </div>
            <div className="leading-none">
              <span className="text-[13px] font-bold text-[#0F172A] tracking-tight block">
                Bridgestone IT
              </span>
              <span className="text-[9px] text-[#94A3B8] font-semibold uppercase tracking-wider mt-0.5 block">
                Enterprise Portal
              </span>
            </div>
          </div>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-2">

          {/* Clock */}
          <div className="hidden lg:flex items-center gap-1.5 text-[11px] text-[#64748B] font-mono bg-[#F8FAFC] border border-[#E2E8F0] px-2.5 py-1.5 rounded-lg">
            <Clock className="w-3 h-3 text-[#E30613]" aria-hidden />
            <span>{currentTime}</span>
          </div>

          {/* Notification bell */}
          <button
            className="relative p-2 rounded-lg text-[#64748B] hover:text-[#1E293B] hover:bg-[#F1F5F9] transition-all cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#E30613]"
            title="Notifications"
            aria-label="View notifications"
          >
            <Bell className="w-4 h-4" />
            <span
              className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-[#E30613] rounded-full ring-1 ring-white"
              aria-label="You have new notifications"
            />
          </button>

          {/* User chip */}
          <div className="flex items-center gap-2 bg-[#F8FAFC] border border-[#E2E8F0] px-2.5 py-1.5 rounded-lg">
            <div className="w-5 h-5 rounded-full bg-[#FEF2F2] border border-[#FCA5A5] flex items-center justify-center flex-shrink-0">
              <UserIcon className="w-3 h-3 text-[#E30613]" aria-hidden />
            </div>
            <span className="text-[12px] font-semibold text-[#1E293B] leading-none">
              {displayName}
            </span>
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide ${roleBadgeCls(user?.role)}`}>
              {user?.role}
            </span>
          </div>

          {/* Sign out */}
          <button
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
            className="flex items-center gap-1.5 text-[11px] text-[#64748B] hover:text-[#E30613] transition-colors px-2.5 py-1.5 rounded-lg hover:bg-[#FEF2F2] cursor-pointer font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#E30613]"
          >
            <LogOut className="w-3.5 h-3.5" aria-hidden />
            <span className="hidden md:inline">Sign Out</span>
          </button>
        </div>
      </header>

      {/* ════════════════════════════════════════════════════════
          BODY
          ════════════════════════════════════════════════════════ */}
      <div className="flex-1 flex overflow-hidden relative">

        {/* Mobile Drawer Overlay Backdrop */}
        {isSidebarOpen && (
          <div
            onClick={() => setIsSidebarOpen(false)}
            className="md:hidden fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-30 transition-opacity duration-200"
          />
        )}

        {/* Mobile Sidebar Drawer overlay */}
        <aside
          className={`fixed inset-y-0 left-0 z-40 w-56 bg-white border-r border-[#E2E8F0] flex flex-col justify-between pt-3 pb-4 shadow-xl transform transition-transform duration-300 ease-in-out md:hidden ${
            isSidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div>
            {/* Header / close inside drawer */}
            <div className="flex items-center justify-between px-4 pb-3 border-b border-[#F1F5F9] mb-2">
              <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider">Navigation</span>
              <button
                onClick={() => setIsSidebarOpen(false)}
                className="p-1 rounded-lg text-[#64748B] hover:bg-[#F1F5F9] cursor-pointer"
                aria-label="Close navigation"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            {renderNav(true, () => setIsSidebarOpen(false))}
          </div>
          
          <div className="px-4 pt-3 border-t border-[#F1F5F9]">
            <p className="text-[9px] text-[#CBD5E1] font-medium leading-relaxed">
              Bridgestone IT Hub v2.1<br />
              © 2026 Bridgestone Corp.
            </p>
          </div>
        </aside>

        {/* Desktop/Tablet Sidebar aside */}
        <aside 
          className={`hidden md:flex flex-col justify-between pt-3 pb-4 bg-white border-r border-[#E2E8F0] z-10 flex-shrink-0 transition-all duration-300 ${
            isCollapsed ? "w-16" : "w-52"
          }`}
        >
          <div>
            {renderNav(!isCollapsed)}
          </div>

          <div className="flex flex-col gap-2">
            {/* Collapse/Expand Toggle button (Tablet and up) */}
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="flex items-center justify-center p-1.5 mx-3 rounded-lg text-[#64748B] hover:bg-[#F8FAFC] hover:text-[#1E293B] border border-[#E2E8F0] transition-colors cursor-pointer"
              title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
              aria-label={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
            >
              <ChevronRight className={`w-3.5 h-3.5 transition-transform duration-200 ${isCollapsed ? "" : "rotate-180"}`} />
            </button>

            {!isCollapsed && (
              <div className="px-4 pt-3 border-t border-[#F1F5F9] mx-1">
                <p className="text-[9px] text-[#CBD5E1] font-medium leading-relaxed">
                  Bridgestone IT Hub v2.1<br />
                  © 2026 Bridgestone Corp.
                </p>
              </div>
            )}
          </div>
        </aside>

        {/* ── Main content ─────────────────────────────────── */}
        <main className="flex-1 overflow-y-auto bg-[#F8FAFC] relative">
          {children}
        </main>

      </div>
    </div>
  );
}
