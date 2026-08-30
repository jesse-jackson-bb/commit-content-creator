import { query } from "./_generated/server";
import { v } from "convex/values";

/**
 * DBA Relational Integrity Auditor.
 * Inspects collections to detect any orphaned records or referential inconsistencies.
 */
export const auditRelationalIntegrity = query({
  args: {
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const scanLimit = args.limit ?? 100;
    const anomalies: Array<{
      table: string;
      id: string;
      reason: string;
    }> = [];

    // 1. Audit Stories referential integrity (must point to valid user and repository)
    const sampleStories = await ctx.db.query("stories").take(scanLimit);
    for (const story of sampleStories) {
      const user = await ctx.db.get(story.userId);
      if (!user) {
        anomalies.push({
          table: "stories",
          id: story._id,
          reason: `Orphaned: references non-existent userId ${story.userId}`,
        });
      }
      const repo = await ctx.db.get(story.repositoryId);
      if (!repo) {
        anomalies.push({
          table: "stories",
          id: story._id,
          reason: `Orphaned: references non-existent repositoryId ${story.repositoryId}`,
        });
      }
    }

    // 2. Audit Posts referential integrity (must point to valid user and story)
    const samplePosts = await ctx.db.query("posts").take(scanLimit);
    for (const post of samplePosts) {
      const user = await ctx.db.get(post.userId);
      if (!user) {
        anomalies.push({
          table: "posts",
          id: post._id,
          reason: `Orphaned: references non-existent userId ${post.userId}`,
        });
      }
      const story = await ctx.db.get(post.storyId);
      if (!story) {
        anomalies.push({
          table: "posts",
          id: post._id,
          reason: `Orphaned: references non-existent storyId ${post.storyId}`,
        });
      }
    }

    // 3. Audit Approval Requests referential integrity
    const sampleApprovalRequests = await ctx.db.query("approvalRequests").take(scanLimit);
    for (const req of sampleApprovalRequests) {
      const post = await ctx.db.get(req.postId);
      if (!post) {
        anomalies.push({
          table: "approvalRequests",
          id: req._id,
          reason: `Orphaned: references non-existent postId ${req.postId}`,
        });
      }
      const version = await ctx.db.get(req.currentPostVersionId);
      if (!version) {
        anomalies.push({
          table: "approvalRequests",
          id: req._id,
          reason: `Orphaned: references non-existent currentPostVersionId ${req.currentPostVersionId}`,
        });
      }
    }

    return {
      scannedCount: sampleStories.length + samplePosts.length + sampleApprovalRequests.length,
      anomaliesCount: anomalies.length,
      anomalies,
      healthy: anomalies.length === 0,
      timestamp: Date.now(),
    };
  },
});

/**
 * DBA Table Metrics Collector.
 * Provides document counts and health indicators across primary tables.
 */
export const getTableMetrics = query({
  args: {},
  handler: async (ctx) => {
    const [
      users,
      repositories,
      commits,
      commitAnalyses,
      stories,
      posts,
      approvalRequests,
      whatsappSessions,
      activityEvents,
    ] = await Promise.all([
      ctx.db.query("users").take(500),
      ctx.db.query("repositories").take(500),
      ctx.db.query("commits").take(500),
      ctx.db.query("commitAnalyses").take(500),
      ctx.db.query("stories").take(500),
      ctx.db.query("posts").take(500),
      ctx.db.query("approvalRequests").take(500),
      ctx.db.query("whatsappSessions").take(500),
      ctx.db.query("activityEvents").take(500),
    ]);

    return {
      tables: {
        users: users.length,
        repositories: repositories.length,
        commits: commits.length,
        commitAnalyses: commitAnalyses.length,
        stories: stories.length,
        posts: posts.length,
        approvalRequests: approvalRequests.length,
        whatsappSessions: whatsappSessions.length,
        activityEvents: activityEvents.length,
      },
      timestamp: Date.now(),
    };
  },
});
