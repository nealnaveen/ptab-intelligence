import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_GATEWAY_URL;

export async function POST(req: NextRequest) {
  if (!API_URL) {
    return NextResponse.json({ error: "API_GATEWAY_URL is not configured" }, { status: 500 });
  }

  try {
    const body = await req.json();

    const upstream = await fetch(`${API_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const text = await upstream.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text || "Empty response from API" };
    }

    return NextResponse.json(data, { status: upstream.status });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
