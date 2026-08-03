import React, { useState, useEffect } from "react";
import {
  X, MessageSquare, History, User, Users, Calendar, Clock,
  Shield, CheckCircle2, XCircle, AlertTriangle, Send, Loader2,
  Trash2, Edit, UserCheck, RefreshCw, Sparkles, Check, FileText
} from "lucide-react";
import { API_BASE_URL } from "../lib/apiClient";
import {
  StatusPill,
  PriorityPill,
  RequestTypePill,
  ApprovalPill
} from "./shared/UIComponents";

interface TicketDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketId: string | null;
  userRole?: string; // "EMPLOYEE" | "MANAGER" | "ADMIN"
  currentUsername?: string;
  token?: string | null;
  onTicketUpdated?: () => void;
}

export default function TicketDetailsModal({
  isOpen,
  onClose,
  ticketId,
  userRole = "EMPLOYEE",
  currentUsername = "user",
  token,
  onTicketUpdated
}: TicketDetailsModalProps) {
  const [activeTab, setActiveTab] = useState<"timeline" | "comments" | "details">("timeline");
  const [details, setDetails] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [newComment, setNewComment] = useState("");
  const [isInternalNote, setIsInternalNote] = useState(false);
  const [postingComment, setPostingComment] = useState(false);
  
  // Action Modals & States
  const [showReassignModal, setShowReassignModal] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);

  const [actionNote, setActionNote] = useState("");
  const [selectedEngineer, setSelectedEngineer] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Edit fields for Admin
  const [editCategory, setEditCategory] = useState("");
  const [editPriority, setEditPriority] = useState("");
  const [editStatus, setEditStatus] = useState("");

  const effectiveToken = token || (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);

  const fetchTicketDetails = async () => {
    if (!ticketId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/tickets/${ticketId}/details`, {
        headers: effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {}
      });
      if (res.ok) {
        const data = await res.json();
        setDetails(data);
        if (data.ticket) {
          setSelectedTeam(data.ticket.assigned_team || data.ticket.assignment_group || "Helpdesk");
          setSelectedEngineer(data.ticket.assigned_engineer || "");
          setEditCategory(data.ticket.category || "");
          setEditPriority(data.ticket.priority || "MEDIUM");
          setEditStatus(data.ticket.status || "NEW");
        }
      }
    } catch (err) {
      console.error("Failed to fetch ticket details:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && ticketId) {
      fetchTicketDetails();
    }
  }, [isOpen, ticketId]);

  if (!isOpen || !ticketId) return null;

  const t = details?.ticket || {};
  const timeline = (details?.timeline || []).slice().sort((a: any, b: any) =>
    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
  const comments = details?.comments || [];

  const roleUpper = (userRole || "EMPLOYEE").toUpperCase();
  const isCreator = (t.created_by === currentUsername);

  // ── Actions ─────────────────────────────────────────────────────────────

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    setPostingComment(true);
    try {
      const res = await fetch(`${API_BASE_URL}/tickets/${ticketId}/comments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {})
        },
        body: JSON.stringify({ text: newComment, is_internal: isInternalNote })
      });
      if (res.ok) {
        setNewComment("");
        fetchTicketDetails();
        if (onTicketUpdated) onTicketUpdated();
      }
    } catch (err) {
      console.error("Failed to post comment:", err);
    } finally {
      setPostingComment(false);
    }
  };

  const handleTicketAction = async (actionName: string, extraPayload: any = {}) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/tickets/${ticketId}/action`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {})
        },
        body: JSON.stringify({ action: actionName, note: actionNote, ...extraPayload })
      });
      if (res.ok) {
        setActionNote("");
        setShowReassignModal(false);
        setShowApproveModal(false);
        setShowRejectModal(false);
        fetchTicketDetails();
        if (onTicketUpdated) onTicketUpdated();
      }
    } catch (err) {
      console.error(`Action ${actionName} failed:`, err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteTicket = async () => {
    if (!confirm(`Are you sure you want to permanently delete ticket ${ticketId}?`)) return;
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/tickets/${ticketId}`, {
        method: "DELETE",
        headers: effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {}
      });
      if (res.ok) {
        onClose();
        if (onTicketUpdated) onTicketUpdated();
      }
    } catch (err) {
      console.error("Delete failed:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/tickets/${ticketId}/update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {})
        },
        body: JSON.stringify({
          category: editCategory,
          priority: editPriority,
          status: editStatus,
          assigned_team: selectedTeam,
          assigned_engineer: selectedEngineer
        })
      });
      if (res.ok) {
        setShowEditModal(false);
        fetchTicketDetails();
        if (onTicketUpdated) onTicketUpdated();
      }
    } catch (err) {
      console.error("Update failed:", err);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 font-sans">
      <div className="bg-white rounded-2xl shadow-2xl border border-[#E2E8F0] w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-4 bg-[#F8FAFC] border-b border-[#E2E8F0] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#E30613] text-white flex items-center justify-center font-bold text-sm shadow-xs">
              IT
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold text-[#0F172A] font-mono">#{t.ticket_id || ticketId}</span>
                <StatusPill status={t.status || "NEW"} />
                <PriorityPill priority={t.priority || "MEDIUM"} />
                <ApprovalPill status={t.approval_status || "NOT_REQUIRED"} />
              </div>
              <p className="text-xs text-[#64748B] mt-0.5 font-medium line-clamp-1">
                {t.description || t.issue_description || "Enterprise Incident Record"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchTicketDetails}
              disabled={loading}
              className="p-2 text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-lg transition-colors cursor-pointer"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-lg transition-colors cursor-pointer"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {loading && !details ? (
          <div className="p-16 text-center text-xs text-[#64748B] flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-[#E30613]" />
            <span>Loading enterprise ticket data...</span>
          </div>
        ) : (
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {/* Metadata Grid */}
            <div className="p-6 bg-white border-b border-[#E2E8F0] grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider block">Requester</span>
                <span className="font-semibold text-[#0F172A] mt-0.5 block truncate">{t.created_by || "Employee"}</span>
              </div>
              <div>
                <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider block">Category</span>
                <span className="font-semibold text-[#0F172A] mt-0.5 block truncate">{t.category || "General"}</span>
              </div>
              <div>
                <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider block">Assignment Group</span>
                <span className="font-semibold text-[#0F172A] mt-0.5 block truncate">{t.assigned_team || t.assignment_group || "Helpdesk"}</span>
              </div>
              <div>
                <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider block">Assigned Engineer</span>
                <span className="font-semibold text-[#0F172A] mt-0.5 block truncate">{t.assigned_engineer || "Unassigned"}</span>
              </div>

              <div>
                <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider block">Impact / Urgency</span>
                <span className="font-semibold text-[#0F172A] mt-0.5 block">Medium / Medium</span>
              </div>
              <div>
                <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider block">Created Date</span>
                <span className="font-semibold text-[#0F172A] mt-0.5 block">
                  {t.created_at ? new Date(t.created_at).toLocaleString() : "N/A"}
                </span>
              </div>
              <div>
                <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider block">Updated Date</span>
                <span className="font-semibold text-[#0F172A] mt-0.5 block">
                  {t.updated_at ? new Date(t.updated_at).toLocaleString() : "N/A"}
                </span>
              </div>
              <div>
                <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider block">Manager</span>
                <span className="font-semibold text-[#0F172A] mt-0.5 block truncate">{t.manager || "manager"}</span>
              </div>
            </div>

            {/* Tabs */}
            <div className="px-6 bg-[#F8FAFC] border-b border-[#E2E8F0] flex gap-2">
              <button
                onClick={() => setActiveTab("timeline")}
                className={`py-2.5 px-4 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                  activeTab === "timeline"
                    ? "border-[#E30613] text-[#E30613]"
                    : "border-transparent text-[#64748B] hover:text-[#0F172A]"
                }`}
              >
                Ticket Timeline ({timeline.length})
              </button>
              <button
                onClick={() => setActiveTab("comments")}
                className={`py-2.5 px-4 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                  activeTab === "comments"
                    ? "border-[#E30613] text-[#E30613]"
                    : "border-transparent text-[#64748B] hover:text-[#0F172A]"
                }`}
              >
                Comments & Work Notes ({comments.length})
              </button>
              {details?.ai_diagnosis && (
                <button
                  onClick={() => setActiveTab("details")}
                  className={`py-2.5 px-4 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                    activeTab === "details"
                      ? "border-[#E30613] text-[#E30613]"
                      : "border-transparent text-[#64748B] hover:text-[#0F172A]"
                  }`}
                >
                  AI Diagnosis
                </button>
              )}
            </div>

            {/* Tab Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              
              {/* TIMELINE TAB */}
              {activeTab === "timeline" && (
                <div className="space-y-4 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-[#E2E8F0]">
                  {timeline.length === 0 ? (
                    <p className="text-xs text-[#94A3B8] italic">No timeline events recorded.</p>
                  ) : (
                    timeline.map((event: TimelineEvent, idx: number) => (
                      <div key={idx} className="flex gap-4 relative">
                        <div className="w-7 h-7 rounded-full bg-white border border-[#CBD5E1] shadow-xs flex items-center justify-center flex-shrink-0 z-10">
                          <Clock className="w-3.5 h-3.5 text-[#E30613]" />
                        </div>
                        <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3.5 flex-1 shadow-2xs">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-bold text-[#0F172A]">{event.title}</span>
                            <span className="text-[10px] text-[#94A3B8] font-mono">
                              {event.timestamp ? new Date(event.timestamp).toLocaleString() : ""}
                            </span>
                          </div>
                          <p className="text-xs text-[#475569] mt-1 leading-relaxed">{event.description}</p>
                          {event.user && (
                            <div className="mt-2 text-[10px] text-[#64748B] font-semibold flex items-center gap-1">
                              <User className="w-3 h-3 text-[#94A3B8]" />
                              <span>{event.user}</span>
                              {event.role && (
                                <span className="px-1.5 py-0.2 rounded bg-slate-200 text-slate-700 text-[9px] uppercase font-bold">
                                  {event.role}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* COMMENTS TAB */}
              {activeTab === "comments" && (
                <div className="space-y-6">
                  {/* Post Comment Form */}
                  <form onSubmit={handleAddComment} className="bg-[#F8FAFC] border border-[#E2E8F0] p-4 rounded-xl space-y-3">
                    <textarea
                      value={newComment}
                      onChange={(e) => setNewComment(e.target.value)}
                      placeholder="Add a comment or work note..."
                      className="w-full bg-white border border-[#CBD5E1] rounded-lg p-3 text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:ring-1 focus:ring-[#E30613]"
                      rows={3}
                      required
                    />

                    <div className="flex items-center justify-between">
                      {roleUpper !== "EMPLOYEE" ? (
                        <label className="flex items-center gap-2 text-xs text-[#475569] font-medium cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isInternalNote}
                            onChange={(e) => setIsInternalNote(e.target.checked)}
                            className="rounded text-[#E30613] focus:ring-[#E30613]"
                          />
                          <span>Internal Work Note (Staff Only)</span>
                        </label>
                      ) : <div />}

                      <button
                        type="submit"
                        disabled={postingComment || !newComment.trim()}
                        className="px-4 py-2 bg-[#E30613] hover:bg-red-700 text-white font-bold text-xs rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                      >
                        {postingComment ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                        <span>Submit</span>
                      </button>
                    </div>
                  </form>

                  {/* Comments Thread */}
                  <div className="space-y-3">
                    {comments.length === 0 ? (
                      <p className="text-xs text-[#94A3B8] italic text-center py-4">No comments posted yet.</p>
                    ) : (
                      comments.map((c: any) => (
                        <div
                          key={c.id}
                          className={`p-4 rounded-xl border text-xs space-y-1.5 ${
                            c.is_internal
                              ? "bg-amber-50/50 border-amber-200"
                              : "bg-white border-[#E2E8F0]"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-[#0F172A]">{c.author}</span>
                              {c.is_internal && (
                                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800 uppercase">
                                  Internal Note
                                </span>
                              )}
                            </div>
                            <span className="text-[10px] text-[#94A3B8]">
                              {c.created_at ? new Date(c.created_at).toLocaleString() : ""}
                            </span>
                          </div>
                          <p className="text-[#334155] leading-relaxed whitespace-pre-wrap">{c.text}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* AI DIAGNOSIS TAB */}
              {activeTab === "details" && details?.ai_diagnosis && (
                <div className="bg-slate-900 text-white p-5 rounded-xl space-y-3">
                  <div className="flex items-center gap-2 text-amber-400 font-bold text-xs">
                    <Sparkles className="w-4 h-4" />
                    <span>AI Automated Diagnosis & Root Cause</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {details.ai_diagnosis.summary || details.ai_diagnosis.engineer_summary || "Automated diagnostic engine analyzed configuration metrics."}
                  </p>
                  {details.ai_diagnosis.root_cause && (
                    <div className="p-3 bg-slate-800 rounded-lg text-xs">
                      <span className="font-bold text-slate-400 block uppercase text-[9px]">Root Cause</span>
                      <span className="text-amber-200 font-mono mt-0.5 block">{details.ai_diagnosis.root_cause}</span>
                    </div>
                  )}
                </div>
              )}

            </div>

            {/* Action Bar Footer (Role Scoped) */}
            <div className="px-6 py-4 bg-[#F8FAFC] border-t border-[#E2E8F0] flex items-center justify-between flex-wrap gap-2">
              <span className="text-[11px] text-[#64748B] font-medium">Role: {roleUpper}</span>

              <div className="flex items-center gap-2 flex-wrap">
                {/* Employee Action: Close ticket if resolved */}
                {(roleUpper === "EMPLOYEE" || isCreator) && (t.status === "RESOLVED" || t.status === "FULFILLED") && (
                  <button
                    onClick={() => handleTicketAction("close")}
                    disabled={actionLoading}
                    className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg transition-colors cursor-pointer"
                  >
                    Confirm & Close Ticket
                  </button>
                )}

                {/* Manager / Admin Actions */}
                {(roleUpper === "MANAGER" || roleUpper === "ADMIN") && (
                  <>
                    {t.approval_status === "PENDING" && (
                      <>
                        <button
                          onClick={() => setShowApproveModal(true)}
                          className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg transition-colors cursor-pointer"
                        >
                          Approve Request
                        </button>
                        <button
                          onClick={() => setShowRejectModal(true)}
                          className="px-3.5 py-2 bg-red-600 hover:bg-red-700 text-white font-bold text-xs rounded-lg transition-colors cursor-pointer"
                        >
                          Reject Request
                        </button>
                      </>
                    )}

                    <button
                      onClick={() => setShowReassignModal(true)}
                      className="px-3.5 py-2 bg-slate-800 hover:bg-slate-900 text-white font-bold text-xs rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <UserCheck className="w-3.5 h-3.5" />
                      <span>Reassign</span>
                    </button>
                  </>
                )}

                {/* Admin Actions */}
                {roleUpper === "ADMIN" && (
                  <>
                    <button
                      onClick={() => setShowEditModal(true)}
                      className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <Edit className="w-3.5 h-3.5" />
                      <span>Edit</span>
                    </button>

                    {t.status === "CLOSED" || t.status === "RESOLVED" ? (
                      <button
                        onClick={() => handleTicketAction("reopen")}
                        disabled={actionLoading}
                        className="px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-lg transition-colors cursor-pointer"
                      >
                        Reopen Ticket
                      </button>
                    ) : (
                      <button
                        onClick={() => handleTicketAction("resolve")}
                        disabled={actionLoading}
                        className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg transition-colors cursor-pointer"
                      >
                        Resolve Ticket
                      </button>
                    )}

                    <button
                      onClick={handleDeleteTicket}
                      disabled={actionLoading}
                      className="px-3 py-2 bg-red-50 hover:bg-red-100 text-red-700 font-bold text-xs rounded-lg border border-red-200 transition-colors flex items-center gap-1 cursor-pointer"
                      title="Delete Ticket"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Delete</span>
                    </button>
                  </>
                )}
              </div>
            </div>

          </div>
        )}

      </div>

      {/* ── REASSIGN MODAL ─────────────────────────────────────────────────── */}
      {showReassignModal && (
        <div className="fixed inset-0 z-60 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full border border-[#E2E8F0] shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-[#0F172A]">Reassign Ticket #{t.ticket_id}</h3>
            
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-[#475569] block mb-1">Assignment Group</label>
                <select
                  value={selectedTeam}
                  onChange={(e) => setSelectedTeam(e.target.value)}
                  className="w-full bg-white border border-[#CBD5E1] rounded-lg p-2 text-xs font-semibold"
                >
                  <option value="Helpdesk">Helpdesk</option>
                  <option value="Network">Network</option>
                  <option value="Security">Security</option>
                  <option value="Hardware">Hardware</option>
                  <option value="Database">Database</option>
                  <option value="Access Management">Access Management</option>
                  <option value="Cloud Infrastructure">Cloud Infrastructure</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-[#475569] block mb-1">Assigned Engineer</label>
                <input
                  type="text"
                  value={selectedEngineer}
                  onChange={(e) => setSelectedEngineer(e.target.value)}
                  placeholder="e.g. Emily Watson (Helpdesk L2)"
                  className="w-full bg-white border border-[#CBD5E1] rounded-lg p-2 text-xs"
                />
              </div>

              <div>
                <label className="font-bold text-[#475569] block mb-1">Reassignment Reason / Note</label>
                <textarea
                  value={actionNote}
                  onChange={(e) => setActionNote(e.target.value)}
                  placeholder="Provide reason for reassignment..."
                  className="w-full bg-white border border-[#CBD5E1] rounded-lg p-2 text-xs"
                  rows={2}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowReassignModal(false)}
                className="px-3.5 py-1.5 text-xs font-bold text-[#64748B] hover:bg-[#F1F5F9] rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={() => handleTicketAction("assign", { team: selectedTeam, engineer: selectedEngineer })}
                disabled={actionLoading}
                className="px-4 py-1.5 text-xs font-bold bg-[#E30613] text-white rounded-lg hover:bg-red-700"
              >
                Submit Reassignment
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── APPROVE MODAL ──────────────────────────────────────────────────── */}
      {showApproveModal && (
        <div className="fixed inset-0 z-60 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full border border-[#E2E8F0] shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-[#0F172A]">Approve Request #{t.ticket_id}</h3>
            <textarea
              value={actionNote}
              onChange={(e) => setActionNote(e.target.value)}
              placeholder="Manager approval note (optional)..."
              className="w-full bg-white border border-[#CBD5E1] rounded-lg p-3 text-xs"
              rows={3}
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowApproveModal(false)} className="px-3 py-1.5 text-xs font-bold text-[#64748B]">Cancel</button>
              <button
                onClick={() => handleTicketAction(roleUpper === "MANAGER" ? "manager_approve" : "approve")}
                disabled={actionLoading}
                className="px-4 py-1.5 text-xs font-bold bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
              >
                Confirm Approval
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── REJECT MODAL ───────────────────────────────────────────────────── */}
      {showRejectModal && (
        <div className="fixed inset-0 z-60 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full border border-[#E2E8F0] shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-[#0F172A]">Reject Request #{t.ticket_id}</h3>
            <textarea
              value={actionNote}
              onChange={(e) => setActionNote(e.target.value)}
              placeholder="Reason for rejection (required)..."
              className="w-full bg-white border border-[#CBD5E1] rounded-lg p-3 text-xs"
              rows={3}
              required
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowRejectModal(false)} className="px-3 py-1.5 text-xs font-bold text-[#64748B]">Cancel</button>
              <button
                onClick={() => handleTicketAction(roleUpper === "MANAGER" ? "manager_reject" : "reject")}
                disabled={actionLoading || !actionNote.trim()}
                className="px-4 py-1.5 text-xs font-bold bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── EDIT MODAL (ADMIN) ─────────────────────────────────────────────── */}
      {showEditModal && (
        <div className="fixed inset-0 z-60 bg-slate-900/50 flex items-center justify-center p-4">
          <form onSubmit={handleUpdateTicket} className="bg-white rounded-2xl p-6 max-w-md w-full border border-[#E2E8F0] shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-[#0F172A]">Edit Ticket #{t.ticket_id}</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-[#475569] block mb-1">Category</label>
                <input
                  type="text"
                  value={editCategory}
                  onChange={(e) => setEditCategory(e.target.value)}
                  className="w-full bg-white border border-[#CBD5E1] rounded-lg p-2 text-xs"
                />
              </div>
              <div>
                <label className="font-bold text-[#475569] block mb-1">Priority</label>
                <select
                  value={editPriority}
                  onChange={(e) => setEditPriority(e.target.value)}
                  className="w-full bg-white border border-[#CBD5E1] rounded-lg p-2 text-xs"
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>
              <div>
                <label className="font-bold text-[#475569] block mb-1">Status</label>
                <select
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value)}
                  className="w-full bg-white border border-[#CBD5E1] rounded-lg p-2 text-xs"
                >
                  <option value="NEW">NEW</option>
                  <option value="ASSIGNED">ASSIGNED</option>
                  <option value="IN_PROGRESS">IN_PROGRESS</option>
                  <option value="WAITING">WAITING</option>
                  <option value="PENDING">PENDING</option>
                  <option value="RESOLVED">RESOLVED</option>
                  <option value="CLOSED">CLOSED</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowEditModal(false)} className="px-3 py-1.5 text-xs font-bold text-[#64748B]">Cancel</button>
              <button type="submit" disabled={actionLoading} className="px-4 py-1.5 text-xs font-bold bg-[#E30613] text-white rounded-lg">Save Changes</button>
            </div>
          </form>
        </div>
      )}

    </div>
  );
}
