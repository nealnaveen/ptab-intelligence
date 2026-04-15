"use client";

import { useState, useEffect, useCallback } from "react";

interface Column {
  key: string;
  label: string;
  width: string;
}

interface BrowseTabProps {
  docType: string;
  title: string;
  description: string;
  columns: Column[];
}

interface BrowseResult {
  records: Record<string, unknown>[];
  next_token?: string;
  has_more: boolean;
  count: number;
}

const STATUS_COLORS: Record<string, string> = {
  // Applications
  patented: "bg-green-900/40 text-green-400 border-green-800",
  abandoned: "bg-red-900/40 text-red-400 border-red-800",
  pending: "bg-yellow-900/40 text-yellow-400 border-yellow-800",
  published: "bg-blue-900/40 text-blue-400 border-blue-800",
  // Proceedings
  terminated: "bg-red-900/40 text-red-400 border-red-800",
  instituted: "bg-green-900/40 text-green-400 border-green-800",
  "final written decision": "bg-purple-900/40 text-purple-400 border-purple-800",
  // Default
  default: "bg-gray-800 text-gray-400 border-gray-700",
};

function statusColor(value: string): string {
  const key = value.toLowerCase();
  for (const [k, v] of Object.entries(STATUS_COLORS)) {
    if (key.includes(k)) return v;
  }
  return STATUS_COLORS.default;
}

function CellValue({ col, value }: { col: Column; value: unknown }) {
  if (value === null || value === undefined || value === "N/A" || value === "") {
    return <span className="text-gray-600">—</span>;
  }

  // Boolean fields (§101, §102, etc.)
  if (typeof value === "boolean") {
    return value ? (
      <span className="badge bg-red-900/40 text-red-400 border border-red-800">Yes</span>
    ) : (
      <span className="badge bg-gray-800 text-gray-600 border border-gray-700">No</span>
    );
  }

  // Status field
  if (col.key === "status" && typeof value === "string") {
    return (
      <span className={`badge border ${statusColor(value)}`}>
        {value.length > 24 ? value.slice(0, 22) + "…" : value}
      </span>
    );
  }

  // Type field (IPR, PGR, etc.)
  if (col.key === "proceeding_type" && typeof value === "string") {
    return (
      <span className="badge bg-indigo-900/40 text-indigo-400 border border-indigo-800">
        {value}
      </span>
    );
  }

  const str = String(value);
  return (
    <span title={str.length > 60 ? str : undefined}>
      {str.length > 60 ? str.slice(0, 58) + "…" : str}
    </span>
  );
}

export default function BrowseTab({ docType, title, description, columns }: BrowseTabProps) {
  const [data, setData] = useState<BrowseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tokenStack, setTokenStack] = useState<string[]>([]); // history for back navigation

  const fetch_page = useCallback(async (token?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "25" });
      if (token) params.set("token", token);

      const res = await fetch(`/api/browse/${docType}?${params}`);
      const json = await res.json();

      if (!res.ok) throw new Error(json.error || "Request failed");
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [docType]);

  useEffect(() => {
    setData(null);
    setTokenStack([]);
    fetch_page();
  }, [fetch_page]);

  function nextPage() {
    if (!data?.next_token) return;
    setTokenStack((prev) => [...prev, data.next_token ?? ""]);
    fetch_page(data.next_token);
  }

  function prevPage() {
    const stack = [...tokenStack];
    stack.pop(); // remove current page token
    const prev = stack[stack.length - 1]; // go to previous
    setTokenStack(stack);
    fetch_page(prev);
  }

  const page = tokenStack.length + 1;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <p className="text-sm text-gray-400 mt-0.5">{description}</p>
        </div>
        {data && (
          <span className="text-xs text-gray-500 mt-1">
            Page {page} · {data.count} records shown
          </span>
        )}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-gray-800 bg-gray-900/50">
              <tr>
                {columns.map((col) => (
                  <th key={col.key} className={`table-th ${col.width}`}>
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {columns.map((col) => (
                      <td key={col.key} className="table-td">
                        <div className="h-3.5 bg-gray-800 rounded w-3/4" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : error ? (
                <tr>
                  <td colSpan={columns.length} className="table-td text-center py-12">
                    <div className="text-red-400 text-sm">⚠️ {error}</div>
                    <button onClick={() => fetch_page()} className="mt-3 text-xs text-indigo-400 hover:underline">
                      Retry
                    </button>
                  </td>
                </tr>
              ) : !data || data.records.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="table-td text-center py-12">
                    <div className="text-gray-500 text-sm">No records found</div>
                  </td>
                </tr>
              ) : (
                data.records.map((record, i) => (
                  <tr key={i} className="hover:bg-gray-800/40 transition-colors duration-75">
                    {columns.map((col) => (
                      <td key={col.key} className={`table-td ${col.width}`}>
                        <CellValue col={col} value={record[col.key]} />
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {!loading && !error && data && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <button
              onClick={prevPage}
              disabled={page <= 1}
              className="text-sm text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed
                         px-3 py-1.5 rounded border border-gray-700 hover:border-gray-500 transition-colors"
            >
              ← Previous
            </button>
            <span className="text-xs text-gray-500">Page {page}</span>
            <button
              onClick={nextPage}
              disabled={!data.has_more}
              className="text-sm text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed
                         px-3 py-1.5 rounded border border-gray-700 hover:border-gray-500 transition-colors"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
