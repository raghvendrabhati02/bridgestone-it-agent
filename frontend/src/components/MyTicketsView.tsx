"use client";


import { apiFetch, NetworkError } from "@/lib/apiClient";
import { useState, useEffect } from "react";
import IncidentView from "./IncidentView";
import {
  X, MessageSquare, User, CheckCircle2, AlertTriangle, Send, Loader2,
  Calendar, FileText, ShieldAlert, Shield, ShieldCheck, ShieldOff,
  Clock, RefreshCw, UserCheck, Bot, Lock, TicketCheck,
  CheckCircle, Circle, ChevronDown, ChevronUp, Cpu, Zap
} from "lucide-react";
import {
  StatusPill,
  PriorityPill,
  RequestTypePill,
  ApprovalPill
} from "./shared/UIComponents";

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
  servicenow_number?: string;
  local_ticket_id?: string;
  sla_state?: string;
  sla_breached?: boolean;
  request_type?: string;
  approval_status?: string;
  description?: string;
  assigned_engineer?: string;
  manager?: string;
}

interface TimelineEvent {
  timestamp: string;
  title: string;
  description: string;
  type: string;
  user?: string;
  role?: string;
}

interface Comment {
  id: number;
  author: string;
  text: string;
  created_at: string;
}

interface TicketDetail {
  ticket: Ticket;
  requester: any;
  assignment: any;
  sla: any;
  timeline: TimelineEvent[];
  comments: Comment[];
  approval_required: boolean;
  approval_status: string;
  ai_diagnosis?: {
    summary?: string;
    root_cause?: string;
    confidence_score?: number;
    engineer_summary?: string;
    tools_executed?: string[];
  };
  conversation_summary?: {
    current_status?: string;
    recommended_next_step?: string;
  };
}

interface MyTicketsViewProps {
  tickets: Ticket[];
  token: string | null;
}

// Helper functions for classes that are still needed for fallback
function statusBadgeClass(status: string): string {
  // Keeping fallback return value matching status pill classes
  return "";
}

function slaBadgeClass(state?: string): string {
  if (!state) return "bg-emerald-50 text-emerald-800 border-emerald-250";
  const map: Record<string, string> = {
    HEALTHY: "bg-emerald-50 text-emerald-800 border-emerald-250",
    WARNING_75: "bg-amber-50 text-amber-800 border-amber-250",
    WARNING_90: "bg-amber-50 text-amber-800 border-amber-250",
    BREACHED: "bg-red-50 text-red-800 border-red-250",
    ESCALATED_L1: "bg-red-50 text-red-800 border-red-250",
    ESCALATED_L2: "bg-red-50 text-red-800 border-red-250",
    ESCALATED_L3: "bg-red-50 text-red-800 border-red-250",
  };
  return map[state] || "bg-emerald-50 text-emerald-800 border-emerald-250";
}

function slaStateLabel(state?: string): string {
  if (!state) return "Unknown";
  const map: Record<string, string> = {
    HEALTHY: "On Track",
    WARNING_75: "75% Used",
    WARNING_90: "90% Used",
    BREACHED: "Breached",
    ESCALATED_L1: "Escalated L1",
    ESCALATED_L2: "Escalated L2",
    ESCALATED_L3: "Escalated L3",
  };
  return map[state] || state;
}

function priorityColor(p?: string): string {
  const map: Record<string, string> = {
    CRITICAL: "text-red-700",
    HIGH: "text-orange-700",
    MEDIUM: "text-yellow-750",
    LOW: "text-green-700",
  };
  return p ? (map[p] || "text-[#475569]") : "text-[#475569]";
}

function calculateSLACountdown(t: Ticket): string {
  if (!t.sla_hours || !t.created_at) return "N/A";
  const created = new Date(t.created_at).getTime();
  const deadline = created + t.sla_hours * 3_600_000;
  const diff = deadline - Date.now();
  if (diff <= 0) return "Breached";
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  return `${h}h ${m}m`;
}

export default function MyTicketsView({ tickets, token }: MyTicketsViewProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<TicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);

  const [isRevealed, setIsRevealed] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!detailData?.ticket) return;
    const t_left = (detailData.ticket as any).laps_time_left;
    if (typeof t_left === "number") {
      setTimeLeft(t_left);
    }
  }, [detailData]);

  useEffect(() => {
    if (timeLeft <= 0) return;
    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          if (selectedTicketId) fetchTicketDetails(selectedTicketId);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [timeLeft, selectedTicketId]);

  const filteredTickets = tickets.filter(t =>
    t.ticket_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.status.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.assigned_team.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (t.issue_description || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const fetchTicketDetails = async (ticketId: string) => {
    setDetailLoading(true);
    try {
      const res = await apiFetch(`/tickets/${ticketId}/details`, {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setDetailData(data);
      } else {
        // fetch details failed
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
    } finally {
      setDetailLoading(false);
    }
  };

  const handleTicketClick = (id: string) => {
    setSelectedTicketId(id);
    fetchTicketDetails(id);
  };

  const handlePostComment = async () => {
    if (!newComment.trim() || !selectedTicketId) return;
    setSubmittingComment(true);
    try {
      const res = await apiFetch(`/tickets/${selectedTicketId}/comments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          text: newComment,
          is_internal: false
        })
      });
      if (res.ok) {
        setNewComment("");
        await fetchTicketDetails(selectedTicketId);
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
    } finally {
      setSubmittingComment(false);
    }
  };

  return (
    <div className="h-full relative overflow-hidden flex flex-col md:flex-row bg-[#F8FAFC]">
      <div className="flex-1 overflow-y-auto">
        <IncidentView
          tickets={tickets}
          filteredTickets={filteredTickets}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          handleTicketClick={handleTicketClick}
          statusBadgeClass={statusBadgeClass}
          slaBadgeClass={slaBadgeClass}
          slaStateLabel={slaStateLabel}
          priorityColor={priorityColor}
          calculateSLACountdown={calculateSLACountdown}
        />
      </div>

      {/* Side Detail Panel Drawer */}
      {selectedTicketId && (
        <div className="w-full md:w-[480px] bg-white border-l border-[#E2E8F0] h-full flex flex-col shadow-lg z-30 relative flex-shrink-0 font-sans">
          {/* Header */}
          <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
            <div>
              <h3 className="font-bold text-[#0F172A] text-xs flex items-center gap-1.5 uppercase tracking-wider">
                <FileText className="w-4 h-4 text-[#E30613]" />
                Ticket Details
              </h3>
              <span className="text-[10px] font-mono text-[#64748B] block mt-0.5">{selectedTicketId}</span>
            </div>
            <button 
              onClick={() => { setSelectedTicketId(null); setDetailData(null); }} 
              className="p-1.5 hover:bg-[#F1F5F9] rounded-lg text-[#94A3B8] hover:text-[#475569] transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {detailLoading ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2">
              <Loader2 className="w-8 h-8 text-[#E30613] animate-spin" />
              <span className="text-xs text-[#64748B] font-semibold">Loading details...</span>
            </div>
          ) : detailData ? (
            <div className="flex-1 overflow-y-auto flex flex-col">
              {/* Summary Card */}
              <div className="p-5 border-b border-[#E2E8F0] space-y-4">
                <div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <StatusPill status={detailData.ticket.status} />
                    {detailData.ticket.request_type && (
                      <RequestTypePill type={detailData.ticket.request_type} />
                    )}
                    {detailData.ticket.approval_status && detailData.ticket.approval_status !== "NOT_REQUIRED" && (
                      <ApprovalPill status={detailData.ticket.approval_status} />
                    )}
                  </div>
                  <h4 className="text-xs font-bold text-[#0F172A] mt-3 leading-snug uppercase tracking-wider">
                    {detailData.ticket.issue_description || detailData.ticket.description}
                  </h4>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs bg-[#F8FAFC] p-3 rounded-xl border border-[#E2E8F0]">
                  <div>
                    <span className="text-[9px] text-[#64748B] block font-bold uppercase tracking-wider">Category</span>
                    <span className="text-[#1E293B] font-bold">{detailData.ticket.category}</span>
                  </div>
                  <div>
                    <span className="text-[9px] text-[#64748B] block font-bold uppercase tracking-wider">Priority</span>
                    <span className="inline-block mt-0.5">
                      <PriorityPill priority={detailData.ticket.priority || "MEDIUM"} />
                    </span>
                  </div>
                  <div className="mt-1">
                    <span className="text-[9px] text-[#64748B] block font-bold uppercase tracking-wider">Assigned Group</span>
                    <span className="text-[#1E293B] font-bold">{detailData.ticket.assigned_team}</span>
                  </div>
                  <div className="mt-1">
                    <span className="text-[9px] text-[#64748B] block font-bold uppercase tracking-wider">Technician</span>
                    <span className="text-[#1E293B] font-bold">{detailData.ticket.assigned_engineer || "Auto-pilot"}</span>
                  </div>
                </div>

                {(detailData.ticket.request_type === "SERVICE_REQUEST" || detailData.ticket.request_type === "PRIVILEGED_ACTION") && detailData.ticket.approval_status === "PENDING" && (
                  <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3 rounded-xl flex items-start gap-2.5 text-xs font-bold">
                    <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      {detailData.ticket.request_type === "PRIVILEGED_ACTION"
                        ? <>This incident requires <strong>administrator privileges</strong>. Awaiting manager approval from <strong>{detailData.ticket.manager || "your manager"}</strong> before LAPS access can be granted.</>
                        : <>This request requires manager approval. A notification has been sent to your manager <strong>{detailData.ticket.manager || "manager"}</strong>.</>
                      }
                    </div>
                  </div>
                )}

                {/* WAITING_ADMIN_APPROVAL notice */}
                {(detailData.ticket.status === "WAITING_ADMIN_APPROVAL" || detailData.ticket.status === "WAITING_ADMIN") && (
                  <div className="bg-blue-50 border border-blue-200 text-blue-800 p-3 rounded-xl flex items-start gap-2.5 text-xs font-bold">
                    <Shield className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div>
                      Manager has approved this request. It is now in the <strong>IT Admin Queue</strong> awaiting final admin approval before LAPS credentials are issued.
                    </div>
                  </div>
                )}

                {/* AI Assessment Panel — shown for privileged / service-request tickets */}
                {(detailData.ticket.request_type === "PRIVILEGED_ACTION" || detailData.ticket.request_type === "SERVICE_REQUEST") && detailData.ai_diagnosis && (
                  <AIAssessmentPanel
                    confidence={detailData.ai_diagnosis.confidence_score}
                    summary={detailData.ai_diagnosis.summary}
                    rootCause={detailData.ai_diagnosis.root_cause}
                    engineerSummary={detailData.ai_diagnosis.engineer_summary}
                    recommendedStep={detailData.conversation_summary?.recommended_next_step}
                    requestType={detailData.ticket.request_type}
                  />
                )}

                {/* LAPS Simulation Secure Panel */}
                {(detailData.ticket.status === "TEMP_ADMIN_GRANTED" || (detailData.ticket as any).laps_active) && (
                  <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl flex flex-col gap-3 text-xs font-semibold relative overflow-hidden mt-3 normal-case">
                    <div className="flex items-center gap-2">
                      <Shield className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                      <span className="font-bold text-emerald-900">Temporary Administrator Access</span>
                    </div>
                    
                    <div className="border-t border-emerald-100 pt-2 flex flex-col gap-2">
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] text-emerald-700 uppercase tracking-wider">Status:</span>
                        <span className="text-emerald-950 font-bold uppercase bg-emerald-100 px-2 py-0.5 rounded text-[10px]">Granted</span>
                      </div>
                      
                      <div className="flex flex-col gap-1 bg-white p-2 rounded-lg border border-emerald-100">
                        <span className="text-[9px] text-emerald-700 uppercase tracking-wider block">Temporary LAPS Password:</span>
                        <div className="flex items-center justify-between mt-1">
                          <span className="font-mono text-sm tracking-wider text-slate-800 font-bold">
                            {isRevealed ? (detailData.ticket as any).laps_password || "BS-LAPS-9B8c" : "••••••••••"}
                          </span>
                          <button 
                            onClick={() => setIsRevealed(!isRevealed)}
                            className="text-[10px] text-[#E30613] hover:underline font-bold focus:outline-none cursor-pointer"
                          >
                            {isRevealed ? "Hide Password" : "Reveal Password"}
                          </button>
                        </div>
                      </div>

                      <div className="flex justify-between items-center text-[10px] text-emerald-700">
                        <span>Expires In:</span>
                        <span className="font-bold font-mono text-emerald-900 bg-emerald-100 px-2 py-0.5 rounded">
                          {timeLeft > 0 ? `${Math.floor(timeLeft / 60)}m ${timeLeft % 60}s` : "Expired"}
                        </span>
                      </div>

                      <div className="flex justify-between items-center text-[10px] text-emerald-700">
                        <span>Approved By:</span>
                        <span className="font-bold text-emerald-900">
                          {detailData.ticket.manager ? `${detailData.ticket.manager} (Manager)` : "Manager"}, Admin
                        </span>
                      </div>

                      <div className="flex justify-between items-center text-[10px] text-emerald-700">
                        <span>Audit ID:</span>
                        <span className="font-mono text-emerald-900">{(detailData.ticket as any).laps_audit_id || "LAPS-AUDIT-12345"}</span>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        navigator.clipboard.writeText((detailData.ticket as any).laps_password || "");
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      }}
                      className="w-full mt-1 py-1.5 bg-emerald-650 hover:bg-emerald-700 text-white font-bold rounded-lg transition cursor-pointer flex items-center justify-center gap-1.5 text-[11px] shadow-sm"
                    >
                      {copied ? "Copied ✓" : "Copy Password"}
                    </button>
                  </div>
                )}
              </div>

              {/* Comments Section */}
              <div className="p-5 border-b border-[#E2E8F0] flex-1 flex flex-col min-h-[250px]">
                <h5 className="text-[10px] font-bold text-[#64748B] flex items-center gap-1.5 mb-3 uppercase tracking-wider">
                  <MessageSquare className="w-3.5 h-3.5 text-indigo-500" />
                  Comments &amp; Discussion
                </h5>

                <div className="flex-1 overflow-y-auto space-y-3 pr-1 max-h-[280px]">
                  {detailData.comments && detailData.comments.length > 0 ? (
                    detailData.comments.map(c => (
                      <div key={c.id} className="bg-[#F8FAFC] border border-[#E2E8F0] p-3 rounded-xl space-y-1">
                        <div className="flex items-center justify-between text-[10px] text-[#64748B] font-bold uppercase">
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3 text-indigo-400" />
                            {c.author}
                          </span>
                          <span className="font-medium text-[#94A3B8]">{new Date(c.created_at).toLocaleString()}</span>
                        </div>
                        <p className="text-xs text-[#334155] leading-normal whitespace-pre-wrap font-semibold">{c.text}</p>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-6 text-xs text-[#94A3B8] italic font-semibold">
                      No comments posted on this ticket.
                    </div>
                  )}
                </div>

                {/* Comment Input */}
                <div className="mt-4 flex gap-2">
                  <input
                    type="text"
                    value={newComment}
                    onChange={e => setNewComment(e.target.value)}
                    placeholder="Type a message or reply..."
                    className="flex-1 bg-white border border-[#E2E8F0] rounded-xl px-3 py-2 text-xs font-semibold outline-none focus:ring-1 focus:ring-[#E30613] text-[#1E293B]"
                    onKeyDown={e => { if (e.key === "Enter") handlePostComment(); }}
                  />
                  <button
                    onClick={handlePostComment}
                    disabled={submittingComment || !newComment.trim()}
                    className="px-3 py-2 bg-[#E30613] hover:bg-red-750 text-white rounded-xl disabled:opacity-50 transition cursor-pointer flex items-center justify-center flex-shrink-0 font-bold text-xs gap-1.5 shadow-xs"
                  >
                    {submittingComment ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <>
                        <Send className="w-3.5 h-3.5" />
                        Send
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Enterprise Timeline Section */}
              <div className="p-5 space-y-4">
                <h5 className="text-[10px] font-bold text-[#64748B] flex items-center gap-1.5 uppercase tracking-wider">
                  <Calendar className="w-3.5 h-3.5 text-indigo-500" />
                  Activity Timeline
                </h5>

                {detailData.timeline && detailData.timeline.length > 0 ? (
                  <div className="relative ml-4">
                    {/* Vertical connector line */}
                    <div className="absolute left-0 top-3 bottom-3 w-px bg-gradient-to-b from-indigo-300 via-slate-200 to-slate-100" />

                    <div className="flex flex-col gap-0">
                      {[...detailData.timeline].reverse().map((evt, idx) => {
                        // Determine icon, colors, label per event type
                        type EventMeta = { icon: React.ReactNode; dot: string; pill: string; label: string; };
                        const meta: Record<string, EventMeta> = {
                          TICKET_CREATED:      { icon: <TicketCheck className="w-3 h-3" />,   dot: "bg-blue-500 border-blue-300",    pill: "bg-blue-50 text-blue-800 border-blue-200",    label: "Ticket Created" },
                          SERVICE_REQUEST_CREATED: { icon: <TicketCheck className="w-3 h-3" />, dot: "bg-blue-500 border-blue-300", pill: "bg-blue-50 text-blue-800 border-blue-200", label: "Service Request Created" },
                          AI_DIAGNOSIS:        { icon: <Bot className="w-3 h-3" />,            dot: "bg-violet-500 border-violet-300", pill: "bg-violet-50 text-violet-800 border-violet-200", label: "AI Diagnosis" },
                          LAPS_GRANTED:        { icon: <ShieldCheck className="w-3 h-3" />,   dot: "bg-emerald-500 border-emerald-300", pill: "bg-emerald-50 text-emerald-800 border-emerald-200", label: "LAPS Credentials Granted" },
                          LAPS_REVOKED:        { icon: <ShieldOff className="w-3 h-3" />,     dot: "bg-amber-500 border-amber-300",  pill: "bg-amber-50 text-amber-800 border-amber-200",  label: "LAPS Credentials Revoked" },
                          LAPS_EXPIRED:        { icon: <Clock className="w-3 h-3" />,         dot: "bg-orange-500 border-orange-300", pill: "bg-orange-50 text-orange-800 border-orange-200", label: "LAPS Credentials Expired" },
                          TICKET_CLOSED:       { icon: <CheckCircle className="w-3 h-3" />,   dot: "bg-teal-500 border-teal-300",   pill: "bg-teal-50 text-teal-800 border-teal-200",   label: "Ticket Closed" },
                          STATUS_CHANGED:      { icon: <RefreshCw className="w-3 h-3" />,     dot: "bg-indigo-400 border-indigo-300", pill: "bg-indigo-50 text-indigo-800 border-indigo-200", label: "Status Updated" },
                          MANAGER_APPROVED:    { icon: <UserCheck className="w-3 h-3" />,     dot: "bg-green-500 border-green-300",  pill: "bg-green-50 text-green-800 border-green-200",  label: "Manager Approved" },
                          ADMIN_APPROVED:      { icon: <ShieldCheck className="w-3 h-3" />,   dot: "bg-emerald-600 border-emerald-400", pill: "bg-emerald-50 text-emerald-800 border-emerald-200", label: "Admin Approved" },
                          COMMENT:             { icon: <MessageSquare className="w-3 h-3" />, dot: "bg-slate-400 border-slate-300",  pill: "bg-slate-50 text-slate-700 border-slate-200",  label: "Comment Added" },
                        };
                        const m = meta[evt.type] || {
                          icon: <Circle className="w-3 h-3" />,
                          dot: "bg-slate-300 border-slate-200",
                          pill: "bg-slate-50 text-slate-600 border-slate-200",
                          label: evt.title || evt.type?.replace(/_/g, " ") || "Event",
                        };

                        return (
                          <TimelineEventRow
                            key={idx}
                            evt={evt}
                            meta={m}
                            isLast={idx === detailData.timeline.length - 1}
                          />
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-[#94A3B8] italic font-semibold py-2">
                    No activity recorded yet.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-6">
              <AlertTriangle className="w-8 h-8 text-red-550 mb-2" />
              <span className="text-xs text-[#64748B] font-bold uppercase tracking-wider">Failed to load details. Please try again.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
// ── TimelineEventRow sub-component ─────────────────────────────────────────
interface TimelineEventRowProps {
  evt: TimelineEvent;
  meta: { icon: React.ReactNode; dot: string; pill: string; label: string };
  isLast: boolean;
}

function TimelineEventRow({ evt, meta, isLast }: TimelineEventRowProps) {
  const [expanded, setExpanded] = useState(false);
  const ts = evt.timestamp ? new Date(evt.timestamp) : null;
  const dateStr = ts ? ts.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "";
  const timeStr = ts ? ts.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : "";

  return (
    <div className={`relative flex gap-3 pl-4 pb-4 ${isLast ? "" : ""}`}>
      {/* Dot on the timeline line */}
      <div className={`absolute left-[-5px] top-1.5 w-2.5 h-2.5 rounded-full border-2 flex-shrink-0 z-10 ${meta.dot}`} />

      <div className="flex-1 min-w-0">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={`inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded border ${meta.pill}`}>
              {meta.icon}
              {meta.label}
            </span>
            {evt.user || (evt as any).actor ? (
              <span className="text-[9px] text-[#94A3B8] font-medium">
                by <strong className="text-[#475569]">{evt.user || (evt as any).actor}</strong>
              </span>
            ) : null}
          </div>
          <div className="text-right flex-shrink-0">
            <span className="text-[9px] text-[#94A3B8] font-bold block">{timeStr}</span>
            <span className="text-[9px] text-[#CBD5E1] font-medium">{dateStr}</span>
          </div>
        </div>

        {/* Description (collapsible if long) */}
        {evt.description && (
          <div className="mt-1">
            <p className={`text-[10px] text-[#475569] leading-relaxed font-medium ${
              !expanded && evt.description.length > 120 ? "line-clamp-2" : ""
            }`}>
              {evt.description}
            </p>
            {evt.description.length > 120 && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-0.5 text-[9px] text-indigo-500 hover:text-indigo-700 font-bold mt-0.5 cursor-pointer"
              >
                {expanded ? <><ChevronUp className="w-2.5 h-2.5" /> Show less</> : <><ChevronDown className="w-2.5 h-2.5" /> Show more</>}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── AI Assessment Panel sub-component ───────────────────────────────────────
interface AIAssessmentPanelProps {
  confidence?: number;
  summary?: string;
  rootCause?: string;
  engineerSummary?: string;
  recommendedStep?: string;
  requestType?: string;
}

function AIAssessmentPanel({ confidence, summary, rootCause, engineerSummary, recommendedStep, requestType }: AIAssessmentPanelProps) {
  const [open, setOpen] = useState(false);
  const pct = confidence ?? 85;
  const barColor = pct >= 90 ? "bg-emerald-500" : pct >= 75 ? "bg-amber-500" : "bg-red-500";
  const barLabel = pct >= 90 ? "High" : pct >= 75 ? "Medium" : "Low";
  const barLabelColor = pct >= 90 ? "text-emerald-700" : pct >= 75 ? "text-amber-700" : "text-red-700";
  const isPriv = requestType === "PRIVILEGED_ACTION";

  return (
    <div className="border border-violet-200 rounded-xl overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-3 bg-violet-50 hover:bg-violet-100 transition cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <Bot className="w-3.5 h-3.5 text-violet-600 flex-shrink-0" />
          <span className="text-[10px] font-bold text-violet-900 uppercase tracking-wider">
            AI Assessment
          </span>
          <span className={`text-[9px] font-bold ${barLabelColor} bg-white px-1.5 py-0.5 rounded border border-violet-200`}>
            {barLabel} Confidence · {pct}%
          </span>
        </div>
        {open ? <ChevronUp className="w-3.5 h-3.5 text-violet-400" /> : <ChevronDown className="w-3.5 h-3.5 text-violet-400" />}
      </button>

      {/* Collapsible body */}
      {open && (
        <div className="p-3 bg-white space-y-3">
          {/* Confidence bar */}
          <div>
            <div className="flex justify-between text-[9px] font-bold text-[#64748B] mb-1 uppercase tracking-wider">
              <span>Confidence Score</span>
              <span className={barLabelColor}>{pct}% — {barLabel}</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${barColor}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {/* Root cause / reasoning */}
          {(rootCause || summary) && (
            <div>
              <span className="text-[9px] font-bold text-[#64748B] uppercase tracking-wider block mb-1">
                {isPriv ? "Privileged Action Reasoning" : "Request Classification"}
              </span>
              <p className="text-[10px] text-[#334155] leading-relaxed font-medium">
                {rootCause || summary}
              </p>
            </div>
          )}

          {/* Engineer summary */}
          {engineerSummary && (
            <div>
              <span className="text-[9px] font-bold text-[#64748B] uppercase tracking-wider block mb-1">IT Engineer Notes</span>
              <p className="text-[10px] text-[#475569] leading-relaxed font-medium">{engineerSummary}</p>
            </div>
          )}

          {/* Recommended next step */}
          {recommendedStep && (
            <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-2.5 flex items-start gap-2">
              <Zap className="w-3 h-3 text-indigo-500 flex-shrink-0 mt-0.5" />
              <div>
                <span className="text-[9px] font-bold text-indigo-700 uppercase tracking-wider block mb-0.5">Recommended Action</span>
                <p className="text-[10px] text-indigo-800 leading-relaxed font-medium">{recommendedStep}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
