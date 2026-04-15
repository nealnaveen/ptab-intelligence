import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_GATEWAY_URL;

export async function GET(
  req: NextRequest,
  { params }: { params: { type: string } }
) {
  if (!API_URL) {
    return NextResponse.json({ error: "API_GATEWAY_URL is not configured" }, { status: 500 });
  }

  try {
    const { searchParams } = new URL(req.url);
    const upstream = await fetch(
      `${API_URL}/browse/${params.type}?${searchParams.toString()}`,
      { headers: { Accept: "application/json" } }
    );

    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
