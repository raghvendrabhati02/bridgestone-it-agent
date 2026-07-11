"use client";

import { useState, useEffect } from "react";
import { API_BASE_URL, apiFetch, NetworkError } from "@/lib/apiClient";
import {
  Search, BookOpen, Sparkles, Plus, Edit, Trash2, CheckCircle,
  Archive, History, Upload, Eye, Settings, FileText, ArrowLeft,
  ChevronRight, Image as ImageIcon, X, Trash
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

export default function KnowledgeBase() {

  // State Management
  const [isAdmin, setIsAdmin] = useState(false);
  const [articles, setArticles] = useState<KBArticle[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedArticle, setSelectedArticle] = useState<KBArticle | null>(null);
  
  // Editor State
  const [editingArticle, setEditingArticle] = useState<Partial<KBArticle> | null>(null);
  const [activeTab, setActiveTab] = useState<"general" | "steps" | "others">("general");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);

  // Version History State
  const [versions, setVersions] = useState<VersionLog[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<any | null>(null);
  const [showVersionsModal, setShowVersionsModal] = useState(false);

  // Fetch Headers Helper
  const getHeaders = () => {
    const token = localStorage.getItem("access_token");
    return {
      "Content-Type": "application/json",
      ...(token ? { "Authorization": `Bearer ${token}` } : {})
    };
  };

  // Load All Articles
  const loadArticles = async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/admin/knowledge/articles`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setArticles(data);
      } else {
        setErrorMsg("Failed to load KB articles");
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Connection error loading articles");
      // NetworkError: silently skip — backend may be restarting
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadArticles();
  }, []);

  // Filter articles based on search
  const filteredArticles = articles.filter(art => {
    const isMatchingQuery = 
      art.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      art.article_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      art.category.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (art.keywords && art.keywords.some(k => k.toLowerCase().includes(searchTerm.toLowerCase())));
    
    if (!isAdmin) {
      return isMatchingQuery && art.status === "published";
    }
    return isMatchingQuery;
  });

  // Handle Create New Article Action
  const handleCreateNew = () => {
    const initialDraft: Partial<KBArticle> = {
      title: "New Troubleshooting SOP",
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
      escalation: {
        after_attempts: 3,
        team: "IT Support",
        condition: "Escalate if not resolved after standard steps."
      },
      faq: [],
      related_articles: []
    };
    setEditingArticle(initialDraft);
    setActiveTab("general");
    setErrorMsg("");
  };

  // Save Article (Create or Update)
  const handleSaveArticle = async () => {
    if (!editingArticle) return;
    if (!editingArticle.title?.trim()) {
      setErrorMsg("Title is required.");
      return;
    }
    if (!editingArticle.problem?.trim()) {
      setErrorMsg("Problem description is required.");
      return;
    }

    setLoading(true);
    setErrorMsg("");
    try {
      const isNew = !editingArticle.article_id;
      const url = isNew 
        ? `${API_BASE_URL}/api/admin/knowledge/articles`
        : `${API_BASE_URL}/api/admin/knowledge/articles/${editingArticle.article_id}`;
      
      const method = isNew ? "POST" : "PUT";
      
      const res = await apiFetch(url, {
        method,
        headers: getHeaders(),
        body: JSON.stringify(editingArticle)
      });

      if (res.ok) {
        setEditingArticle(null);
        await loadArticles();
        setSelectedArticle(null);
      } else {
        const errorData = await res.json();
        setErrorMsg(errorData.detail || "Failed to save article");
      }
    } catch (e) {
      setErrorMsg("Connection error while saving");
    } finally {
      setLoading(false);
    }
  };

  // Publish Article
  const handlePublish = async (article_id: string) => {
    if (!window.confirm("Publishing will increment the version and activate this SOP. Continue?")) return;
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/admin/knowledge/articles/${article_id}/publish`, {
        method: "POST",
        headers: getHeaders()
      });
      if (res.ok) {
        await loadArticles();
        setSelectedArticle(null);
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Connection error");
    }
  };

  // Archive Article
  const handleArchive = async (article_id: string) => {
    if (!window.confirm("Archiving will remove this SOP from chatbot active matching. Continue?")) return;
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/admin/knowledge/articles/${article_id}/archive`, {
        method: "POST",
        headers: getHeaders()
      });
      if (res.ok) {
        await loadArticles();
        setSelectedArticle(null);
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Connection error");
    }
  };

  // Delete Article
  const handleDelete = async (article_id: string) => {
    if (!window.confirm("Are you sure you want to permanently delete this article? This action cannot be undone.")) return;
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/admin/knowledge/articles/${article_id}`, {
        method: "DELETE",
        headers: getHeaders()
      });
      if (res.ok) {
        await loadArticles();
        setSelectedArticle(null);
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Connection error");
    }
  };

  // View Version History
  const loadVersions = async (article_id: string) => {
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/admin/knowledge/articles/${article_id}/versions`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setVersions(data);
        setShowVersionsModal(true);
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Could not load versions");
    }
  };

  // View Version Content
  const loadVersionContent = async (article_id: string, version: string) => {
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/admin/knowledge/articles/${article_id}/versions/${version}`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedVersion(data);
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) setErrorMsg("Could not load version content");
    }
  };

  // Restore Historical Version
  const handleRestoreVersion = async (vContent: any) => {
    if (!window.confirm(`Restore article to version ${vContent.version}? This creates a draft.`)) return;
    setEditingArticle({
      ...vContent,
      status: "draft"
    });
    setShowVersionsModal(false);
    setSelectedVersion(null);
  };

  // Handle Step Upload
  const handleImageUpload = async (stepIndex: number, file: File) => {
    if (!editingArticle || !editingArticle.article_id) {
      alert("Please save the article once before uploading images.");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);

    const token = localStorage.getItem("access_token");

    try {
      const res = await apiFetch(`${API_BASE_URL}/api/admin/knowledge/articles/${editingArticle.article_id}/upload`, {
        method: "POST",
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        const updatedSteps = [...(editingArticle.troubleshooting_steps || [])];
        updatedSteps[stepIndex] = {
          ...updatedSteps[stepIndex],
          image: data.filename
        };
        setEditingArticle({
          ...editingArticle,
          troubleshooting_steps: updatedSteps
        });
      } else {
        alert("Upload failed.");
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) alert("Image upload error.");
      else alert("Upload failed: backend is offline.");
    }
  };

  return (
    <div className="p-6 space-y-6 bg-[#F8FAFC] font-sans">
      {/* HEADER SECTION */}
      <div className="pb-4 border-b border-[#E2E8F0] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xs font-black text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[#E30613]" />
            Enterprise Knowledge Base SOP
          </h1>
          <p className="text-[10px] text-[#64748B] font-bold uppercase mt-1 tracking-wider">
            Browse and manage standard operating procedures used by the AI Copilot.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Toggle admin view */}
          <button
            onClick={() => {
              setIsAdmin(!isAdmin);
              setSelectedArticle(null);
              setEditingArticle(null);
            }}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 border text-xs font-bold rounded-xl transition-all cursor-pointer shadow-xs ${
              isAdmin 
                ? "bg-[#FEF2F2] border-[#FCA5A5] text-[#E30613]" 
                : "bg-white border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC]"
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            {isAdmin ? "Admin Mode Active" : "Enable Admin Mode"}
          </button>

          {isAdmin && !editingArticle && (
            <button
              onClick={handleCreateNew}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-[#E30613] hover:bg-red-705 text-white text-xs font-bold rounded-xl cursor-pointer transition-colors shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              New SOP
            </button>
          )}

          <div className="w-64">
            <SearchInput
              placeholder="Search SOP documentation..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setSelectedArticle(null);
              }}
            />
          </div>
        </div>
      </div>

      {/* SOURCING NOTIFICATION BANNER */}
      {!editingArticle && (
        <div className="p-4 bg-[#FEF2F2] border border-[#FEE2E2] rounded-2xl flex items-start gap-2.5 shadow-xs">
          <Sparkles className="w-4.5 h-4.5 text-[#E30613] mt-0.5 flex-shrink-0 animate-pulse" />
          <div>
            <span className="text-xs font-bold text-[#0F172A] block uppercase tracking-wider">AI Agent SOP Sourcing</span>
            <span className="text-[10px] text-[#64748B] font-bold leading-normal block mt-0.5 uppercase tracking-wider">
              The IT Support Assistant queries this Knowledge Base. Validated steps, symptoms, and prerequisites are used to guide users step-by-step during live troubleshoot sessions.
            </span>
          </div>
        </div>
      )}

      {errorMsg && (
        <div className="p-3.5 bg-red-50 border border-red-205 text-[#DC2626] text-xs font-bold rounded-xl flex items-center justify-between shadow-xs">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg("")} className="text-red-500 hover:text-red-700 cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <span className="text-xs text-[#64748B] font-bold uppercase tracking-wider animate-pulse">Processing...</span>
        </div>
      ) : editingArticle ? (
        /* ARTICLE EDITOR VIEW */
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-6">
          <div className="flex justify-between items-center border-b border-[#E2E8F0] pb-3">
            <div className="flex items-center gap-3">
              <button 
                onClick={() => setEditingArticle(null)}
                className="p-1 hover:bg-[#F8FAFC] rounded-lg border border-transparent hover:border-[#E2E8F0] cursor-pointer"
              >
                <ArrowLeft className="w-4.5 h-4.5 text-[#475569]" />
              </button>
              <div>
                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                  {editingArticle.article_id ? `Edit SOP: ${editingArticle.article_id}` : "Create New SOP Draft"}
                </h3>
                <p className="text-[10px] text-[#64748B] font-bold uppercase mt-0.5">
                  Version {editingArticle.version || "1.0"} • {editingArticle.status || "draft"}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setEditingArticle(null)}
                className="px-4 py-2 border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#475569] text-xs font-bold rounded-xl cursor-pointer transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveArticle}
                className="px-4 py-2 bg-[#E30613] hover:bg-red-750 text-white text-xs font-bold rounded-xl cursor-pointer shadow-xs transition-colors"
              >
                Save SOP
              </button>
            </div>
          </div>

          {/* EDITOR TABS */}
          <div className="flex border-b border-[#E2E8F0]">
            {["general", "steps", "others"].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={`px-4 py-2 border-b-2 text-xs font-bold uppercase cursor-pointer -mb-px transition-all ${
                  activeTab === tab 
                    ? "border-[#E30613] text-[#E30613]" 
                    : "border-transparent text-[#94A3B8] hover:text-[#475569]"
                }`}
              >
                {tab === "others" ? "MetaData & Rules" : tab + " info"}
              </button>
            ))}
          </div>

          {/* TAB 1: GENERAL INFO */}
          {activeTab === "general" && (
            <div className="space-y-4 font-semibold text-[#1E293B]">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-1 md:col-span-2">
                  <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">SOP Title</label>
                  <input
                    type="text"
                    value={editingArticle.title || ""}
                    onChange={(e) => setEditingArticle({ ...editingArticle, title: e.target.value })}
                    className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs font-semibold focus:ring-1 focus:ring-[#E30613] outline-none text-[#1E293B]"
                    placeholder="e.g. GlobalProtect VPN Troubleshooting"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Category</label>
                  <select
                    value={editingArticle.category || "VPN"}
                    onChange={(e) => setEditingArticle({ ...editingArticle, category: e.target.value })}
                    className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs bg-white focus:ring-1 focus:ring-[#E30613] outline-none text-[#1E293B] font-bold"
                  >
                    {["VPN", "PASSWORD_RESET", "OUTLOOK", "PRINTER", "SHARED_MAILBOX", "GUEST_WIFI", "IT_ASSET_ALLOCATION", "SOFTWARE_INSTALLATION", "SAP", "DEVICE_HEALTH"].map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Problem Definition</label>
                <textarea
                  rows={2}
                  value={editingArticle.problem || ""}
                  onChange={(e) => setEditingArticle({ ...editingArticle, problem: e.target.value })}
                  className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none text-[#1E293B] font-semibold"
                  placeholder="Detailed description of the user issue..."
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Symptoms (one per line)</label>
                  <textarea
                    rows={4}
                    value={(editingArticle.symptoms || []).join("\n")}
                    onChange={(e) => setEditingArticle({ ...editingArticle, symptoms: e.target.value.split("\n") })}
                    className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none font-mono text-[#1E293B]"
                    placeholder="Connection timeout&#10;Authentication failed"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Search Keywords (comma separated)</label>
                  <textarea
                    rows={4}
                    value={(editingArticle.keywords || []).join(", ")}
                    onChange={(e) => setEditingArticle({ ...editingArticle, keywords: e.target.value.split(",").map(k => k.trim()).filter(Boolean) })}
                    className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none font-mono text-[#1E293B]"
                    placeholder="vpn, globalprotect, remote access"
                  />
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: STEPS */}
          {activeTab === "steps" && (
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Troubleshooting Steps Sequence</span>
                <button
                  onClick={() => {
                    const steps = [...(editingArticle.troubleshooting_steps || [])];
                    steps.push({
                      step: steps.length + 1,
                      title: "New Troubleshooting Action",
                      instruction: ""
                    });
                    setEditingArticle({ ...editingArticle, troubleshooting_steps: steps });
                  }}
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl transition-all cursor-pointer shadow-xs"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Step
                </button>
              </div>

              <div className="space-y-4">
                {(editingArticle.troubleshooting_steps || []).map((step, idx) => (
                  <div key={idx} className="border border-[#E2E8F0] rounded-2xl p-4 bg-[#F8FAFC] relative group">
                    <button
                      onClick={() => {
                        const steps = [...(editingArticle.troubleshooting_steps || [])];
                        steps.splice(idx, 1);
                        const reindexed = steps.map((s, i) => ({ ...s, step: i + 1 }));
                        setEditingArticle({ ...editingArticle, troubleshooting_steps: reindexed });
                      }}
                      className="absolute top-4 right-4 p-1.5 hover:bg-red-50 border border-transparent hover:border-[#FEE2E2] rounded-lg text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 transition-all cursor-pointer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>

                    <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                      <div className="md:col-span-1 flex flex-col items-center justify-center bg-white border border-[#E2E8F0] rounded-xl p-2 h-14">
                        <span className="text-[9px] font-bold text-[#64748B] uppercase tracking-wider">Step</span>
                        <span className="text-base font-black text-[#0F172A]">{step.step}</span>
                      </div>

                      <div className="md:col-span-7 space-y-3 font-semibold text-[#1E293B]">
                        <input
                          type="text"
                          value={step.title}
                          onChange={(e) => {
                            const steps = [...(editingArticle.troubleshooting_steps || [])];
                            steps[idx] = { ...step, title: e.target.value };
                            setEditingArticle({ ...editingArticle, troubleshooting_steps: steps });
                          }}
                          className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs font-bold focus:ring-1 focus:ring-[#E30613] outline-none text-[#0F172A] bg-white"
                          placeholder="Step title"
                        />
                        <textarea
                          rows={2}
                          value={step.instruction}
                          onChange={(e) => {
                            const steps = [...(editingArticle.troubleshooting_steps || [])];
                            steps[idx] = { ...step, instruction: e.target.value };
                            setEditingArticle({ ...editingArticle, troubleshooting_steps: steps });
                          }}
                          className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none text-[#334155] bg-white"
                          placeholder="Action instruction details..."
                        />
                      </div>

                      <div className="md:col-span-4 space-y-2 border-l border-[#E2E8F0] pl-4">
                        <span className="text-[9px] font-bold text-[#64748B] uppercase tracking-wider block">Screenshot Image</span>
                        
                        {step.image ? (
                          <div className="relative aspect-video bg-[#E2E8F0] border border-[#E2E8F0] rounded-xl overflow-hidden">
                            <img
                              src={`/images/${step.image}`}
                              alt={step.caption}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                (e.target as HTMLImageElement).src = "https://images.unsplash.com/photo-1531403009284-440f080d1e12?w=800&auto=format&fit=crop&q=60";
                              }}
                            />
                            <div className="absolute top-1 right-1 flex gap-1">
                              <button
                                onClick={() => {
                                  const steps = [...(editingArticle.troubleshooting_steps || [])];
                                  steps[idx] = { ...step, image: "" };
                                  setEditingArticle({ ...editingArticle, troubleshooting_steps: steps });
                                }}
                                className="p-1 bg-white border border-[#E2E8F0] hover:bg-red-50 rounded-lg shadow-xs text-red-500 cursor-pointer"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        ) : (
                          <label className="flex flex-col items-center justify-center border-2 border-dashed border-[#E2E8F0] hover:border-[#E30613] rounded-xl p-3 text-center cursor-pointer hover:bg-white transition-colors">
                            <Upload className="w-5 h-5 text-[#94A3B8] mb-1" />
                            <span className="text-[10px] text-[#475569] font-bold uppercase">Upload screenshot</span>
                            <input
                              type="file"
                              accept="image/*"
                              className="hidden"
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) {
                                  handleImageUpload(idx, file);
                                }
                              }}
                            />
                          </label>
                        )}

                        <input
                          type="text"
                          value={step.caption || ""}
                          onChange={(e) => {
                            const steps = [...(editingArticle.troubleshooting_steps || [])];
                            steps[idx] = { ...step, caption: e.target.value };
                            setEditingArticle({ ...editingArticle, troubleshooting_steps: steps });
                          }}
                          className="w-full px-2 py-1 border border-[#E2E8F0] rounded-lg text-[10px] font-semibold text-[#334155] focus:ring-1 focus:ring-[#E30613] outline-none"
                          placeholder="Image caption (e.g. Connected Screen)"
                        />
                      </div>
                    </div>
                  </div>
                ))}

                {(editingArticle.troubleshooting_steps || []).length === 0 && (
                  <div className="text-center py-8 border-2 border-dashed border-[#E2E8F0] rounded-2xl text-[#94A3B8] font-bold text-xs italic uppercase">
                    No steps added yet. Add a step to begin troubleshooting workflow.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: OTHERS */}
          {activeTab === "others" && (
            <div className="space-y-6 text-[#1E293B]">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4 font-semibold">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Prerequisites (one per line)</label>
                    <textarea
                      rows={4}
                      value={(editingArticle.prerequisites || []).join("\n")}
                      onChange={(e) => setEditingArticle({ ...editingArticle, prerequisites: e.target.value.split("\n").filter(Boolean) })}
                      className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none font-mono text-[#1E293B]"
                      placeholder="Internet is available.&#10;GlobalProtect Client is installed."
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Verification Checks (one per line)</label>
                    <textarea
                      rows={4}
                      value={(editingArticle.verification || []).join("\n")}
                      onChange={(e) => setEditingArticle({ ...editingArticle, verification: e.target.value.split("\n").filter(Boolean) })}
                      className="w-full px-3.5 py-2 border border-[#E2E8F0] rounded-xl text-xs focus:ring-1 focus:ring-[#E30613] outline-none font-mono text-[#1E293B]"
                      placeholder="GlobalProtect shows Connected.&#10;Internal sites open normally."
                    />
                  </div>
                </div>

                <div className="space-y-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl p-4 font-bold">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block mb-3 tracking-wider">Escalation Configuration</span>
                  
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-[#64748B] uppercase tracking-wider">Escalate After (attempts)</label>
                        <input
                          type="number"
                          value={editingArticle.escalation?.after_attempts || 3}
                          onChange={(e) => setEditingArticle({
                            ...editingArticle,
                            escalation: {
                              ...(editingArticle.escalation || { team: "IT Support", condition: "" }),
                              after_attempts: parseInt(e.target.value, 10) || 3
                            }
                          })}
                          className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs outline-none text-[#1E293B] bg-white font-semibold"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-[#64748B] uppercase tracking-wider">Assignee Escalation Team</label>
                        <input
                          type="text"
                          value={editingArticle.escalation?.team || "IT Support"}
                          onChange={(e) => setEditingArticle({
                            ...editingArticle,
                            escalation: {
                              ...(editingArticle.escalation || { after_attempts: 3, condition: "" }),
                              team: e.target.value
                            }
                          })}
                          className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs outline-none text-[#1E293B] bg-white font-semibold"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[9px] font-bold text-[#64748B] uppercase tracking-wider">Escalation Condition</label>
                      <input
                        type="text"
                        value={editingArticle.escalation?.condition || ""}
                        onChange={(e) => setEditingArticle({
                          ...editingArticle,
                          escalation: {
                            ...(editingArticle.escalation || { after_attempts: 3, team: "IT Support" }),
                            condition: e.target.value
                          }
                        })}
                        className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-xl text-xs outline-none text-[#1E293B] bg-white font-semibold"
                        placeholder="e.g. Escalate if VPN remains disconnected."
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* FAQs Editor */}
              <div className="space-y-4 border-t border-[#E2E8F0] pt-6 font-bold">
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Frequently Asked Questions (FAQ)</span>
                  <button
                    onClick={() => {
                      const faqs = [...(editingArticle.faq || [])];
                      faqs.push({ question: "", answer: "" });
                      setEditingArticle({ ...editingArticle, faq: faqs });
                    }}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl transition-all cursor-pointer shadow-xs"
                  >
                    <Plus className="w-3 h-3" />
                    Add FAQ
                  </button>
                </div>

                <div className="space-y-3">
                  {(editingArticle.faq || []).map((faqItem, idx) => (
                    <div key={idx} className="flex gap-3 items-start border border-[#E2E8F0] rounded-2xl p-3 bg-white">
                      <div className="flex-1 space-y-2 font-semibold">
                        <input
                          type="text"
                          value={faqItem.question}
                          onChange={(e) => {
                            const faqs = [...(editingArticle.faq || [])];
                            faqs[idx] = { ...faqItem, question: e.target.value };
                            setEditingArticle({ ...editingArticle, faq: faqs });
                          }}
                          className="w-full px-2.5 py-1 border border-[#E2E8F0] rounded-lg text-xs font-bold focus:ring-1 focus:ring-[#E30613] outline-none text-[#0F172A]"
                          placeholder="Question Title?"
                        />
                        <input
                          type="text"
                          value={faqItem.answer}
                          onChange={(e) => {
                            const faqs = [...(editingArticle.faq || [])];
                            faqs[idx] = { ...faqItem, answer: e.target.value };
                            setEditingArticle({ ...editingArticle, faq: faqs });
                          }}
                          className="w-full px-2.5 py-1 border border-[#E2E8F0] rounded-lg text-xs focus:ring-1 focus:ring-[#E30613] outline-none text-[#334155]"
                          placeholder="Answer description text..."
                        />
                      </div>
                      <button
                        onClick={() => {
                          const faqs = [...(editingArticle.faq || [])];
                          faqs.splice(idx, 1);
                          setEditingArticle({ ...editingArticle, faq: faqs });
                        }}
                        className="p-1 text-red-500 hover:bg-red-50 border border-transparent hover:border-[#FEE2E2] rounded-lg cursor-pointer"
                      >
                        <Trash className="w-4.5 h-4.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* STANDARD SOP LIST/GRID VIEW */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-4">
            <span className="text-[10px] font-black text-[#64748B] uppercase tracking-wider block">Troubleshoot Guides SOP</span>
            <div className="space-y-3">
              {filteredArticles.map(art => (
                <div
                  key={art.article_id}
                  onClick={() => {
                    setSelectedArticle(art);
                    setSelectedVersion(null);
                  }}
                  className={`card p-4 cursor-pointer transition-all border ${
                    selectedArticle?.article_id === art.article_id 
                      ? "border-[#E30613] bg-white shadow-xs" 
                      : "bg-white border-[#E2E8F0] hover:border-[#94A3B8]"
                  }`}
                >
                  <div className="flex justify-between items-center text-[10px] font-bold text-[#64748B] uppercase mb-1">
                    <span>{art.article_id}</span>
                    <div className="flex items-center gap-1.5">
                      <StatusPill status={art.status || "published"} />
                      <span className="text-[#475569] font-bold">v{art.version || "1.0"}</span>
                    </div>
                  </div>
                  <h4 className="text-xs font-bold text-[#0F172A] leading-tight uppercase tracking-wider">{art.title}</h4>
                  <p className="text-[11px] text-[#475569] mt-2 line-clamp-2 leading-relaxed font-semibold">
                    {art.problem}
                  </p>
                </div>
              ))}

              {filteredArticles.length === 0 && (
                <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl text-center italic text-xs text-[#94A3B8] font-semibold uppercase">
                  No matching reference docs found.
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-2 space-y-4">
            <span className="text-[10px] font-black text-[#64748B] uppercase tracking-wider block">SOP Document Details</span>
            {selectedArticle ? (
              <div className="card p-6 bg-white border border-[#E2E8F0] space-y-6 shadow-xs relative">
                {isAdmin && (
                  <div className="absolute top-6 right-6 flex gap-2">
                    <button
                      onClick={() => loadVersions(selectedArticle.article_id)}
                      className="p-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569] hover:text-[#0F172A] rounded-xl cursor-pointer transition-all shadow-xs"
                      title="Version History"
                    >
                      <History className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        setEditingArticle(selectedArticle);
                        setActiveTab("general");
                        setErrorMsg("");
                      }}
                      className="p-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569] hover:text-[#0F172A] rounded-xl cursor-pointer transition-all shadow-xs"
                      title="Edit Article"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    {selectedArticle.status !== "published" && (
                      <button
                        onClick={() => handlePublish(selectedArticle.article_id)}
                        className="p-1.5 bg-green-50 border border-green-200 hover:bg-green-100 text-[#16A34A] rounded-xl cursor-pointer transition-colors shadow-xs"
                        title="Publish SOP"
                      >
                        <CheckCircle className="w-4 h-4" />
                      </button>
                    )}
                    {selectedArticle.status === "published" && (
                      <button
                        onClick={() => handleArchive(selectedArticle.article_id)}
                        className="p-1.5 bg-amber-50 border border-amber-200 hover:bg-amber-100 text-amber-700 rounded-xl cursor-pointer transition-colors shadow-xs"
                        title="Archive SOP"
                      >
                        <Archive className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(selectedArticle.article_id)}
                      className="p-1.5 bg-red-50 border border-red-200 hover:bg-red-100 text-[#DC2626] rounded-xl cursor-pointer transition-colors shadow-xs"
                      title="Delete Article"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                )}

                <div className="space-y-2 border-b border-[#E2E8F0] pb-4">
                  <div className="flex items-center gap-2 font-bold">
                    <span className="text-[10px] text-[#64748B] uppercase tracking-wider">{selectedArticle.article_id}</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-[#E2E8F0]" />
                    <span className="text-[10px] text-[#475569] uppercase tracking-wider">{selectedArticle.category}</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-[#E2E8F0]" />
                    <span className="text-[10px] text-[#94A3B8] italic">{selectedArticle.source}</span>
                  </div>
                  <h3 className="text-xs font-black text-[#0F172A] leading-snug pr-28 uppercase tracking-wider">
                    {selectedArticle.title}
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-semibold">
                  <div className="space-y-1.5">
                    <span className="font-bold text-[#0F172A] uppercase tracking-wider block">SOP Objective</span>
                    <p className="text-[#475569] leading-relaxed font-medium">{selectedArticle.problem}</p>
                  </div>
                  {selectedArticle.prerequisites && selectedArticle.prerequisites.length > 0 && (
                    <div className="space-y-1.5 border-l border-[#E2E8F0] pl-4">
                      <span className="font-bold text-[#0F172A] uppercase tracking-wider block">Prerequisites</span>
                      <ul className="list-disc list-inside text-[#475569] space-y-0.5 font-medium">
                        {selectedArticle.prerequisites.map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="space-y-3 pt-2">
                  <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Troubleshooting Guide Steps Sequence</span>
                  
                  <div className="space-y-3">
                    {(selectedArticle.troubleshooting_steps || []).map((step, idx) => (
                      <div key={idx} className="flex gap-4 items-start bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl p-4">
                        <div className="w-6 h-6 rounded-full bg-[#FEF2F2] border border-[#FEE2E2] text-[#E30613] flex items-center justify-center text-xs font-black flex-shrink-0">
                          {step.step}
                        </div>
                        <div className="flex-1 space-y-2 min-w-0 font-semibold">
                          <h4 className="text-xs font-bold text-[#0F172A] leading-none uppercase tracking-wider">{step.title}</h4>
                          <p className="text-[11px] text-[#475569] font-medium leading-relaxed">{step.instruction}</p>
                          
                          {step.image && (
                            <div className="border border-[#E2E8F0] rounded-xl p-0.5 bg-white max-w-sm mt-2 overflow-hidden shadow-xs">
                              <div className="aspect-video bg-[#F8FAFC] rounded-lg overflow-hidden relative">
                                <img
                                  src={`/images/${step.image}`}
                                  alt={step.caption}
                                  className="w-full h-full object-cover"
                                  onError={(e) => {
                                    (e.target as HTMLImageElement).src = "https://images.unsplash.com/photo-1531403009284-440f080d1e12?w=800&auto=format&fit=crop&q=60";
                                  }}
                                />
                              </div>
                              <p className="text-[9px] text-[#64748B] text-center italic mt-1 font-bold uppercase tracking-wider">{step.caption}</p>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {selectedArticle.verification && selectedArticle.verification.length > 0 && (
                  <div className="space-y-2 pt-2 text-xs border-t border-[#E2E8F0] font-bold">
                    <span className="font-bold text-[#0F172A] uppercase tracking-wider block">Verification Checks</span>
                    <ul className="list-disc list-inside text-[#475569] space-y-0.5 font-medium pl-1">
                      {selectedArticle.verification.map((v, i) => (
                        <li key={i}>{v}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="card p-10 bg-white border border-[#E2E8F0] text-center space-y-3">
                <FileText className="w-10 h-10 text-[#CBD5E1] mx-auto" />
                <div>
                  <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">No SOP Selected</h4>
                  <p className="text-[10px] text-[#64748B] mt-1 font-bold uppercase tracking-wider">Select a troubleshoot guide from the list to view its execution details.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* VERSION HISTORY MODAL */}
      {showVersionsModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-2xl max-w-4xl w-full flex flex-col h-[80vh] overflow-hidden">
            <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
              <div>
                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">SOP Version Logs &amp; Rollback</h3>
                <p className="text-[10px] text-[#64748B] font-bold mt-0.5 uppercase tracking-wider">Select a version copy to view content details or restore it as draft.</p>
              </div>
              <button 
                onClick={() => {
                  setShowVersionsModal(false);
                  setSelectedVersion(null);
                }} 
                className="p-1 hover:bg-[#F8FAFC] border border-transparent hover:border-[#E2E8F0] rounded-lg text-[#94A3B8] hover:text-[#475569] cursor-pointer transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 min-h-0 flex overflow-hidden">
              <div className="w-1/3 border-r border-[#E2E8F0] overflow-y-auto p-4 space-y-2 bg-[#F8FAFC]">
                <span className="text-[9px] font-black text-[#64748B] uppercase tracking-wider block mb-2">Versions History Log</span>
                {versions.map(v => (
                  <div
                    key={v.version}
                    onClick={() => loadVersionContent(selectedArticle?.article_id || "", v.version)}
                    className={`p-3 border rounded-xl cursor-pointer transition-all shadow-xs ${
                      selectedVersion?.version === v.version 
                        ? "border-[#E30613] bg-white text-[#0F172A]" 
                        : "border-[#E2E8F0] bg-white hover:border-[#94A3B8] text-[#475569]"
                    }`}
                  >
                    <div className="flex justify-between items-center font-bold text-xs uppercase tracking-wider">
                      <span>Version {v.version}</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </div>
                    <p className="text-[9px] text-[#64748B] font-bold mt-1 uppercase tracking-wider">
                      Published {new Date(v.timestamp * 1000).toLocaleString()}
                    </p>
                  </div>
                ))}
                {versions.length === 0 && (
                  <div className="text-center py-8 text-xs text-[#94A3B8] font-bold uppercase tracking-wider italic">
                    No historical logs saved yet. Published changes trigger automatic backup logs.
                  </div>
                )}
              </div>

              <div className="w-2/3 overflow-y-auto p-6 space-y-4">
                {selectedVersion ? (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center border-b border-[#E2E8F0] pb-3">
                      <div>
                        <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">{selectedVersion.title}</h4>
                        <span className="text-[9px] text-[#64748B] font-bold block mt-0.5 uppercase tracking-wider">Version {selectedVersion.version} content backup</span>
                      </div>
                      <button
                        onClick={() => handleRestoreVersion(selectedVersion)}
                        className="px-3.5 py-1.5 bg-[#E30613] hover:bg-red-750 text-white text-xs font-bold rounded-xl cursor-pointer transition-colors shadow-xs"
                      >
                        Restore Version
                      </button>
                    </div>

                    <div className="text-xs space-y-3 font-bold leading-relaxed">
                      <div>
                        <span className="text-[9px] font-bold text-[#64748B] uppercase block tracking-wider">Problem Objective</span>
                        <p className="text-[#334155] font-semibold">{selectedVersion.problem}</p>
                      </div>
                      <div>
                        <span className="text-[9px] font-bold text-[#64748B] uppercase block tracking-wider">Steps Configuration count</span>
                        <p className="text-[#334155] font-semibold">{(selectedVersion.troubleshooting_steps || []).length} steps registered.</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center text-[#94A3B8] space-y-2">
                    <FileText className="w-10 h-10 text-[#CBD5E1]" />
                    <span className="text-xs font-bold uppercase tracking-wider">No Version Selected</span>
                    <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider">Select a historical snapshot on the left to inspect its contents.</span>
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
