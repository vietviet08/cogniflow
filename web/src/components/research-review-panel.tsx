"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, RefreshCcw, XCircle } from "lucide-react";

import {
  decideResearchReview,
  listResearchReviews,
  requestResearchReview,
} from "@/lib/api/client";
import type { ResearchReviewData } from "@/lib/api/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

function getReviewVariant(status: ResearchReviewData["status"]) {
  if (status === "approved") return "success";
  if (status === "rejected") return "destructive";
  return "warning";
}

export function ResearchReviewPanel({
  projectId,
  targetType,
  targetId,
  canRequest,
  canReview,
}: {
  projectId: string;
  targetType: "insight" | "report";
  targetId: string;
  canRequest: boolean;
  canReview: boolean;
}) {
  const [reviews, setReviews] = useState<ResearchReviewData[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");

  const currentReview =
    reviews.find((review) => review.target_id === targetId) ?? null;

  const loadReviews = useCallback(async () => {
    if (!projectId || !targetId) return;
    setLoading(true);
    try {
      const response = await listResearchReviews({
        projectId,
        targetType,
      });
      const items = response.data.items.filter(
        (review) => review.target_id === targetId,
      );
      setReviews(items);
      setReviewNotes(items[0]?.review_notes ?? "");
    } catch (error) {
      console.error("Failed to load research reviews", error);
    } finally {
      setLoading(false);
    }
  }, [projectId, targetId, targetType]);

  useEffect(() => {
    void loadReviews();
  }, [loadReviews]);

  async function handleRequestReview() {
    if (!canRequest) {
      toast.error("Requesting review requires editor role or higher.");
      return;
    }
    setBusy(true);
    try {
      await requestResearchReview({
        projectId,
        targetType,
        targetId,
      });
      toast.success("Review requested.");
      await loadReviews();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to request review.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(status: "approved" | "rejected") {
    if (!currentReview) return;
    if (!canReview) {
      toast.error("Approving research outputs requires owner role.");
      return;
    }
    setBusy(true);
    try {
      await decideResearchReview({
        projectId,
        reviewId: currentReview.approval_id,
        status,
        reviewNotes,
      });
      toast.success(`Review ${status}.`);
      await loadReviews();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to submit review.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">Review Workflow</CardTitle>
            {currentReview ? (
              <Badge variant={getReviewVariant(currentReview.status)}>
                {currentReview.status}
              </Badge>
            ) : null}
          </div>
          <CardDescription>
            Human approval and citation feedback before sharing this {targetType}.
          </CardDescription>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => void loadReviews()}
          disabled={loading}
        >
          {loading ? <Spinner size="sm" /> : <RefreshCcw className="h-3.5 w-3.5" />}
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!currentReview ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => void handleRequestReview()}
            disabled={busy || !canRequest}
            className="w-fit"
          >
            {busy ? <Spinner size="sm" /> : null}
            Request review
          </Button>
        ) : (
          <>
            <Textarea
              value={reviewNotes}
              onChange={(event) => setReviewNotes(event.target.value)}
              rows={3}
              placeholder="Add citation, wording, or decision-readiness feedback."
              disabled={busy || currentReview.status !== "pending" || !canReview}
            />
            {currentReview.status === "pending" ? (
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleDecision("approved")}
                  disabled={busy || !canReview}
                  className="gap-2"
                >
                  {busy ? <Spinner size="sm" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  Approve
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleDecision("rejected")}
                  disabled={busy || !canReview}
                  className="gap-2"
                >
                  {busy ? <Spinner size="sm" /> : <XCircle className="h-3.5 w-3.5" />}
                  Reject
                </Button>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Reviewed {currentReview.reviewed_at ? new Date(currentReview.reviewed_at).toLocaleString() : ""}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
