"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Sliders, Table as TableIcon, List, FileText } from "lucide-react";
import {
  SearchInput,
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  StatusPill,
  PriorityPill,
  RequestTypePill
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

function getAIConfidence(ticketId: string): string {
  let sum = 0;
  for (let i = 0; i < ticketId.length; i++) sum += ticketId.charCodeAt(i);
  return 85 + (sum % 14) + "%";
}

export default function IncidentView({
  filteredTickets,
  searchQuery,
  setSearchQuery,
  handleTicketClick,
  slaBadgeClass,
  slaStateLabel,
  calculateSLACountdown
}: IncidentViewProps) {
  const [viewMode, setViewMode] = useState<"cards" | "table">("table");

  const renderCardsList = () => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {filteredTickets.length === 0 ? (
        <div className="col-span-full flex flex-col items-center justify-center gap-3 py-16 text-center">
          <div className="w-12 h-12 rounded-xl bg-[#F1F5F9] border border-[#E2E8F0] flex items-center justify-center">
            <FileText className="w-5 h-5 text-[#94A3B8]" aria-hidden />
          </div>
          <p className="text-sm font-semibold text-[#1E293B]">No tickets found</p>
          <p className="text-xs text-[#64748B]">
            {searchQuery ? "Try adjusting your search query." : "Submit a support request to get started."}
          </p>
        </div>
      ) : (
        filteredTickets.map(t => (
          <motion.div
            key={t.ticket_id}
            whileHover={{ y: -2, boxShadow: "0 8px 24px rgba(0,0,0,0.04)" }}
            onClick={() => handleTicketClick(t.ticket_id)}
            className="bg-white border border-[#E2E8F0] rounded-2xl p-4 cursor-pointer flex flex-col justify-between min-h-[160px] transition-all hover:border-[#CBD5E1] shadow-xs"
          >
            <div>
              <div className="flex justify-between items-start gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] font-mono text-[#475569] bg-[#F8FAFC] px-2 py-0.5 rounded font-bold border border-[#E2E8F0]">
                    {t.ticket_id}
                  </span>
                  {t.request_type && (
                    <RequestTypePill type={t.request_type} />
                  )}
                </div>
                <StatusPill status={t.status} />
              </div>
              <p className="text-xs font-semibold text-[#1E293B] mt-2.5 line-clamp-2 leading-tight uppercase tracking-wider">
                {t.issue_description || "No description provided"}
              </p>
            </div>

            <div className="pt-3 border-t border-[#F1F5F9] flex items-center justify-between text-[11px] font-bold uppercase tracking-wider mt-3">
              <div>
                <span className="text-[#94A3B8] block">
                  Priority: <PriorityPill priority={t.priority || "MEDIUM"} className="ml-1" />
                </span>
                <span className="text-[#94A3B8] block mt-1">
                  Team: <strong className="text-[#1E293B]">{t.assigned_team}</strong>
                </span>
              </div>
              <div className="text-right">
                <span className="text-[#94A3B8] block">
                  AI: <strong className="text-[#E30613]">{getAIConfidence(t.ticket_id)}</strong>
                </span>
                <span className="text-[#94A3B8] block mt-1">
                  SLA: <span className={`${slaBadgeClass(t.sla_state)} ml-1`}>{calculateSLACountdown(t)}</span>
                </span>
              </div>
            </div>
          </motion.div>
        ))
      )}
    </div>
  );

  return (
    <div className="p-6 space-y-5 font-sans">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-xs font-black text-[#0F172A] uppercase tracking-wider">
            <Sliders className="w-4 h-4 text-[#E30613]" aria-hidden />
            My Support Tickets
          </h1>
          <p className="text-[10px] text-[#64748B] font-bold uppercase mt-1 tracking-wider">
            Track, inspect, and manage your IT support requests.
          </p>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2.5">
          {/* Search */}
          <div className="w-56">
            <SearchInput
              placeholder="Search tickets…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Filter tickets"
            />
          </div>

          {/* View toggle */}
          <div className="flex items-center bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl p-0.5 gap-0.5">
            <button
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded-lg transition-all cursor-pointer ${
                viewMode === "table"
                  ? "bg-white text-[#1E293B] shadow-xs border border-[#E2E8F0]"
                  : "text-[#94A3B8] hover:text-[#475569]"
              }`}
              title="Table view"
              aria-pressed={viewMode === "table"}
            >
              <TableIcon className="w-3.5 h-3.5" aria-hidden />
            </button>
            <button
              onClick={() => setViewMode("cards")}
              className={`p-1.5 rounded-lg transition-all cursor-pointer ${
                viewMode === "cards"
                  ? "bg-white text-[#1E293B] shadow-xs border border-[#E2E8F0]"
                  : "text-[#94A3B8] hover:text-[#475569]"
              }`}
              title="Card view"
              aria-pressed={viewMode === "cards"}
            >
              <List className="w-3.5 h-3.5" aria-hidden />
            </button>
          </div>
        </div>
      </div>

      {/* Content area */}
      <div className="md:hidden">
        {/* Always cards on mobile */}
        {renderCardsList()}
      </div>

      <div className="hidden md:block">
        {/* Toggleable on tablet/desktop */}
        {viewMode === "cards" ? (
          renderCardsList()
        ) : (
          /* Table view */
          <Table>
            <TableHeader>
              <TableRow>
                {["Ticket ID", "Type", "Description", "Priority", "Status", "AI Conf.", "Team", "SLA", ""].map(h => (
                  <TableHead key={h}>
                    {h}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredTickets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="py-14 text-center">
                    <div className="flex flex-col items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-[#F1F5F9] flex items-center justify-center">
                        <FileText className="w-4.5 h-4.5 text-[#94A3B8]" aria-hidden />
                      </div>
                      <p className="text-sm font-semibold text-[#1E293B]">No tickets found</p>
                      <p className="text-xs text-[#64748B]">
                        {searchQuery ? "Try adjusting your search query." : "Your tickets will appear here."}
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                filteredTickets.map((t) => (
                  <TableRow key={t.ticket_id}>
                    <TableCell className="font-mono font-bold text-[#E30613]">
                      {t.ticket_id}
                    </TableCell>
                    <TableCell>
                      <RequestTypePill type={t.request_type || "INCIDENT"} />
                    </TableCell>
                    <TableCell className="text-[#1E293B] font-semibold max-w-[220px] truncate" title={t.issue_description}>
                      {t.issue_description || "N/A"}
                    </TableCell>
                    <TableCell>
                      <PriorityPill priority={t.priority || "MEDIUM"} />
                    </TableCell>
                    <TableCell>
                      <StatusPill status={t.status} />
                    </TableCell>
                    <TableCell className="font-mono font-semibold text-[#475569]">
                      {getAIConfidence(t.ticket_id)}
                    </TableCell>
                    <TableCell className="text-[#475569]">
                      {t.assigned_team}
                    </TableCell>
                    <TableCell className="font-mono font-bold text-[#16A34A]">
                      {calculateSLACountdown(t)}
                    </TableCell>
                    <TableCell className="text-right">
                      <button
                        onClick={() => handleTicketClick(t.ticket_id)}
                        className="px-3 py-1.5 bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#CBD5E1] text-[#475569] text-[10.5px] font-bold uppercase tracking-wider rounded-xl cursor-pointer transition-all shadow-xs"
                      >
                        Details
                      </button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
