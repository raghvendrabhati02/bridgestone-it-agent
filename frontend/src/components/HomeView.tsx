"use client";

import {
  ChevronRight, ArrowRight,
  MessageSquare, Zap,
  Sparkles, Wrench, FileText,
  Download, KeyRound, RefreshCw, Monitor,
  Globe, Mail, Code2, Package, WifiOff,
  CheckCircle,
} from "lucide-react";
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  StatusPill,
  PriorityPill
} from "./shared/UIComponents";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────
interface Ticket {
  ticket_id: string;
  category: string;
  issue_description: string;
  assigned_team: string;
  status: string;
  created_by?: string;
  created_at: string;
  priority?: string;
  sla_hours?: number;
  servicenow_id?: string;
  sla_state?: string;
  sla_breached?: boolean;
}

interface HomeViewProps {
  user: any;
  tickets: Ticket[];
  setActiveView: (view: any) => void;
  handleQuickAction: (prompt: string) => void;
  startNewSession: () => void;
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────
function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit" });
  } catch { return "—"; }
}

// ─────────────────────────────────────────────────────────────
// Data
// ─────────────────────────────────────────────────────────────
const SUPPORT_FEATURES = [
  { Icon: Sparkles, label: "AI Diagnosis", desc: "Understands your issue instantly" },
  { Icon: Wrench, label: "Auto Troubleshooting", desc: "Resolves problems end-to-end" },
  { Icon: FileText, label: "Smart Ticket Creation", desc: "Escalates when human help is needed" },
];

const ACTION_FEATURES = [
  { Icon: Download, label: "Install Software" },
  { Icon: KeyRound, label: "Change Password" },
  { Icon: RefreshCw, label: "Restart Services" },
  { Icon: Monitor, label: "Device Health Check" },
];

const COMMON_REQUESTS = [
  { Icon: KeyRound, label: "Change Password", prompt: "Reset my corporate password" },
  { Icon: Globe, label: "VPN Not Working", prompt: "My VPN is not connecting, can you help me fix it?" },
  { Icon: Mail, label: "Outlook Issues", prompt: "Outlook is not opening, help me fix it" },
  { Icon: Code2, label: "Install VS Code", prompt: "Install Visual Studio Code on my device" },
  { Icon: Package, label: "Install SAP GUI", prompt: "Install SAP GUI 8.00 on my device" },
  { Icon: WifiOff, label: "Wi-Fi Issues", prompt: "I have Wi-Fi connectivity issues on my device" },
];

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────
export default function HomeView({
  user,
  tickets,
  setActiveView,
  handleQuickAction,
  startNewSession,
}: HomeViewProps) {
  const firstName = user?.username
    ? user.username.charAt(0).toUpperCase() + user.username.slice(1)
    : "there";

  const recentTickets = [...tickets]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 3);

  return (
    <div className="h-full flex flex-col px-6 py-4 gap-3 overflow-y-auto bg-white">

      {/* HERO SECTION */}
      <section className="flex-none border-b border-[#E2E8F0] pb-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[28px] font-bold text-[#0F172A] leading-none tracking-tight">
              {getGreeting()}, {firstName}&nbsp;👋
            </h1>
            <p className="text-sm font-medium text-[#475569] mt-1.5 font-bold uppercase tracking-wider">
              AI-powered Enterprise IT Support
            </p>
            <p className="text-xs text-[#94A3B8] mt-0.5 font-bold uppercase tracking-wider">
              Describe your issue or choose an action below.
            </p>
          </div>

          {/* AI status indicator */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 border border-green-200 rounded-full flex-shrink-0 mt-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse inline-block" aria-hidden />
            <span className="text-[11px] font-bold text-green-700 uppercase tracking-wider">AI Online</span>
          </div>
        </div>
      </section>

      {/* PRIMARY CARDS */}
      <section className="flex-none grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* IT Support */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden flex flex-col hover:border-[#E30613]/30 hover:shadow-sm transition-all">
          <div className="h-[3px] bg-[#E30613]" />

          <div className="px-5 py-4 flex flex-col gap-3.5 flex-1">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-red-50 border border-red-100 flex items-center justify-center flex-shrink-0">
                <MessageSquare className="w-4 h-4 text-[#E30613]" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-gray-900 leading-none">IT Support</h2>
                <p className="text-[11px] text-gray-400 mt-0.5">Conversational AI resolution</p>
              </div>
            </div>

            <div className="space-y-2">
              {SUPPORT_FEATURES.map(({ Icon, label, desc }) => (
                <div key={label} className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded bg-gray-50 border border-gray-100 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-3 h-3 text-[#E30613]" />
                  </div>
                  <div className="leading-none">
                    <span className="text-xs font-semibold text-gray-800">{label}</span>
                    <span className="text-[10px] text-gray-400 ml-1">— {desc}</span>
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={() => { startNewSession(); setActiveView("support"); }}
              className="mt-auto flex items-center justify-center gap-1.5 w-full py-2 bg-[#E30613] hover:bg-[#B8050F] active:bg-[#8B0309] text-white text-xs font-bold rounded-lg transition-colors cursor-pointer"
            >
              Open IT Support
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* IT Actions */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden flex flex-col hover:border-[#E30613]/30 hover:shadow-sm transition-all">
          <div className="h-[3px] bg-[#E30613]" />

          <div className="px-5 py-4 flex flex-col gap-3.5 flex-1">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-red-50 border border-red-100 flex items-center justify-center flex-shrink-0">
                <Zap className="w-4 h-4 text-[#E30613]" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-gray-900 leading-none">IT Actions</h2>
                <p className="text-[11px] text-gray-400 mt-0.5">Automated device tasks, no waiting</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 flex-1">
              {ACTION_FEATURES.map(({ Icon, label }) => (
                <div
                  key={label}
                  className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-100 rounded-lg"
                >
                  <Icon className="w-3.5 h-3.5 text-[#E30613] flex-shrink-0" />
                  <span className="text-xs font-medium text-gray-700 leading-tight">{label}</span>
                </div>
              ))}
            </div>

            <button
              onClick={() => setActiveView("actions")}
              className="flex items-center justify-center gap-1.5 w-full py-2 bg-[#E30613] hover:bg-[#B8050F] active:bg-[#8B0309] text-white text-xs font-bold rounded-lg transition-colors cursor-pointer"
            >
              Open IT Actions
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </section>

      {/* COMMON REQUESTS */}
      <section className="flex-none">
        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">
          Common Requests
        </p>
        <div className="flex flex-wrap gap-2">
          {COMMON_REQUESTS.map(({ Icon, label, prompt }) => (
            <button
              key={label}
              onClick={() => handleQuickAction(prompt)}
              className="group inline-flex items-center gap-1.5 px-3 py-1.5
                         bg-white border border-gray-200 rounded-full
                         text-xs font-semibold text-gray-600
                         hover:border-[#E30613] hover:bg-red-50/40 hover:text-[#E30613]
                         transition-all duration-150 cursor-pointer"
            >
              <Icon className="w-3 h-3 text-gray-400 group-hover:text-[#E30613] transition-colors duration-150" />
              {label}
            </button>
          ))}
        </div>
      </section>

      {/* RECENT TICKETS */}
      <section className="flex-1 min-h-0 flex flex-col border border-gray-200 rounded-xl overflow-hidden bg-white">

        <div className="flex items-center justify-between px-5 py-3 border-b border-[#F1F5F9] bg-[#F8FAFC] flex-shrink-0">
          <p className="text-[10px] font-bold text-[#64748B] uppercase tracking-widest">
            Recent Tickets
          </p>
          <button
            onClick={() => setActiveView("my_tickets")}
            className="inline-flex items-center gap-1 text-[11px] font-bold text-[#E30613] hover:underline cursor-pointer uppercase tracking-wider"
          >
            View All
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {recentTickets.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-6">
            <div className="w-12 h-12 rounded-full bg-[#F8FAFC] border border-[#F1F5F9] flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-[#CBD5E1]" aria-hidden />
            </div>
            <div>
              <p className="text-sm font-bold text-[#1E293B] uppercase tracking-wider">No tickets found</p>
              <p className="text-xs text-[#64748B] mt-1 max-w-[200px] font-bold uppercase tracking-wider">Your history will appear here once you've submitted a request.</p>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentTickets.map((ticket, idx) => (
                  <TableRow key={ticket.ticket_id}>
                    <TableCell>
                      <button
                        onClick={() => setActiveView("my_tickets")}
                        className="font-mono font-bold text-[#E30613] hover:underline cursor-pointer text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#E30613] rounded"
                      >
                        {ticket.ticket_id}
                      </button>
                    </TableCell>
                    <TableCell className="max-w-xs font-semibold">
                      <span
                        className="text-gray-800 block truncate text-xs"
                        title={ticket.issue_description}
                      >
                        {ticket.issue_description || "—"}
                      </span>
                      <span className="text-gray-400 text-[10px] block mt-0.5">
                        {ticket.assigned_team}
                      </span>
                    </TableCell>
                    <TableCell>
                      <PriorityPill priority={ticket.priority || "MEDIUM"} />
                    </TableCell>
                    <TableCell>
                      <StatusPill status={ticket.status} />
                    </TableCell>
                    <TableCell className="text-gray-400 text-[11px] font-semibold">
                      {formatDate(ticket.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

    </div>
  );
}
