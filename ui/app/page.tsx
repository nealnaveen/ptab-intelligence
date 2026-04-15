"use client";

import { useState } from "react";
import ChatTab from "@/components/ChatTab";
import BrowseTab from "@/components/BrowseTab";

const TABS = [
  { id: "chat",         label: "💬 Ask AI",        desc: "RAG-powered Q&A" },
  { id: "applications", label: "📄 Applications",   desc: "Patent file wrappers" },
  { id: "proceedings",  label: "⚖️ Proceedings",    desc: "PTAB IPR / PGR trials" },
  { id: "rejections",   label: "🚫 Rejections",     desc: "Office action rejections" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabId>("chat");

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ── */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm">
              PT
            </div>
            <div>
              <h1 className="text-base font-semibold text-white leading-tight">PTAB Intelligence</h1>
              <p className="text-xs text-gray-500">USPTO Patent Data · RAG Pipeline</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              Live
            </span>
          </div>
        </div>
      </header>

      {/* ── Tabs ── */}
      <div className="border-b border-gray-800 bg-gray-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <nav className="flex gap-1 -mb-px overflow-x-auto">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`tab-btn whitespace-nowrap ${
                  activeTab === tab.id ? "tab-btn-active" : "tab-btn-inactive"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* ── Content ── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6">
        {activeTab === "chat" && <ChatTab />}
        {activeTab === "applications" && (
          <BrowseTab
            docType="applications"
            title="Patent Applications"
            description="USPTO patent file wrapper data — applications, status, inventors, art units"
            columns={[
              { key: "application_number", label: "App #", width: "w-32" },
              { key: "invention_title",    label: "Title",  width: "flex-1" },
              { key: "filing_date",        label: "Filed",  width: "w-28" },
              { key: "status",             label: "Status", width: "w-36" },
              { key: "art_unit",           label: "Art Unit", width: "w-20" },
              { key: "applicant",          label: "Applicant", width: "w-40" },
            ]}
          />
        )}
        {activeTab === "proceedings" && (
          <BrowseTab
            docType="proceedings"
            title="PTAB Proceedings"
            description="IPR, PGR, and CBM trial proceedings before the Patent Trial and Appeal Board"
            columns={[
              { key: "proceeding_number", label: "Trial #",     width: "w-36" },
              { key: "proceeding_type",   label: "Type",        width: "w-20" },
              { key: "filing_date",       label: "Filed",       width: "w-28" },
              { key: "status",            label: "Status",      width: "w-32" },
              { key: "patent_owner",      label: "Patent Owner", width: "w-40" },
              { key: "petitioner",        label: "Petitioner",  width: "w-40" },
            ]}
          />
        )}
        {activeTab === "rejections" && (
          <BrowseTab
            docType="rejections"
            title="Office Action Rejections"
            description="USPTO office action rejection data — 101/102/103/112 grounds, art units, prior art"
            columns={[
              { key: "proceeding_number", label: "App #",       width: "w-32" },
              { key: "art_unit",          label: "Art Unit",    width: "w-20" },
              { key: "submission_date",   label: "Date",        width: "w-28" },
              { key: "action_type",       label: "Action",      width: "w-32" },
              { key: "has_rej_101",       label: "§101",        width: "w-16" },
              { key: "has_rej_102",       label: "§102",        width: "w-16" },
              { key: "has_rej_103",       label: "§103",        width: "w-16" },
              { key: "has_rej_112",       label: "§112",        width: "w-16" },
            ]}
          />
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-800 py-4 text-center text-xs text-gray-600">
        PTAB Intelligence · Data from USPTO Open Data Portal · Built with AWS Bedrock + Pinecone + Claude
      </footer>
    </div>
  );
}
