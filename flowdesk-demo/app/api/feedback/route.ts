import { NextResponse } from "next/server";
import { checkRateLimit } from "@/lib/rateLimit";

export async function POST(req: Request) {
  try {
    // 1. Basic IP-based Rate Limiting (30 requests per minute)
    const ip = req.headers.get("x-forwarded-for") ?? "anonymous";
    const rateLimit = checkRateLimit(ip, 30, 60 * 1000);
    
    if (!rateLimit.success) {
      return NextResponse.json(
        { error: "Too many requests" },
        { 
          status: 429,
          headers: {
            "X-RateLimit-Limit": rateLimit.limit.toString(),
            "X-RateLimit-Remaining": rateLimit.remaining.toString(),
            "X-RateLimit-Reset": rateLimit.reset.toString()
          }
        }
      );
    }

    const body = await req.json();
    const { message_id, session_id, rating, confidence, intent } = body;

    // For the demo, we simply log the feedback payload as requested.
    console.log("----------------------------------------");
    console.log("Feedback Received:");
    console.log(`Message ID: ${message_id}`);
    console.log(`Session ID: ${session_id}`);
    console.log(`Rating:     ${rating === "up" ? "👍 Helpful" : "👎 Not Helpful"}`);
    console.log(`Confidence: ${confidence}`);
    console.log(`Intent:     ${intent}`);
    console.log("----------------------------------------");

    // Optional: Forward to backend
    const backendUrl = process.env.BACKEND_URL;
    if (backendUrl) {
       // fetch(`${backendUrl}/feedback`, { ... })
    }

    return NextResponse.json({ status: "success", logged: true });
  } catch (error) {
    console.error("Error processing feedback:", error);
    return NextResponse.json(
      { status: "error", detail: "Invalid payload" },
      { status: 400 }
    );
  }
}
