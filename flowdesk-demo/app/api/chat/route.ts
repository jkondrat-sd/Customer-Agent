import { checkRateLimit } from "@/lib/rateLimit";

export async function POST(req: Request) {
  // 1. Basic IP-based Rate Limiting (10 requests per minute)
  const ip = req.headers.get("x-forwarded-for") ?? "anonymous";
  const rateLimit = checkRateLimit(ip, 10, 60 * 1000);
  
  if (!rateLimit.success) {
    return new Response(JSON.stringify({ error: "Too many requests" }), {
      status: 429,
      headers: {
        "X-RateLimit-Limit": rateLimit.limit.toString(),
        "X-RateLimit-Remaining": rateLimit.remaining.toString(),
        "X-RateLimit-Reset": rateLimit.reset.toString(),
        "Content-Type": "application/json"
      }
    });
  }

  // 2. Dynamic Backend URL configuration
  const body = await req.json();
  const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  
  const backendRes = await fetch(`${backendUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  
  return new Response(backendRes.body, {
    headers: { 
      "Content-Type": "text/event-stream",
      "X-RateLimit-Limit": rateLimit.limit.toString(),
      "X-RateLimit-Remaining": rateLimit.remaining.toString(),
      "X-RateLimit-Reset": rateLimit.reset.toString()
    },
  });
}
