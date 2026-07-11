"use client";


import { apiFetch, NetworkError } from "@/lib/apiClient";
import { useState } from "react";
import IncidentView from "./IncidentView";
import {
  X, MessageSquare, User, CheckCircle2, AlertTriangle, Send, Loader2,
  Calendar, FileText, ShieldAlert
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
}

interface MyTicketsViewProps {
  tickets: Ticket[];
  token: string | null;
  apiBaseUrl: string;
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

export default function MyTicketsView({ tickets, token, apiBaseUrl }: MyTicketsViewProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<TicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);

  const filteredTickets = tickets.filter(t =>
    t.ticket_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.status.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.assigned_team.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (t.issue_description || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const fetchTicketDetails = async (ticketId: string) => {
    setDetailLoading(true);
    try {
      const res = await apiFetch(`${apiBaseUrl}/tickets/${ticketId}/details`, {
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
      const res = await apiFetch(`${apiBaseUrl}/tickets/${selectedTicketId}/comments`, {
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

                {detailData.ticket.request_type === "SERVICE_REQUEST" && detailData.ticket.approval_status === "PENDING" && (
                  <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3 rounded-xl flex items-start gap-2.5 text-xs font-bold">
                    <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      This request requires manager approval. A notification has been sent to your manager <strong>{detailData.ticket.manager || "manager"}</strong>.
                    </div>
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

              {/* Timeline Section */}
              <div className="p-5 space-y-4">
                <h5 className="text-[10px] font-bold text-[#64748B] flex items-center gap-1.5 uppercase tracking-wider">
                  <Calendar className="w-3.5 h-3.5 text-indigo-500" />
                  Ticket Activity Timeline
                </h5>

                <div className="relative border-l border-[#CBD5E1] ml-2.5 pl-4 space-y-4">
                  {detailData.timeline && detailData.timeline.length > 0 ? (
                    detailData.timeline.map((evt, idx) => (
                      <div key={idx} className="relative text-xs">
                        <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-white border-2 border-indigo-400" />
                        <div className="text-[9px] text-[#94A3B8] font-bold uppercase tracking-wider">
                          {new Date(evt.timestamp).toLocaleString()}
                        </div>
                        <div className="font-bold text-[#1E293B] mt-0.5 uppercase text-[10px] tracking-wider">{evt.title}</div>
                        <div className="text-[#475569] mt-0.5 leading-normal font-semibold">{evt.description}</div>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-[#94A3B8] italic font-semibold">No timeline events found.</div>
                  )}
                </div>
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
