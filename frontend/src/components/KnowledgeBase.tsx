"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { apiFetch, NetworkError } from "@/lib/apiClient";
import {
  Search, BookOpen, Sparkles, Plus, Edit, Trash2, CheckCircle,
  Archive, History, Upload, Eye, Settings, FileText, ArrowLeft,
  ChevronRight, X, Trash, Download, RefreshCw, Loader2, Tag,
  RotateCcw, EyeOff, BarChart3, Filter, Globe, AlertCircle
} from "lucide-react";
import {
  SearchInput,
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  StatusPill,
  Badge
} from "./shared/UIComponents";

interface Step {
  step: number;
  title: string;
  instruction: string;
  image?: string;
  caption?: string;
}

interface FAQItem {
  question: string;
  answer: string;
}

interface CommonError {
  error: string;
  resolution: string;
}

interface Escalation {
  after_attempts: number;
  team: string;
  condition: string;
}

interface KBArticle {
  article_id: string;
  title: string;
  category: string;
  version: string;
  source: string;
  status: string;
  keywords: string[];
  problem: string;
  symptoms: string[];
  prerequisites: string[];
  troubleshooting_steps: Step[];
  verification: string[];
  common_errors: CommonError[];
  escalation: Escalation;
  screenshots: any[];
  faq: FAQItem[];
  related_articles: string[];
}

interface VersionLog {
  version: string;
  filename: string;
  timestamp: number;
}

const CATEGORIES = [
  "VPN", "PASSWORD_RESET", "OUTLOOK", "PRINTER", "SHARED_MAILBOX",
  "GUEST_WIFI", "IT_ASSET_ALLOCATION", "SOFTWARE_INSTALLATION", "SAP", "DEVICE_HEALTH"
];

const STATUS_TABS = ["ALL", "published", "draft", "archived"] as const;
type StatusTab = typeof STATUS_TABS[number];

const STATUS_COLORS: Record<string, string> = {
  published: "bg-emerald-50 border-emerald-200 text-emerald-700",
  draft: "bg-amber-50 border-amber-200 text-amber-700",
  archived: "bg-slate-100 border-slate-200 text-slate-500",
};

export default function KnowledgeBase() {
  const [user, setUser] = useState<any>(null);
  const [articles, setArticles] = useState<KBArticle[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusTab>("ALL");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [selectedArticle, setSelectedArticle] = useState<KBArticle | null>(null);
  const [activeView, setActiveView] = useState<"dashboard" | "list" | "editor" | "viewer">("dashboard");

  // Editor state
  const [editingArticle, setEditingArticle] = useState<Partial<KBArticle> | null>(null);
  const [editorTab, setEditorTab] = useState<"general" | "steps" | "meta">("general");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Version History
  const [versions, setVersions] = useState<VersionLog[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<any | null>(null);
  const [showVersionsModal, setShowVersionsModal] = useState(false);

  // Import / Export
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("access_token");
    return {
      "Content-Type": "application/json",
      ...(token ? { "Authorization": `Bearer ${token}` } : {})
    };
  }, []);

  const getAuthToken = useCallback(() => localStorage.getItem("access_token") || "", []);

  // Load user from localStorage
  useEffect(() => {
    try {
      const u = JSON.parse(localStorage.getItem("user") || "{}");
      setUser(u);
    } catch { setUser({}); }
  }, []);

  const isAdmin = user?.role === "ADMIN" || user?.role === "admin";

  // Load Articles
  const loadArticles = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await apiFetch("/api/admin/knowledge/articles", { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setArticles(Array.isArray(data) ? data : []);
      } else {
        setErrorMsg("Failed to load knowledge base articles.");
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Connection error loading articles.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [getHeaders]);

  useEffect(() => { loadArticles(); }, [loadArticles]);

  // Dashboard stats
  const stats = useMemo(() => {
    const published = articles.filter(a => a.status === "published").length;
    const draft = articles.filter(a => a.status === "draft").length;
    const archived = articles.filter(a => a.status === "archived").length;
    const cats: Record<string, number> = {};
    articles.forEach(a => {
      if (a.status === "published") cats[a.category] = (cats[a.category] || 0) + 1;
    });
    return { total: articles.length, published, draft, archived, cats };
  }, [articles]);

  // Filtered articles
  const filteredArticles = useMemo(() => {
    return articles.filter(art => {
      if (statusFilter !== "ALL" && art.status !== statusFilter) return false;
      if (categoryFilter !== "ALL" && art.category !== categoryFilter) return false;
      if (!searchTerm.trim()) return true;
      const q = searchTerm.toLowerCase();
      return (
        art.title.toLowerCase().includes(q) ||
        art.article_id.toLowerCase().includes(q) ||
        art.category.toLowerCase().includes(q) ||
        (art.keywords || []).some(k => k.toLowerCase().includes(q)) ||
        (art.symptoms || []).some(s => s.toLowerCase().includes(q)) ||
        (art.problem || "").toLowerCase().includes(q)
      );
    });
  }, [articles, statusFilter, categoryFilter, searchTerm]);

  // Open article viewer
  const openArticle = (art: KBArticle) => {
    setSelectedArticle(art);
    setActiveView("viewer");
  };

  // Handle Create
  const handleCreateNew = () => {
    setEditingArticle({
      title: "New Knowledge Article",
      category: "VPN",
      source: "Bridgestone IT Knowledge Base",
      status: "draft",
      keywords: [],
      problem: "",
      symptoms: [],
      prerequisites: [],
      troubleshooting_steps: [],
      verification: [],
      common_errors: [],
      escalation: { after_attempts: 3, team: "IT Support", condition: "" },
      faq: [],
      related_articles: []
    });
    setEditorTab("general");
    setErrorMsg("");
    setActiveView("editor");
  };

  // Handle Save
  const handleSaveArticle = async () => {
    if (!editingArticle) return;
    if (!editingArticle.title?.trim()) { setErrorMsg("Title is required."); return; }
    if (!editingArticle.problem?.trim()) { setErrorMsg("Problem description is required."); return; }
    setLoading(true);
    setErrorMsg("");
    try {
      const isNew = !editingArticle.article_id;
      const url = isNew
        ? "/api/admin/knowledge/articles"
        : `/api/admin/knowledge/articles/${editingArticle.article_id}`;
      const res = await apiFetch(url, {
        method: isNew ? "POST" : "PUT",
        headers: getHeaders(),
        body: JSON.stringify(editingArticle)
      });
      if (res.ok) {
        setEditingArticle(null);
        await loadArticles(true);
        setActiveView("list");
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Failed to save article.");
      }
    } catch { setErrorMsg("Connection error while saving."); }
    finally { setLoading(false); }
  };

  // Lifecycle actions
  const handleAction = async (article_id: string, action: string, confirmMsg: string) => {
    if (!window.confirm(confirmMsg)) return;
    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${article_id}/${action}`, {
        method: "POST",
        headers: getHeaders()
      });
      if (res.ok) {
        await loadArticles(true);
        setSelectedArticle(null);
        setActiveView("list");
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || `Failed to ${action} article.`);
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg(`Connection error during ${action}.`);
    }
  };

  const handleDelete = async (article_id: string) => {
    if (!window.confirm("Permanently delete this article? This cannot be undone.")) return;
    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${article_id}`, {
        method: "DELETE",
        headers: getHeaders()
      });
      if (res.ok) {
        await loadArticles(true);
        setSelectedArticle(null);
        setActiveView("list");
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Delete failed.");
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Connection error during delete.");
    }
  };

  // Versions
  const loadVersions = async (article_id: string) => {
    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${article_id}/versions`, { headers: getHeaders() });
      if (res.ok) { setVersions(await res.json()); setShowVersionsModal(true); }
    } catch { }
  };

  const loadVersionContent = async (article_id: string, version: string) => {
    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${article_id}/versions/${version}`, { headers: getHeaders() });
      if (res.ok) setSelectedVersion(await res.json());
    } catch { }
  };

  const handleRestoreVersion = (vContent: any) => {
    if (!window.confirm(`Restore article to version ${vContent.version}? Opens as draft.`)) return;
    setEditingArticle({ ...vContent, status: "draft" });
    setShowVersionsModal(false);
    setSelectedVersion(null);
    setEditorTab("general");
    setActiveView("editor");
  };

  // Export
  const handleExport = async () => {
    try {
      const res = await apiFetch("/api/admin/knowledge/articles/export", { headers: getHeaders() });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `bridgestone_kb_export_${new Date().toISOString().split("T")[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { setErrorMsg("Export failed."); }
  };

  // Import
  const handleImport = async (file: File) => {
    if (!file) return;
    setImportLoading(true);
    setImportResult(null);
    const token = getAuthToken();
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await apiFetch("/api/admin/knowledge/import", {
        method: "POST",
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
        body: formData
      });
      if (res.ok) {
        const result = await res.json();
        setImportResult(result);
        await loadArticles(true);
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Import failed.");
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Import connection error.");
    } finally { setImportLoading(false); }
  };

  // Image Upload
  const handleImageUpload = async (stepIndex: number, file: File) => {
    if (!editingArticle?.article_id) {
      alert("Save the article once before uploading images.");
      return;
    }
    const token = getAuthToken();
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${editingArticle.article_id}/upload`, {
        method: "POST",
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        const updatedSteps = [...(editingArticle.troubleshooting_steps || [])];
        updatedSteps[stepIndex] = { ...updatedSteps[stepIndex], image: data.filename };
        setEditingArticle({ ...editingArticle, troubleshooting_steps: updatedSteps });
      } else alert("Upload failed.");
    } catch (e) {
      if (!(e instanceof NetworkError)) alert("Image upload error.");
    }
  };

  // ── RENDER ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex-1 flex flex-col bg-[#F8FAFC] font-sans min-h-screen">

      {/* TOP HEADER */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 sticky top-0 z-20">
        <div className="flex items-center gap-3">
          {activeView !== "dashboard" && (
            <button
              onClick={() => {
                setActiveView(activeView === "editor" || activeView === "viewer" ? "list" : "dashboard");
                setEditingArticle(null); setSelectedArticle(null); setErrorMsg("");
              }}
              className="p-1.5 hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[#475569] cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
          )}
          <div>
            <h1 className="text-xs font-black text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-[#E30613]" />
              Enterprise Knowledge Management Portal
              {activeView === "editor" && editingArticle?.article_id && (
                <span className="text-[#64748B]">— Editing {editingArticle.article_id}</span>
              )}
              {activeView === "editor" && !editingArticle?.article_id && (
                <span className="text-[#64748B]">— New Article</span>
              )}
            </h1>
            <p className="text-[10px] text-[#64748B] font-bold uppercase mt-0.5 tracking-wider">
              Manage SOP documentation used by the AI Service Desk Agent.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {activeView !== "editor" && (
            <button onClick={() => loadArticles(true)} disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer disabled:opacity-50">
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
          )}
          {isAdmin && activeView === "list" && (
            <>
              <button onClick={handleExport}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer">
                <Download className="w-3.5 h-3.5" />
                Export JSON
              </button>
              <label className={`flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer ${importLoading ? "opacity-50" : ""}`}>
                <Upload className="w-3.5 h-3.5" />
                {importLoading ? "Importing..." : "Import JSON"}
                <input type="file" accept=".json" className="hidden" disabled={importLoading}
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleImport(f); e.target.value = ""; }} />
              </label>
              <button onClick={handleCreateNew}
                className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#E30613] hover:bg-red-700 text-white text-xs font-bold rounded-xl cursor-pointer shadow-xs">
                <Plus className="w-3.5 h-3.5" />
                New Article
              </button>
            </>
          )}
          {activeView !== "dashboard" && activeView !== "editor" && (
            <button onClick={() => setActiveView("dashboard")}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer">
              <BarChart3 className="w-3.5 h-3.5" />
              Dashboard
            </button>
          )}
          {activeView === "dashboard" && (
            <button onClick={() => setActiveView("list")}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer">
              <FileText className="w-3.5 h-3.5" />
              All Articles
            </button>
          )}
        </div>
      </div>

      {/* ERROR BANNER */}
      {errorMsg && (
        <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 text-[#DC2626] text-xs font-bold rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2"><AlertCircle className="w-4 h-4" />{errorMsg}</div>
          <button onClick={() => setErrorMsg("")} className="cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* IMPORT RESULT */}
      {importResult && (
        <div className="mx-6 mt-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold rounded-xl flex items-center justify-between">
          <span>✓ Imported {importResult.imported} article(s). Skipped: {importResult.skipped}. IDs: {(importResult.created_ids || []).join(", ")}</span>
          <button onClick={() => setImportResult(null)} className="cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* AI SOURCING BANNER */}
      {activeView !== "editor" && (
        <div className="mx-6 mt-4 p-3 bg-[#FEF2F2] border border-[#FEE2E2] rounded-2xl flex items-start gap-2.5">
          <Sparkles className="w-4 h-4 text-[#E30613] mt-0.5 flex-shrink-0 animate-pulse" />
          <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider">
            AI Agent SOP Sourcing — Only <strong>published</strong> articles are available for AI retrieval. Drafts and archived articles are excluded from the knowledge engine.
          </span>
        </div>
      )}

      {loading ? (
        <div className="flex-1 flex items-center justify-center gap-3 text-xs text-[#64748B]">
          <Loader2 className="w-6 h-6 animate-spin text-[#E30613]" />
          <span>Loading knowledge base...</span>
        </div>
      ) : (

        <div className="p-6 flex-1 space-y-6">

          {/* ── DASHBOARD VIEW ── */}
          {activeView === "dashboard" && (
            <div className="space-y-6">
              {/* KPI Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { label: "Total Articles", value: stats.total, color: "text-[#0F172A]", icon: <BookOpen className="w-4 h-4 text-[#E30613]" />, badge: "All Statuses" },
                  { label: "Published", value: stats.published, color: "text-emerald-700", icon: <Globe className="w-4 h-4 text-emerald-600" />, badge: "AI Active" },
                  { label: "Draft", value: stats.draft, color: "text-amber-700", icon: <Edit className="w-4 h-4 text-amber-600" />, badge: "Not Indexed" },
                  { label: "Archived", value: stats.archived, color: "text-slate-500", icon: <Archive className="w-4 h-4 text-slate-400" />, badge: "Excluded" },
                ].map((c, i) => (
                  <div key={i} className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">{c.label}</span>
                      {c.icon}
                    </div>
                    <div className="flex items-baseline justify-between">
                      <span className={`text-2xl font-black font-mono ${c.color}`}>{c.value}</span>
                      <span className="text-[9px] font-bold text-[#94A3B8] bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded">{c.badge}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Category breakdown */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs">
                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider mb-4 flex items-center gap-2">
                  <Tag className="w-4 h-4 text-[#E30613]" />
                  Published Articles by Category
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  {CATEGORIES.map(cat => {
                    const count = stats.cats[cat] || 0;
                    return (
                      <button
                        key={cat}
                        onClick={() => { setCategoryFilter(cat); setStatusFilter("published"); setActiveView("list"); }}
                        className="border border-[#E2E8F0] rounded-xl p-3 text-left hover:border-[#E30613] hover:bg-[#FEF2F2] transition-all cursor-pointer group"
                      >
                        <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider group-hover:text-[#E30613]">{cat.replace(/_/g, " ")}</div>
                        <div className="text-lg font-black text-[#0F172A] mt-1 font-mono">{count}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quick actions */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs">
                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider mb-4">Quick Actions</h3>
                <div className="flex flex-wrap gap-3">
                  <button onClick={() => setActiveView("list")}
                    className="flex items-center gap-2 px-4 py-2.5 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer">
                    <FileText className="w-4 h-4" /> Browse All Articles
                  </button>
                  {isAdmin && (
                    <>
                      <button onClick={handleCreateNew}
                        className="flex items-center gap-2 px-4 py-2.5 bg-[#E30613] hover:bg-red-700 text-white rounded-xl text-xs font-bold cursor-pointer">
                        <Plus className="w-4 h-4" /> Create New Article
                      </button>
                      <button onClick={handleExport}
                        className="flex items-center gap-2 px-4 py-2.5 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer">
                        <Download className="w-4 h-4" /> Export Knowledge Base
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── LIST VIEW ── */}
          {activeView === "list" && (
            <div className="space-y-4">
              {/* Filter Bar */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 flex flex-wrap gap-3 items-center">
                <div className="flex gap-1 flex-wrap">
                  {STATUS_TABS.map(tab => (
                    <button key={tab} onClick={() => setStatusFilter(tab)}
                      className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg border transition-all cursor-pointer ${statusFilter === tab ? "bg-[#E30613] text-white border-[#E30613]" : "bg-white text-[#64748B] border-[#E2E8F0] hover:border-[#94A3B8]"}`}>
                      {tab === "ALL" ? "All" : tab}
                    </button>
                  ))}
                </div>
                <select
                  value={categoryFilter}
                  onChange={e => setCategoryFilter(e.target.value)}
                  className="px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-[10px] font-bold text-[#475569] bg-white focus:ring-1 focus:ring-[#E30613] outline-none cursor-pointer"
                >
                  <option value="ALL">All Categories</option>
                  {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
                </select>
                <div className="flex-1 min-w-48">
                  <SearchInput
                    placeholder="Search title, keywords, symptoms..."
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                  />
                </div>
                <span className="text-[10px] font-bold text-[#94A3B8] whitespace-nowrap">{filteredArticles.length} article(s)</span>
              </div>

              {/* Articles Table */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-xs">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Article ID</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Version</TableHead>
                      <TableHead>Keywords</TableHead>
                      {isAdmin && <TableHead>Actions</TableHead>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredArticles.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={isAdmin ? 7 : 6} className="text-center py-12 text-xs text-[#94A3B8]">
                          No articles match the selected filters.
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredArticles.map(art => (
                        <TableRow key={art.article_id} onClick={() => openArticle(art)} className="cursor-pointer hover:bg-[#F8FAFC]">
                          <TableCell className="font-mono font-bold text-[#0F172A] text-[11px]">{art.article_id}</TableCell>
                          <TableCell className="font-bold text-[#0F172A] max-w-xs">
                            <div className="truncate">{art.title}</div>
                            <div className="text-[10px] text-[#64748B] font-medium mt-0.5 truncate">{art.problem}</div>
                          </TableCell>
                          <TableCell>
                            <span className="px-2 py-0.5 text-[9px] font-bold uppercase bg-slate-100 text-slate-600 rounded border border-slate-200">
                              {art.category.replace(/_/g, " ")}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span className={`px-2 py-0.5 text-[9px] font-bold uppercase rounded border ${STATUS_COLORS[art.status] || "bg-slate-100 border-slate-200 text-slate-500"}`}>
                              {art.status}
                            </span>
                          </TableCell>
                          <TableCell className="font-mono text-[11px] font-bold text-[#64748B]">v{art.version || "1.0"}</TableCell>
                          <TableCell className="max-w-xs">
                            <div className="flex flex-wrap gap-1">
                              {(art.keywords || []).slice(0, 3).map(k => (
                                <span key={k} className="px-1.5 py-0.5 text-[9px] bg-blue-50 text-blue-700 border border-blue-200 rounded font-bold">{k}</span>
                              ))}
                              {(art.keywords || []).length > 3 && (
                                <span className="text-[9px] text-[#94A3B8] font-bold">+{art.keywords.length - 3}</span>
                              )}
                            </div>
                          </TableCell>
                          {isAdmin && (
                            <TableCell onClick={e => e.stopPropagation()}>
                              <div className="flex items-center gap-1">
                                <button onClick={() => { setEditingArticle(art); setEditorTab("general"); setActiveView("editor"); }}
                                  className="p-1.5 hover:bg-[#F1F5F9] rounded-lg cursor-pointer text-[#64748B]" title="Edit">
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                {art.status === "draft" && (
                                  <button onClick={() => handleAction(art.article_id, "publish", "Publish this article? It will be activated for AI retrieval.")}
                                    className="p-1.5 hover:bg-emerald-50 rounded-lg cursor-pointer text-emerald-600" title="Publish">
                                    <CheckCircle className="w-3.5 h-3.5" />
                                  </button>
                                )}
                                {art.status === "published" && (
                                  <>
                                    <button onClick={() => handleAction(art.article_id, "unpublish", "Unpublish and revert to draft?")}
                                      className="p-1.5 hover:bg-amber-50 rounded-lg cursor-pointer text-amber-600" title="Unpublish">
                                      <EyeOff className="w-3.5 h-3.5" />
                                    </button>
                                    <button onClick={() => handleAction(art.article_id, "archive", "Archive this article? It will be excluded from AI retrieval.")}
                                      className="p-1.5 hover:bg-slate-100 rounded-lg cursor-pointer text-slate-500" title="Archive">
                                      <Archive className="w-3.5 h-3.5" />
                                    </button>
                                  </>
                                )}
                                {art.status === "archived" && (
                                  <button onClick={() => handleAction(art.article_id, "restore", "Restore this article to draft?")}
                                    className="p-1.5 hover:bg-emerald-50 rounded-lg cursor-pointer text-emerald-600" title="Restore">
                                    <RotateCcw className="w-3.5 h-3.5" />
                                  </button>
                                )}
                                <button onClick={() => loadVersions(art.article_id)}
                                  className="p-1.5 hover:bg-[#F1F5F9] rounded-lg cursor-pointer text-[#64748B]" title="Version History">
                                  <History className="w-3.5 h-3.5" />
                                </button>
                                <button onClick={() => handleDelete(art.article_id)}
                                  className="p-1.5 hover:bg-red-50 rounded-lg cursor-pointer text-red-500" title="Delete">
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </TableCell>
                          )}
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}

          {/* ── ARTICLE VIEWER ── */}
          {activeView === "viewer" && selectedArticle && (
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-6">
              {/* Header */}
              <div className="border-b border-[#E2E8F0] pb-4 flex justify-between items-start">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider font-mono">{selectedArticle.article_id}</span>
                    <span className="w-1 h-1 rounded-full bg-[#E2E8F0]" />
                    <span className={`px-2 py-0.5 text-[9px] font-bold uppercase rounded border ${STATUS_COLORS[selectedArticle.status] || ""}`}>
                      {selectedArticle.status}
                    </span>
                    <span className="text-[10px] font-bold text-[#94A3B8] uppercase">v{selectedArticle.version || "1.0"}</span>
                    <span className="px-2 py-0.5 text-[9px] font-bold uppercase bg-slate-100 text-slate-600 rounded border border-slate-200">
                      {selectedArticle.category.replace(/_/g, " ")}
                    </span>
                  </div>
                  <h2 className="text-sm font-black text-[#0F172A] uppercase tracking-wide">{selectedArticle.title}</h2>
                  <p className="text-xs text-[#64748B] font-medium">{selectedArticle.source}</p>
                </div>
                {isAdmin && (
                  <div className="flex gap-2">
                    <button onClick={() => { setEditingArticle(selectedArticle); setEditorTab("general"); setActiveView("editor"); }}
                      className="p-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569] rounded-xl cursor-pointer" title="Edit">
                      <Edit className="w-4 h-4" />
                    </button>
                    <button onClick={() => loadVersions(selectedArticle.article_id)}
                      className="p-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569] rounded-xl cursor-pointer" title="Versions">
                      <History className="w-4 h-4" />
                    </button>
                    {selectedArticle.status === "draft" && (
                      <button onClick={() => handleAction(selectedArticle.article_id, "publish", "Publish this article?")}
                        className="p-1.5 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded-xl cursor-pointer" title="Publish">
                        <CheckCircle className="w-4 h-4" />
                      </button>
                    )}
                    {selectedArticle.status === "published" && (
                      <button onClick={() => handleAction(selectedArticle.article_id, "archive", "Archive this article?")}
                        className="p-1.5 bg-amber-50 border border-amber-200 hover:bg-amber-100 text-amber-700 rounded-xl cursor-pointer" title="Archive">
                        <Archive className="w-4 h-4" />
                      </button>
                    )}
                    {selectedArticle.status === "archived" && (
                      <button onClick={() => handleAction(selectedArticle.article_id, "restore", "Restore to draft?")}
                        className="p-1.5 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded-xl cursor-pointer" title="Restore">
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    )}
                    <button onClick={() => handleDelete(selectedArticle.article_id)}
                      className="p-1.5 bg-red-50 border border-red-200 hover:bg-red-100 text-red-600 rounded-xl cursor-pointer" title="Delete">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>

              {/* Keywords / Tags */}
              {(selectedArticle.keywords || []).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {selectedArticle.keywords.map(k => (
                    <span key={k} className="px-2 py-0.5 text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200 rounded-lg">{k}</span>
                  ))}
                </div>
              )}

              {/* Body Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
                <div>
                  <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block mb-2">Problem / Objective</span>
                  <p className="text-[#334155] font-medium leading-relaxed">{selectedArticle.problem}</p>
                </div>
                {(selectedArticle.symptoms || []).length > 0 && (
                  <div className="border-l border-[#E2E8F0] pl-4">
                    <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block mb-2">Symptoms</span>
                    <ul className="space-y-1 list-disc list-inside text-[#475569] font-medium">
                      {selectedArticle.symptoms.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                )}
              </div>

              {/* Steps */}
              {(selectedArticle.troubleshooting_steps || []).length > 0 && (
                <div className="space-y-3">
                  <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Troubleshooting Steps</span>
                  {selectedArticle.troubleshooting_steps.map((step, idx) => (
                    <div key={idx} className="flex gap-4 items-start bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl p-4">
                      <div className="w-7 h-7 rounded-full bg-[#FEF2F2] border border-[#FEE2E2] text-[#E30613] flex items-center justify-center text-xs font-black flex-shrink-0">
                        {step.step}
                      </div>
                      <div className="flex-1 space-y-1.5">
                        <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">{step.title}</h4>
                        <p className="text-[11px] text-[#475569] font-medium leading-relaxed">{step.instruction}</p>
                        {step.image && (
                          <div className="mt-2 max-w-sm border border-[#E2E8F0] rounded-xl overflow-hidden">
                            <img src={`/images/${step.image}`} alt={step.caption} className="w-full object-cover" />
                            {step.caption && <p className="text-[9px] text-[#64748B] text-center italic py-1 font-bold uppercase">{step.caption}</p>}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Verification + Prerequisites */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-[#E2E8F0] pt-4">
                {(selectedArticle.prerequisites || []).length > 0 && (
                  <div>
                    <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block mb-2">Prerequisites</span>
                    <ul className="list-disc list-inside text-xs text-[#475569] space-y-0.5 font-medium">
                      {selectedArticle.prerequisites.map((p, i) => <li key={i}>{p}</li>)}
                    </ul>
                  </div>
                )}
                {(selectedArticle.verification || []).length > 0 && (
                  <div>
                    <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block mb-2">Verification Checks</span>
                    <ul className="list-disc list-inside text-xs text-[#475569] space-y-0.5 font-medium">
                      {selectedArticle.verification.map((v, i) => <li key={i}>{v}</li>)}
                    </ul>
                  </div>
                )}
              </div>

              {/* FAQ */}
              {(selectedArticle.faq || []).length > 0 && (
                <div className="space-y-3 border-t border-[#E2E8F0] pt-4">
                  <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Frequently Asked Questions</span>
                  {selectedArticle.faq.map((f, i) => (
                    <div key={i} className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3">
                      <p className="text-xs font-bold text-[#0F172A]">{f.question}</p>
                      <p className="text-[11px] text-[#475569] font-medium mt-1 leading-relaxed">{f.answer}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── EDITOR VIEW ── */}
          {activeView === "editor" && editingArticle && (
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-6">
              {/* Editor Header */}
              <div className="flex justify-between items-center border-b border-[#E2E8F0] pb-4">
                <div>
                  <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                    {editingArticle.article_id ? `Edit: ${editingArticle.article_id}` : "Create New Article"}
                  </h3>
                  <p className="text-[10px] text-[#64748B] font-bold mt-0.5 uppercase">
                    v{editingArticle.version || "1.0"} · {editingArticle.status || "draft"}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => { setEditingArticle(null); setActiveView("list"); }}
                    className="px-4 py-2 border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#475569] text-xs font-bold rounded-xl cursor-pointer">
                    Cancel
                  </button>
                  <button onClick={handleSaveArticle} disabled={loading}
                    className="px-4 py-2 bg-[#E30613] hover:bg-red-700 text-white text-xs font-bold rounded-xl cursor-pointer disabled:opacity-50 shadow-xs">
                    {loading ? "Saving..." : "Save Article"}
                  </button>
                </div>
              </div>

              {/* Editor Tabs */}
              <div className="flex border-b border-[#E2E8F0]">
                {(["general", "steps", "meta"] as const).map(tab => (
                  <button key={tab} onClick={() => setEditorTab(tab)}
                    className={`px-4 py-2 border-b-2 text-xs font-bold uppercase cursor-pointer -mb-px transition-all ${editorTab === tab ? "border-[#E30613] text-[#E30613]" : "border-transparent text-[#94A3B8] hover:text-[#475569]"}`}>
                    {tab === "general" ? "General Info" : tab === "steps" ? "Steps" : "Metadata & Rules"}
                  </button>
                ))}
              </div>

              {errorMsg && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs font-bold rounded-xl">{errorMsg}</div>
              )}

              {/* TAB: GENERAL */}
              {editorTab === "general" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="md:col-span-2 space-y-1">
                      <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Article Title *</label>
                      <input type="text" value={editingArticle.title || ""}
                        onChange={e => setEditingArticle({ ...editingArticle, title: e.target.value })}
                        className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs font-semibold focus:ring-1 focus:ring-[#E30613] outline-none"
                        placeholder="e.g. GlobalProtect VPN Troubleshooting" />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Category</label>
                      <select value={editingArticle.category || "VPN"}
                        onChange={e => setEditingArticle({ ...editingArticle, category: e.target.value })}
                        className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs bg-white focus:ring-1 focus:ring-[#E30613] outline-none font-bold">
                        {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Problem Description *</label>
                    <textarea rows={3} value={editingArticle.problem || ""}
                      onChange={e => setEditingArticle({ ...editingArticle, problem: e.target.value })}
                      className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none resize-none font-medium"
                      placeholder="Describe the issue this article resolves..." />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Symptoms (one per line)</label>
                      <textarea rows={4} value={(editingArticle.symptoms || []).join("\n")}
                        onChange={e => setEditingArticle({ ...editingArticle, symptoms: e.target.value.split("\n") })}
                        className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none font-mono"
                        placeholder={"Connection timeout\nAuthentication failed"} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Keywords / Tags (comma separated)</label>
                      <textarea rows={4} value={(editingArticle.keywords || []).join(", ")}
                        onChange={e => setEditingArticle({ ...editingArticle, keywords: e.target.value.split(",").map(k => k.trim()).filter(Boolean) })}
                        className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none font-mono"
                        placeholder="vpn, globalprotect, remote access" />
                    </div>
                  </div>
                </div>
              )}

              {/* TAB: STEPS */}
              {editorTab === "steps" && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Troubleshooting Steps</span>
                    <button onClick={() => {
                      const steps = [...(editingArticle.troubleshooting_steps || [])];
                      steps.push({ step: steps.length + 1, title: "New Step", instruction: "" });
                      setEditingArticle({ ...editingArticle, troubleshooting_steps: steps });
                    }} className="flex items-center gap-1 px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl cursor-pointer">
                      <Plus className="w-3.5 h-3.5" /> Add Step
                    </button>
                  </div>
                  <div className="space-y-4">
                    {(editingArticle.troubleshooting_steps || []).map((step, idx) => (
                      <div key={idx} className="border border-[#E2E8F0] rounded-2xl p-4 bg-[#F8FAFC] relative group">
                        <button onClick={() => {
                          const steps = [...(editingArticle.troubleshooting_steps || [])];
                          steps.splice(idx, 1);
                          setEditingArticle({ ...editingArticle, troubleshooting_steps: steps.map((s, i) => ({ ...s, step: i + 1 })) });
                        }} className="absolute top-3 right-3 p-1 hover:bg-red-50 rounded-lg text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 cursor-pointer">
                          <Trash2 className="w-4 h-4" />
                        </button>
                        <div className="grid grid-cols-12 gap-3">
                          <div className="col-span-1 flex flex-col items-center justify-center bg-white border border-[#E2E8F0] rounded-xl p-2 h-14">
                            <span className="text-[9px] font-bold text-[#64748B] uppercase">Step</span>
                            <span className="text-base font-black text-[#0F172A]">{step.step}</span>
                          </div>
                          <div className="col-span-11 space-y-2">
                            <input type="text" value={step.title}
                              onChange={e => {
                                const steps = [...(editingArticle.troubleshooting_steps || [])];
                                steps[idx] = { ...step, title: e.target.value };
                                setEditingArticle({ ...editingArticle, troubleshooting_steps: steps });
                              }}
                              className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs font-bold focus:ring-1 focus:ring-[#E30613] outline-none bg-white"
                              placeholder="Step title" />
                            <textarea rows={2} value={step.instruction}
                              onChange={e => {
                                const steps = [...(editingArticle.troubleshooting_steps || [])];
                                steps[idx] = { ...step, instruction: e.target.value };
                                setEditingArticle({ ...editingArticle, troubleshooting_steps: steps });
                              }}
                              className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none bg-white resize-none"
                              placeholder="Detailed instruction..." />
                          </div>
                        </div>
                      </div>
                    ))}
                    {(editingArticle.troubleshooting_steps || []).length === 0 && (
                      <div className="text-center py-10 border-2 border-dashed border-[#E2E8F0] rounded-2xl text-[#94A3B8] text-xs font-bold uppercase">
                        No steps yet. Click "Add Step" to begin.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB: META */}
              {editorTab === "meta" && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Prerequisites (one per line)</label>
                      <textarea rows={4} value={(editingArticle.prerequisites || []).join("\n")}
                        onChange={e => setEditingArticle({ ...editingArticle, prerequisites: e.target.value.split("\n").filter(Boolean) })}
                        className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none font-mono" />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Verification Checks (one per line)</label>
                      <textarea rows={4} value={(editingArticle.verification || []).join("\n")}
                        onChange={e => setEditingArticle({ ...editingArticle, verification: e.target.value.split("\n").filter(Boolean) })}
                        className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none font-mono" />
                    </div>
                  </div>
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl p-4 space-y-3">
                    <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block">Escalation Configuration</span>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-[#64748B] uppercase">Escalate After</label>
                        <input type="number" value={editingArticle.escalation?.after_attempts || 3}
                          onChange={e => setEditingArticle({ ...editingArticle, escalation: { ...(editingArticle.escalation || { team: "IT Support", condition: "" }), after_attempts: parseInt(e.target.value, 10) || 3 } })}
                          className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs bg-white outline-none" />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-[#64748B] uppercase">Escalation Team</label>
                        <input type="text" value={editingArticle.escalation?.team || "IT Support"}
                          onChange={e => setEditingArticle({ ...editingArticle, escalation: { ...(editingArticle.escalation || { after_attempts: 3, condition: "" }), team: e.target.value } })}
                          className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs bg-white outline-none" />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-[#64748B] uppercase">Condition</label>
                        <input type="text" value={editingArticle.escalation?.condition || ""}
                          onChange={e => setEditingArticle({ ...editingArticle, escalation: { ...(editingArticle.escalation || { after_attempts: 3, team: "IT Support" }), condition: e.target.value } })}
                          className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs bg-white outline-none"
                          placeholder="e.g. Escalate if VPN fails" />
                      </div>
                    </div>
                  </div>
                  {/* FAQ */}
                  <div className="space-y-3 border-t border-[#E2E8F0] pt-4">
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">FAQs</span>
                      <button onClick={() => {
                        const faqs = [...(editingArticle.faq || [])];
                        faqs.push({ question: "", answer: "" });
                        setEditingArticle({ ...editingArticle, faq: faqs });
                      }} className="flex items-center gap-1 px-3 py-1 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl cursor-pointer">
                        <Plus className="w-3 h-3" /> Add FAQ
                      </button>
                    </div>
                    {(editingArticle.faq || []).map((faqItem, idx) => (
                      <div key={idx} className="flex gap-3 items-start border border-[#E2E8F0] rounded-xl p-3">
                        <div className="flex-1 space-y-2">
                          <input type="text" value={faqItem.question}
                            onChange={e => {
                              const faqs = [...(editingArticle.faq || [])];
                              faqs[idx] = { ...faqItem, question: e.target.value };
                              setEditingArticle({ ...editingArticle, faq: faqs });
                            }}
                            className="w-full px-2.5 py-1 border border-[#E2E8F0] rounded-lg text-xs font-bold focus:ring-1 focus:ring-[#E30613] outline-none"
                            placeholder="Question?" />
                          <input type="text" value={faqItem.answer}
                            onChange={e => {
                              const faqs = [...(editingArticle.faq || [])];
                              faqs[idx] = { ...faqItem, answer: e.target.value };
                              setEditingArticle({ ...editingArticle, faq: faqs });
                            }}
                            className="w-full px-2.5 py-1 border border-[#E2E8F0] rounded-lg text-xs focus:ring-1 focus:ring-[#E30613] outline-none"
                            placeholder="Answer..." />
                        </div>
                        <button onClick={() => {
                          const faqs = [...(editingArticle.faq || [])];
                          faqs.splice(idx, 1);
                          setEditingArticle({ ...editingArticle, faq: faqs });
                        }} className="p-1 text-red-400 hover:bg-red-50 rounded-lg cursor-pointer">
                          <Trash className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* VERSION HISTORY MODAL */}
      {showVersionsModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-2xl max-w-4xl w-full flex flex-col h-[80vh] overflow-hidden">
            <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
              <div>
                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">Version History</h3>
                <p className="text-[10px] text-[#64748B] font-bold mt-0.5 uppercase tracking-wider">Select a snapshot to preview or restore.</p>
              </div>
              <button onClick={() => { setShowVersionsModal(false); setSelectedVersion(null); }}
                className="p-1 hover:bg-[#F8FAFC] border border-transparent hover:border-[#E2E8F0] rounded-lg text-[#94A3B8] cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 min-h-0 flex overflow-hidden">
              <div className="w-1/3 border-r border-[#E2E8F0] overflow-y-auto p-4 space-y-2 bg-[#F8FAFC]">
                <span className="text-[9px] font-black text-[#64748B] uppercase tracking-wider block mb-2">Snapshots</span>
                {versions.length === 0 ? (
                  <div className="text-center py-8 text-xs text-[#94A3B8] font-bold italic">No version history yet.</div>
                ) : versions.map(v => (
                  <div key={v.version} onClick={() => loadVersionContent(selectedArticle?.article_id || "", v.version)}
                    className={`p-3 border rounded-xl cursor-pointer transition-all ${selectedVersion?.version === v.version ? "border-[#E30613] bg-white" : "border-[#E2E8F0] bg-white hover:border-[#94A3B8]"}`}>
                    <div className="flex justify-between items-center text-xs font-bold uppercase">
                      <span>v{v.version}</span>
                      <ChevronRight className="w-3.5 h-3.5 text-[#94A3B8]" />
                    </div>
                    <p className="text-[9px] text-[#64748B] font-bold mt-0.5">{new Date(v.timestamp * 1000).toLocaleString()}</p>
                  </div>
                ))}
              </div>
              <div className="w-2/3 overflow-y-auto p-6">
                {selectedVersion ? (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center border-b border-[#E2E8F0] pb-3">
                      <div>
                        <h4 className="text-xs font-bold text-[#0F172A] uppercase">{selectedVersion.title}</h4>
                        <span className="text-[9px] text-[#64748B] font-bold uppercase">v{selectedVersion.version}</span>
                      </div>
                      <button onClick={() => handleRestoreVersion(selectedVersion)}
                        className="px-3.5 py-1.5 bg-[#E30613] hover:bg-red-700 text-white text-xs font-bold rounded-xl cursor-pointer">
                        Restore this Version
                      </button>
                    </div>
                    <div className="text-xs space-y-3">
                      <div>
                        <span className="text-[9px] font-bold text-[#64748B] uppercase block">Problem</span>
                        <p className="text-[#334155] font-medium">{selectedVersion.problem}</p>
                      </div>
                      <div>
                        <span className="text-[9px] font-bold text-[#64748B] uppercase block">Steps Count</span>
                        <p className="text-[#334155] font-medium">{(selectedVersion.troubleshooting_steps || []).length} steps</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center text-[#94A3B8]">
                    <FileText className="w-10 h-10 text-[#CBD5E1] mb-3" />
                    <span className="text-xs font-bold uppercase">Select a version to preview</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
