import React, { useState, useEffect } from "react";
import {
  Bell, Check, CheckCheck, Trash2, X, RefreshCw, AlertTriangle,
  CheckCircle2, Clock, MessageSquare, ShieldAlert, FileText, UserCheck, Shield
} from "lucide-react";
import { API_BASE_URL } from "../lib/apiClient";

export interface NotificationItem {
  id: number | string;
  user_id: str;
  ticket_id?: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  read_at?: string;
}

interface NotificationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  token: string | null;
  onNotificationCountChange?: (count: number) => void;
}

export default function NotificationDrawer({
  isOpen,
  onClose,
  token,
  onNotificationCountChange
}: NotificationDrawerProps) {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [actionLoading, setActionLoading] = useState<string | number | null>(null);

  const effectiveToken = token || (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);

  const fetchNotifications = async () => {
    if (!isOpen) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/notifications`, {
        headers: effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(Array.isArray(data) ? data : []);
        const unreadCount = (data || []).filter((n: NotificationItem) => !n.is_read).length;
        if (onNotificationCountChange) {
          onNotificationCountChange(unreadCount);
        }
      }
    } catch (err) {
      console.error("Failed to fetch notifications:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen, effectiveToken]);

  const handleMarkAsRead = async (id: number | string) => {
    setActionLoading(id);
    try {
      const res = await fetch(`${API_BASE_URL}/notifications/read/${id}`, {
        method: "POST",
        headers: effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {},
      });
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n))
        );
        if (onNotificationCountChange) {
          const updatedUnread = notifications.filter((n) => n.id !== id && !n.is_read).length;
          onNotificationCountChange(updatedUnread);
        }
      }
    } catch (err) {
      console.error("Failed to mark notification as read:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleMarkAllAsRead = async () => {
    setActionLoading("all");
    try {
      const res = await fetch(`${API_BASE_URL}/notifications/read-all`, {
        method: "POST",
        headers: effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {},
      });
      if (res.ok) {
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
        if (onNotificationCountChange) {
          onNotificationCountChange(0);
        }
      }
    } catch (err) {
      console.error("Failed to mark all as read:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (id: number | string) => {
    setActionLoading(id);
    try {
      const res = await fetch(`${API_BASE_URL}/notifications/${id}`, {
        method: "DELETE",
        headers: effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {},
      });
      if (res.ok) {
        const remaining = notifications.filter((n) => n.id !== id);
        setNotifications(remaining);
        if (onNotificationCountChange) {
          onNotificationCountChange(remaining.filter((n) => !n.is_read).length);
        }
      }
    } catch (err) {
      console.error("Failed to delete notification:", err);
    } finally {
      setActionLoading(null);
    }
  };

  if (!isOpen) return null;

  const unreadCount = notifications.filter((n) => !n.is_read).length;
  const filteredNotifications = notifications.filter((n) =>
    filter === "unread" ? !n.is_read : true
  );

  const getNotificationIcon = (type: string) => {
    const t = (type || "").toUpperCase();
    if (t.includes("APPROVAL")) return <Shield className="w-4 h-4 text-purple-600" />;
    if (t.includes("SLA")) return <AlertTriangle className="w-4 h-4 text-amber-500" />;
    if (t.includes("RESOLVED") || t.includes("CLOSED")) return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
    if (t.includes("ASSIGN")) return <UserCheck className="w-4 h-4 text-blue-600" />;
    if (t.includes("COMMENT")) return <MessageSquare className="w-4 h-4 text-indigo-600" />;
    if (t.includes("CREATED")) return <FileText className="w-4 h-4 text-red-600" />;
    return <Bell className="w-4 h-4 text-[#E30613]" />;
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;
      return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden font-sans">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity duration-200"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl border-l border-[#E2E8F0] flex flex-col">
          {/* Header */}
          <div className="px-5 py-4 bg-[#F8FAFC] border-b border-[#E2E8F0] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[#FEF2F2] border border-[#FCA5A5] flex items-center justify-center">
                <Bell className="w-4 h-4 text-[#E30613]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-[#0F172A]">Notifications</h2>
                  {unreadCount > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-[#E30613] text-white">
                      {unreadCount} new
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[#64748B]">Enterprise ITSM Activity Stream</p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllAsRead}
                  disabled={actionLoading === "all"}
                  className="px-2.5 py-1 text-[11px] font-semibold text-[#E30613] hover:bg-[#FEF2F2] rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
                  title="Mark all as read"
                >
                  <CheckCheck className="w-3.5 h-3.5" />
                  <span>Mark all read</span>
                </button>
              )}
              <button
                onClick={onClose}
                className="p-1.5 text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-lg transition-colors cursor-pointer"
                aria-label="Close notifications"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="px-5 py-2.5 bg-white border-b border-[#E2E8F0] flex items-center justify-between">
            <div className="flex gap-1 bg-[#F1F5F9] p-1 rounded-lg">
              <button
                onClick={() => setFilter("all")}
                className={`px-3 py-1 rounded-md text-[11px] font-bold transition-all cursor-pointer ${
                  filter === "all"
                    ? "bg-white text-[#0F172A] shadow-xs"
                    : "text-[#64748B] hover:text-[#0F172A]"
                }`}
              >
                All ({notifications.length})
              </button>
              <button
                onClick={() => setFilter("unread")}
                className={`px-3 py-1 rounded-md text-[11px] font-bold transition-all cursor-pointer ${
                  filter === "unread"
                    ? "bg-white text-[#E30613] shadow-xs"
                    : "text-[#64748B] hover:text-[#0F172A]"
                }`}
              >
                Unread ({unreadCount})
              </button>
            </div>

            <button
              onClick={fetchNotifications}
              disabled={loading}
              className="p-1.5 text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-lg transition-colors cursor-pointer"
              title="Refresh"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          {/* Notification List */}
          <div className="flex-1 overflow-y-auto divide-y divide-[#F1F5F9]">
            {loading && notifications.length === 0 ? (
              <div className="p-8 text-center text-xs text-[#64748B] flex flex-col items-center gap-2">
                <RefreshCw className="w-5 h-5 animate-spin text-[#E30613]" />
                <span>Loading notifications...</span>
              </div>
            ) : filteredNotifications.length === 0 ? (
              <div className="p-12 text-center text-xs text-[#64748B] flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-[#F8FAFC] border border-[#E2E8F0] flex items-center justify-center text-[#94A3B8]">
                  <Bell className="w-6 h-6" />
                </div>
                <div>
                  <p className="font-bold text-[#0F172A]">No notifications</p>
                  <p className="text-[11px] text-[#94A3B8] mt-0.5">
                    {filter === "unread" ? "You're all caught up!" : "No recent activity to show."}
                  </p>
                </div>
              </div>
            ) : (
              filteredNotifications.map((notif) => (
                <div
                  key={notif.id}
                  className={`p-4 transition-colors flex items-start gap-3 relative group ${
                    !notif.is_read ? "bg-[#FEF2F2]/40" : "hover:bg-[#F8FAFC]"
                  }`}
                >
                  {/* Icon */}
                  <div className="mt-0.5 flex-shrink-0 w-8 h-8 rounded-lg bg-white border border-[#E2E8F0] shadow-xs flex items-center justify-center">
                    {getNotificationIcon(notif.type)}
                  </div>

                  {/* Body */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className={`text-[12px] truncate ${!notif.is_read ? "font-bold text-[#0F172A]" : "font-semibold text-[#334155]"}`}>
                        {notif.title}
                      </h3>
                      <span className="text-[10px] text-[#94A3B8] whitespace-nowrap flex-shrink-0">
                        {formatTime(notif.created_at)}
                      </span>
                    </div>

                    <p className="text-[11px] text-[#475569] mt-0.5 leading-relaxed break-words">
                      {notif.message}
                    </p>

                    <div className="mt-2 flex items-center justify-between gap-2">
                      {notif.ticket_id ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">
                          #{notif.ticket_id}
                        </span>
                      ) : <span />}

                      {/* Actions */}
                      <div className="flex items-center gap-1.5">
                        {!notif.is_read && (
                          <button
                            onClick={() => handleMarkAsRead(notif.id)}
                            disabled={actionLoading === notif.id}
                            className="px-2 py-0.5 text-[10px] font-bold text-[#E30613] hover:bg-[#FEF2F2] border border-[#FCA5A5]/60 rounded transition-colors flex items-center gap-1 cursor-pointer"
                            title="Mark as read"
                          >
                            <Check className="w-3 h-3" />
                            <span>Read</span>
                          </button>
                        )}

                        <button
                          onClick={() => handleDelete(notif.id)}
                          disabled={actionLoading === notif.id}
                          className="p-1 text-[#94A3B8] hover:text-red-600 hover:bg-red-50 rounded transition-colors cursor-pointer"
                          title="Delete notification"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {!notif.is_read && (
                    <span className="absolute top-4 right-2 w-1.5 h-1.5 rounded-full bg-[#E30613]" aria-hidden />
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
