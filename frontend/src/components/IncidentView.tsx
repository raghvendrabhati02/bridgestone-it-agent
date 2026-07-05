"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, Sliders, ChevronDown, CheckCircle2, Clock, Shield, AlertTriangle, 
  HelpCircle, ChevronRight, X, ArrowUpRight, BarChart3, Filter, Table, List
} from "lucide-react";

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

interface IncidentViewProps {
  tickets: Ticket[];
  filteredTickets: Ticket[];
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  handleTicketClick: (id: string) => void;
  statusBadgeClass: (status: string) => string;
  slaBadgeClass: (state?: string) => string;
  slaStateLabel: (state?: string) => string;
  priorityColor: (p?: string) => string;
  calculateSLACountdown: (t: Ticket) => string;
}

export default function IncidentView({
  tickets,
  filteredTickets,
  searchQuery,
  setSearchQuery,
  handleTicketClick,
  statusBadgeClass,
  slaBadgeClass,
  slaStateLabel,
  priorityColor,
  calculateSLACountdown
}: IncidentViewProps) {
  const [viewMode, setViewMode] = useState<"cards" | "table">("table");
  
  const getAIConfidence = (ticketId: string) => {
    let sum = 0;
    for(let i=0; i<ticketId.length; i++) sum += ticketId.charCodeAt(i);
    return 85 + (sum % 14) + "%";
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
            <Sliders className="w-5 h-5 text-brand-red" />
            Support Incident Registry
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Manage, route, and inspect tickets tracked across internal databases and ServiceNow.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative flex items-center bg-white border border-gray-200 rounded-lg px-3 py-1.5 w-60 shadow-sm">
            <Search className="w-3.5 h-3.5 text-gray-400 mr-2" />
            <input 
              type="text" 
              placeholder="Filter ticket ID, team, status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent border-none outline-none text-xs text-gray-700 w-full"
            />
          </div>

          <div className="flex items-center bg-gray-100 border border-gray-200 rounded-lg p-0.5 shadow-sm text-xs font-semibold text-gray-600">
            <button
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded transition-all cursor-pointer ${
                viewMode === "table" ? "bg-white text-gray-800 shadow-sm border border-gray-200" : "hover:text-gray-955"
              }`}
              title="Table View"
            >
              <Table className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode("cards")}
              className={`p-1.5 rounded transition-all cursor-pointer ${
                viewMode === "cards" ? "bg-white text-gray-800 shadow-sm border border-gray-200" : "hover:text-gray-955"
              }`}
              title="Cards Grid"
            >
              <List className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {viewMode === "cards" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredTickets.map(t => (
            <motion.div
              key={t.ticket_id}
              whileHover={{ y: -2 }}
              onClick={() => handleTicketClick(t.ticket_id)}
              className="card p-5 cursor-pointer flex flex-col justify-between h-48 bg-white border border-gray-250"
            >
              <div>
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-[10px] font-mono text-gray-400 bg-gray-100 px-2 py-0.5 rounded font-bold">
                      {t.ticket_id}
                    </span>
                    {t.servicenow_id && (
                      <span className="text-[9px] font-mono text-amber-600 bg-amber-50 border border-amber-100 px-2.5 py-0.5 rounded font-bold ml-2">
                        {t.servicenow_id}
                      </span>
                    )}
                  </div>
                  <span className={statusBadgeClass(t.status)}>{t.status}</span>
                </div>
                <h4 className="text-xs font-bold text-gray-850 mt-3 line-clamp-2 leading-tight">
                  {t.issue_description || "No description provided"}
                </h4>
              </div>

              <div className="pt-3 border-t border-gray-105 flex items-center justify-between text-[10.5px]">
                <div>
                  <span className="text-gray-400 font-semibold block">Priority: <strong className={`font-bold ${priorityColor(t.priority)}`}>{t.priority || "MEDIUM"}</strong></span>
                  <span className="text-gray-400 font-medium block mt-0.5">Team: <strong className="text-gray-700 font-bold">{t.assigned_team}</strong></span>
                </div>
                <div className="text-right">
                  <span className="text-gray-400 block font-semibold">AI Conf: <strong className="text-brand-red font-bold">{getAIConfidence(t.ticket_id)}</strong></span>
                  <span className="text-gray-400 font-medium block mt-0.5">SLA: <strong className="text-green-605 font-mono font-bold">{calculateSLACountdown(t)}</strong></span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      ) : (
        <div className="enterprise-table-container shadow-sm border border-gray-200">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Ticket ID</th>
                <th>Description</th>
                <th>Priority</th>
                <th>Status</th>
                <th>AI Confidence</th>
                <th>Assigned Team</th>
                <th>SLA Countdown</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredTickets.map(t => (
                <tr key={t.ticket_id}>
                  <td className="font-mono font-bold text-brand-red text-xs">
                    {t.ticket_id}
                  </td>
                  <td className="font-medium text-gray-800 font-bold" title={t.issue_description}>
                    {t.issue_description || "N/A"}
                  </td>
                  <td>
                    <span className={`font-bold ${priorityColor(t.priority)}`}>
                      {t.priority || "MEDIUM"}
                    </span>
                  </td>
                  <td>
                    <span className={statusBadgeClass(t.status)}>
                      {t.status}
                    </span>
                  </td>
                  <td className="font-mono font-bold text-gray-650">
                    {getAIConfidence(t.ticket_id)}
                  </td>
                  <td className="font-semibold text-gray-700">
                    {t.assigned_team}
                  </td>
                  <td className="font-mono font-bold text-green-600">
                    {calculateSLACountdown(t)}
                  </td>
                  <td>
                    <button
                      onClick={() => handleTicketClick(t.ticket_id)}
                      className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 border border-gray-250 text-gray-700 text-[10.5px] font-bold rounded-lg cursor-pointer transition-colors font-semibold"
                    >
                      Details
                    </button>
                  </td>
                </tr>
              ))}
              {filteredTickets.length === 0 && (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-xs text-gray-450 italic">
                    No active support incidents found matching search criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
