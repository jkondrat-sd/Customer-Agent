/**
 * Basic in-memory rate limiter for Edge/Serverless environments.
 * Note: In Vercel, this state is isolated per Lambda container and resets on cold start.
 * It provides basic protection against rapid-fire abuse from a single instance,
 * but for true global rate limiting, a persistent store like Vercel KV or Redis is required.
 */
interface RateLimitInfo {
  count: number;
  resetTime: number;
}

const rateLimitMap = new Map<string, RateLimitInfo>();

export function checkRateLimit(ip: string, limit: number, windowMs: number): { success: boolean; limit: number; remaining: number; reset: number } {
  const now = Date.now();
  const info = rateLimitMap.get(ip);

  // Clean up old entries occasionally to prevent unbounded memory growth
  if (Math.random() < 0.05) {
    rateLimitMap.forEach((val, key) => {
      if (val.resetTime < now) {
        rateLimitMap.delete(key);
      }
    });
  }

  if (!info || info.resetTime < now) {
    // New or expired window
    const resetTime = now + windowMs;
    rateLimitMap.set(ip, { count: 1, resetTime });
    return { success: true, limit, remaining: limit - 1, reset: resetTime };
  }

  // Existing window
  if (info.count >= limit) {
    return { success: false, limit, remaining: 0, reset: info.resetTime };
  }

  info.count += 1;
  return { success: true, limit, remaining: limit - info.count, reset: info.resetTime };
}
