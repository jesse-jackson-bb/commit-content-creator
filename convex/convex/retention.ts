import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

const DEFAULT_BATCH_SIZE = 100;
const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

/**
 * Purges expired WhatsApp session records where expiresAt < now.
 * Uses index `by_expires_at` for optimal scan performance without full table scan.
 */
export const purgeExpiredSessions = mutation({
  args: {
    batchSize: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.batchSize ?? DEFAULT_BATCH_SIZE;
    const now = Date.now();

    const expiredSessions = await ctx.db
      .query("whatsappSessions")
      .withIndex("by_expires_at", (q) => q.lt("expiresAt", now))
      .take(limit);

    let deletedCount = 0;
    for (const session of expiredSessions) {
      await ctx.db.delete(session._id);
      deletedCount++;
    }

    return {
      deletedCount,
      hasMore: expiredSessions.length === limit,
      timestamp: now,
    };
  },
});

/**
 * Prunes activity events older than retention cutoff (default 30 days).
 * Employs index `by_timestamp` to avoid full table scans.
 */
export const pruneActivityLogs = mutation({
  args: {
    retentionDays: v.optional(v.number()),
    batchSize: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.batchSize ?? DEFAULT_BATCH_SIZE;
    const retentionMs = (args.retentionDays ?? 30) * 24 * 60 * 60 * 1000;
    const cutoffTimestamp = Date.now() - retentionMs;

    const staleLogs = await ctx.db
      .query("activityEvents")
      .withIndex("by_timestamp", (q) => q.lt("timestamp", cutoffTimestamp))
      .take(limit);

    let deletedCount = 0;
    for (const log of staleLogs) {
      await ctx.db.delete(log._id);
      deletedCount++;
    }

    return {
      deletedCount,
      cutoffTimestamp,
      hasMore: staleLogs.length === limit,
    };
  },
});

/**
 * Aggregates operational retention statistics across ephemeral and audit collections.
 */
export const getRetentionOverview = query({
  args: {},
  handler: async (ctx) => {
    const now = Date.now();
    const thirtyDaysAgo = now - THIRTY_DAYS_MS;

    const expiredSessionsCount = (
      await ctx.db
        .query("whatsappSessions")
        .withIndex("by_expires_at", (q) => q.lt("expiresAt", now))
        .take(DEFAULT_BATCH_SIZE)
    ).length;

    const staleActivityLogsCount = (
      await ctx.db
        .query("activityEvents")
        .withIndex("by_timestamp", (q) => q.lt("timestamp", thirtyDaysAgo))
        .take(DEFAULT_BATCH_SIZE)
    ).length;

    return {
      expiredSessionsPendingPurge: expiredSessionsCount,
      staleActivityLogsPendingPurge: staleActivityLogsCount,
      evaluatedAt: now,
    };
  },
});
