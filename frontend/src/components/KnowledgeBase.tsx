"use client";

import { useState } from "react";
import { Search, FileText, Sparkles, BookOpen } from "lucide-react";

interface DocItem {
  id: string;
  title: string;
  summary: string;
  content: string;
}

const mockDocs: DocItem[] = [
  { id: "SOP-10", title: "Corporate VPN Connection Troubleshooting", summary: "Troubleshoot connection issues on APAC/US gateways.", content: "Verify credentials in Active Directory database. Flush client DNS using Uvicorn-connected AD tool parameters. Ensure VPN gateway version conforms to secure catalog specifications (v2.8)." },
  { id: "SOP-24", title: "SAP GUI 8.00 Permissions Revocation", summary: "Policy rules regarding automatic cleanup of ERP logins.", content: "Permissions matrices must be synchronized using dynamic role-checker scripts. Active compliance requires instant credentials revoke when a contract finishes." },
  { id: "SOP-09", title: "Disk Clean-up & Security Software Installer", summary: "Storage verification before installing corporate tools.", content: "Ensure local partitions have at least 15GB free storage. If storage limits are breached, trigger temporary file purge routine on the client terminal." }
];

export default function KnowledgeBase() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<DocItem | null>(null);

  const filteredDocs = mockDocs.filter(d => 
    d.title.toLowerCase().includes(searchTerm.toLowerCase()) || 
    d.summary.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6">
      <div className="pb-4 border-b border-gray-200 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-brand-red" />
            Knowledge Base
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Search standard operations procedures (SOPs).
          </p>
        </div>

        <div className="relative flex items-center bg-white border border-gray-200 rounded-lg px-3 py-1.5 w-64 shadow-sm">
          <Search className="w-3.5 h-3.5 text-gray-400 mr-2" />
          <input 
            type="text" 
            placeholder="Search SOP documentation..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setSelectedDoc(null);
            }}
            className="bg-transparent border-none outline-none text-xs text-gray-700 w-full"
          />
        </div>
      </div>

      {/* Prominent explanation banner */}
      <div className="p-4 bg-red-50/20 border border-brand-red/15 rounded-xl flex items-start gap-2.5 shadow-sm">
        <Sparkles className="w-4.5 h-4.5 text-brand-red mt-0.5 flex-shrink-0 animate-pulse" />
        <div>
          <span className="text-xs font-bold text-gray-800 block">Agentic RAG Integration Notice</span>
          <span className="text-[10.5px] text-gray-500 font-medium leading-normal block mt-0.5">
            The Autonomous AI Engineer queries this Knowledge Base dynamically during the reasoning pipeline to find SOP guidelines, security rules, and reference parameters before planning device executions.
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-4 lg:col-span-1">
          <span className="section-header block">Matching Rules SOPs</span>
          <div className="space-y-3">
            {filteredDocs.map(doc => (
              <div 
                key={doc.id}
                onClick={() => setSelectedDoc(doc)}
                className={`card p-4 cursor-pointer transition-all ${
                  selectedDoc?.id === doc.id ? "border-brand-red bg-red-50/10" : "bg-white border-gray-250"
                }`}
              >
                <div className="flex justify-between items-center text-[10px] font-bold text-gray-450 uppercase mb-1">
                  <span>{doc.id}</span>
                  <span className="badge badge-closed">SOP</span>
                </div>
                <h4 className="text-xs font-bold text-gray-850 leading-tight">{doc.title}</h4>
                <p className="text-[11px] text-gray-400 mt-2 line-clamp-2 leading-relaxed font-semibold">{doc.summary}</p>
              </div>
            ))}
            {filteredDocs.length === 0 && (
              <div className="p-4 bg-white border border-gray-200 rounded-xl text-center italic text-xs text-gray-400">
                No matching reference docs found.
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <span className="section-header block">AI Retrieved Document</span>
          {selectedDoc ? (
            <div className="card p-5 bg-white border border-gray-250 space-y-4 shadow-sm">
              <div className="flex justify-between items-center border-b border-gray-100 pb-2">
                <h3 className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
                  <FileText className="w-4.5 h-4.5 text-brand-red" />
                  {selectedDoc.title}
                </h3>
                <span className="text-[10px] font-mono text-gray-450 font-bold">{selectedDoc.id}</span>
              </div>
              <div className="space-y-3 text-xs leading-relaxed text-gray-700 font-semibold">
                <span className="text-[10px] text-gray-400 block font-bold uppercase tracking-wider">RETRIEVED EXCERPT</span>
                <p className="p-4 bg-gray-50 border border-gray-200 rounded-xl font-medium font-serif italic text-gray-800">
                  "{selectedDoc.content}"
                </p>
              </div>
            </div>
          ) : (
            <div className="card p-8 bg-white border border-gray-200 rounded-xl text-center italic text-xs text-gray-400 flex flex-col items-center justify-center space-y-3 shadow-sm">
              <BookOpen className="w-8 h-8 opacity-20 text-gray-400" />
              <span>Select an SOP on the left to display retrieved document contents.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
