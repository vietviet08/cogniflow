"""RAG Evaluation Script — NoteMesh.

Runs retrieval + generation evaluation on a test dataset and outputs
metrics to CLI (table) and exports to Markdown file.

Usage:
    cd api && python -m scripts.rag_evaluation
    cd api && python -m scripts.rag_evaluation --project-id <uuid>
    cd api && python -m scripts.rag_evaluation --output report.md

Requires:
    - DATABASE_URL set in .env
    - Project with indexed sources
    - Provider settings configured (OpenAI or Gemini)
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Test Dataset
# ---------------------------------------------------------------------------

@dataclass
class EvalQuestion:
    question: str
    expected_keywords: list[str]
    category: str = "general"


DEFAULT_TEST_DATASET: list[EvalQuestion] = [
    EvalQuestion(
        question="Gradient descent là gì?",
        expected_keywords=["gradient", "descent", "optimize", "loss", "learning rate"],
        category="ML basics",
    ),
    EvalQuestion(
        question="What is the difference between supervised and unsupervised learning?",
        expected_keywords=["supervised", "unsupervised", "labeled", "label"],
        category="ML basics",
    ),
    EvalQuestion(
        question="Overfitting là gì và cách khắc phục?",
        expected_keywords=["overfitting", "regularization", "dropout", "validation"],
        category="ML basics",
    ),
    EvalQuestion(
        question="Explain the bias-variance tradeoff",
        expected_keywords=["bias", "variance", "tradeoff", "underfitting", "overfitting"],
        category="ML theory",
    ),
    EvalQuestion(
        question="Cross-validation hoạt động như thế nào?",
        expected_keywords=["cross-validation", "fold", "k-fold", "train", "test"],
        category="ML basics",
    ),
    EvalQuestion(
        question="What is a neural network?",
        expected_keywords=["neural", "network", "layer", "neuron", "activation"],
        category="Deep Learning",
    ),
    EvalQuestion(
        question="CNN và RNN khác nhau như thế nào?",
        expected_keywords=["CNN", "RNN", "convolutional", "recurrent", "sequence"],
        category="Deep Learning",
    ),
    EvalQuestion(
        question="Transfer learning là gì?",
        expected_keywords=["transfer", "learning", "pre-trained", "fine-tune"],
        category="Deep Learning",
    ),
    EvalQuestion(
        question="Explain the attention mechanism in transformers",
        expected_keywords=["attention", "transformer", "self-attention", "query", "key", "value"],
        category="Deep Learning",
    ),
    EvalQuestion(
        question="Batch normalization có tác dụng gì?",
        expected_keywords=["batch", "normalization", "normalize", "training", "stable"],
        category="Deep Learning",
    ),
    EvalQuestion(
        question="Precision và Recall khác nhau như thế nào?",
        expected_keywords=["precision", "recall", "true positive", "false positive"],
        category="Evaluation",
    ),
    EvalQuestion(
        question="AUC-ROC là gì?",
        expected_keywords=["AUC", "ROC", "true positive rate", "false positive rate"],
        category="Evaluation",
    ),
    EvalQuestion(
        question="Random Forest hoạt động như thế nào?",
        expected_keywords=["random", "forest", "decision tree", "ensemble", "bagging"],
        category="Traditional ML",
    ),
    EvalQuestion(
        question="SVM là gì và khi nào nên sử dụng?",
        expected_keywords=["SVM", "support vector", "kernel", "margin", "classification"],
        category="Traditional ML",
    ),
    EvalQuestion(
        question="PCA dùng để làm gì?",
        expected_keywords=["PCA", "principal component", "dimensionality", "reduction"],
        category="Traditional ML",
    ),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    query: str
    retrieved_chunk_ids: list[str]
    relevant_chunk_ids: list[str]
    latency_ms: float


@dataclass
class GenerationResult:
    query: str
    answer: str
    context: str
    latency_ms: float
    faithfulness_score: float = 0.0
    relevancy_score: float = 0.0


@dataclass
class EvalMetrics:
    # Retrieval
    precision_at_5: float = 0.0
    recall_at_5: float = 0.0
    mrr: float = 0.0
    hit_rate: float = 0.0
    # Generation
    avg_faithfulness: float = 0.0
    avg_relevancy: float = 0.0
    # Performance
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_queries: int = 0


# ---------------------------------------------------------------------------
# Retrieval evaluation
# ---------------------------------------------------------------------------

def _find_relevant_chunks(
    db: Any,
    project_id: uuid.UUID,
    question: EvalQuestion,
) -> set[str]:
    """Find relevant chunk IDs by keyword matching in chunk content."""
    from app.storage.models import Chunk, Document, Source

    rows = (
        db.query(Chunk.id, Chunk.content)
        .join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .filter(Source.project_id == project_id)
        .all()
    )

    relevant: set[str] = set()
    for chunk_id, content in rows:
        if not content:
            continue
        lower_content = content.lower()
        matches = sum(1 for kw in question.expected_keywords if kw.lower() in lower_content)
        if matches >= 2:
            relevant.add(str(chunk_id))
    return relevant


def run_retrieval_eval(
    db: Any,
    project_id: uuid.UUID,
    dataset: list[EvalQuestion],
    top_k: int = 5,
) -> list[RetrievalResult]:
    """Run retrieval evaluation on test dataset."""
    from app.services.query_service import retrieve_hybrid_evidence

    results: list[RetrievalResult] = []
    for i, question in enumerate(dataset, 1):
        print(f"  [{i}/{len(dataset)}] Retrieval: {question.question[:60]}...")
        start = time.perf_counter()
        try:
            retrieval = retrieve_hybrid_evidence(
                db,
                project_id=project_id,
                query=question.question,
                top_k=top_k,
                _allow_lazy_indexing=False,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            retrieved_ids = [r.id for r in retrieval.records]
            relevant_ids = _find_relevant_chunks(db, project_id, question)
            results.append(RetrievalResult(
                query=question.question,
                retrieved_chunk_ids=retrieved_ids,
                relevant_chunk_ids=list(relevant_ids),
                latency_ms=latency_ms,
            ))
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            print(f"    ⚠ Error: {exc}")
            results.append(RetrievalResult(
                query=question.question,
                retrieved_chunk_ids=[],
                relevant_chunk_ids=list(_find_relevant_chunks(db, project_id, question)),
                latency_ms=latency_ms,
            ))
    return results


def compute_retrieval_metrics(results: list[RetrievalResult], k: int = 5) -> dict[str, float]:
    """Compute Precision@K, Recall@K, MRR, Hit Rate."""
    if not results:
        return {"precision_at_k": 0, "recall_at_k": 0, "mrr": 0, "hit_rate": 0}

    precisions: list[float] = []
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    hits = 0

    for result in results:
        retrieved = result.retrieved_chunk_ids[:k]
        relevant = set(result.relevant_chunk_ids)

        if not relevant:
            # No relevant chunks found — skip this query for retrieval metrics
            continue

        # Precision@K
        relevant_retrieved = sum(1 for cid in retrieved if cid in relevant)
        precision = relevant_retrieved / len(retrieved) if retrieved else 0
        precisions.append(precision)

        # Recall@K
        recall = relevant_retrieved / len(relevant) if relevant else 0
        recalls.append(recall)

        # MRR
        rr = 0.0
        for rank, cid in enumerate(retrieved, start=1):
            if cid in relevant:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        # Hit Rate
        if any(cid in relevant for cid in retrieved):
            hits += 1

    n = len(precisions) or 1
    return {
        "precision_at_k": sum(precisions) / n,
        "recall_at_k": sum(recalls) / n,
        "mrr": sum(reciprocal_ranks) / n,
        "hit_rate": hits / n,
    }


# ---------------------------------------------------------------------------
# Generation evaluation (LLM-as-judge)
# ---------------------------------------------------------------------------

def _call_llm_judge(prompt: str, provider: str, api_key: str, model: str, base_url: str | None = None) -> str:
    """Call LLM to judge answer quality."""
    if provider == "gemini":
        import google.genai as genai
        client = genai.Client(api_key=api_key)
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return (getattr(response, "text", None) or "").strip()
        finally:
            client.close()
    else:
        from openai import OpenAI
        kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": 0, "timeout": 30}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return (response.choices[0].message.content or "").strip()


def _parse_score(response: str) -> float:
    """Extract a 0-1 score from LLM judge response."""
    import re
    match = re.search(r"(\d+(?:\.\d+)?)", response)
    if match:
        score = float(match.group(1))
        if score > 1:
            score = score / 10.0
        return max(0.0, min(1.0, score))
    return 0.5


def evaluate_generation(
    query: str,
    answer: str,
    context: str,
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> tuple[float, float]:
    """Use LLM-as-judge to evaluate faithfulness and relevancy."""
    # Faithfulness
    faith_prompt = (
        "Rate the faithfulness of the answer (0-10). Faithfulness means the answer "
        "is grounded in the context and does not contain hallucinated information.\n\n"
        f"Context:\n{context[:2000]}\n\n"
        f"Question: {query}\n\n"
        f"Answer: {answer[:1000]}\n\n"
        "Score (0-10):"
    )
    faith_response = _call_llm_judge(faith_prompt, provider, api_key, model, base_url)
    faithfulness = _parse_score(faith_response)

    # Relevancy
    relev_prompt = (
        "Rate how relevant the answer is to the question (0-10). "
        "The answer should directly address what was asked.\n\n"
        f"Question: {query}\n\n"
        f"Answer: {answer[:1000]}\n\n"
        "Score (0-10):"
    )
    relev_response = _call_llm_judge(relev_prompt, provider, api_key, model, base_url)
    relevancy = _parse_score(relev_response)

    return faithfulness, relevancy


def run_generation_eval(
    db: Any,
    project_id: uuid.UUID,
    dataset: list[EvalQuestion],
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
    top_k: int = 5,
) -> list[GenerationResult]:
    """Run generation evaluation on test dataset."""
    from app.services.query_service import search_knowledge_base

    results: list[GenerationResult] = []
    for i, question in enumerate(dataset, 1):
        print(f"  [{i}/{len(dataset)}] Generation: {question.question[:60]}...")
        start = time.perf_counter()
        try:
            result = search_knowledge_base(
                db,
                project_id=project_id,
                query=question.question,
                provider=provider,
                top_k=top_k,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            answer = result.get("answer", "")
            citations = result.get("citations", [])
            context = "\n".join(
                f"[{c.get('citation_id', '')}] {c.get('quote', '')}"
                for c in citations[:5]
            )

            faithfulness, relevancy = evaluate_generation(
                question.question, answer, context,
                provider, api_key, model, base_url,
            )

            results.append(GenerationResult(
                query=question.question,
                answer=answer,
                context=context,
                latency_ms=latency_ms,
                faithfulness_score=faithfulness,
                relevancy_score=relevancy,
            ))
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            print(f"    ⚠ Error: {exc}")
            results.append(GenerationResult(
                query=question.question,
                answer=f"ERROR: {exc}",
                context="",
                latency_ms=latency_ms,
            ))
    return results


def compute_generation_metrics(results: list[GenerationResult]) -> dict[str, float]:
    """Compute average faithfulness and relevancy."""
    if not results:
        return {"avg_faithfulness": 0, "avg_relevancy": 0}

    faith_scores = [r.faithfulness_score for r in results if r.faithfulness_score > 0]
    relev_scores = [r.relevancy_score for r in results if r.relevancy_score > 0]

    return {
        "avg_faithfulness": sum(faith_scores) / len(faith_scores) if faith_scores else 0,
        "avg_relevancy": sum(relev_scores) / len(relev_scores) if relev_scores else 0,
    }


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------

def compute_performance_metrics(
    retrieval_results: list[RetrievalResult],
    generation_results: list[GenerationResult],
) -> dict[str, float]:
    """Compute latency metrics."""
    latencies = [r.latency_ms for r in retrieval_results]
    latencies += [r.latency_ms for r in generation_results]

    if not latencies:
        return {"avg_latency_ms": 0, "p95_latency_ms": 0}

    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    return {
        "avg_latency_ms": sum(latencies) / len(latencies),
        "p95_latency_ms": latencies[min(p95_index, len(latencies) - 1)],
    }


# ---------------------------------------------------------------------------
# CLI Output
# ---------------------------------------------------------------------------

def _progress_bar(value: float, width: int = 20) -> str:
    filled = int(value * width)
    return "█" * filled + "░" * (width - filled)


def print_cli_report(
    retrieval_metrics: dict[str, float],
    generation_metrics: dict[str, float],
    performance_metrics: dict[str, float],
    dataset_size: int,
) -> None:
    """Print evaluation report to CLI."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           RAG Evaluation Report — NoteMesh                  ║")
    print(f"║           Date: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC'):<44}║")
    print(f"║           Test Queries: {dataset_size:<37}║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Retrieval Metrics                                          ║")
    print("╠══════════════════════════════════════════════════════════════╣")

    for label, key in [
        ("Precision@5", "precision_at_k"),
        ("Recall@5   ", "recall_at_k"),
        ("MRR        ", "mrr"),
        ("Hit Rate   ", "hit_rate"),
    ]:
        val = retrieval_metrics.get(key, 0)
        bar = _progress_bar(val)
        print(f"║    {label}: {val:.2f}  {bar}  ║")

    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Generation Metrics                                         ║")
    print("╠══════════════════════════════════════════════════════════════╣")

    for label, key in [
        ("Faithfulness  ", "avg_faithfulness"),
        ("Answer Relev. ", "avg_relevancy"),
    ]:
        val = generation_metrics.get(key, 0)
        bar = _progress_bar(val)
        print(f"║    {label}: {val:.2f}  {bar}  ║")

    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Performance                                                ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    avg = performance_metrics.get("avg_latency_ms", 0)
    p95 = performance_metrics.get("p95_latency_ms", 0)
    print(f"║    Avg Latency:  {avg:>8.0f} ms                                ║")
    print(f"║    P95 Latency:  {p95:>8.0f} ms                                ║")
    print("╚══════════════════════════════════════════════════════════════╝")


# ---------------------------------------------------------------------------
# Markdown Export
# ---------------------------------------------------------------------------

def export_markdown(
    retrieval_metrics: dict[str, float],
    generation_metrics: dict[str, float],
    performance_metrics: dict[str, float],
    retrieval_results: list[RetrievalResult],
    generation_results: list[GenerationResult],
    output_path: Path,
) -> None:
    """Export evaluation report to Markdown."""
    lines: list[str] = []
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines.append("# RAG Evaluation Report — NoteMesh")
    lines.append("")
    lines.append(f"**Date:** {now}  ")
    lines.append(f"**Test Queries:** {len(retrieval_results)}  ")
    lines.append("")

    lines.append("## 1. Retrieval Metrics")
    lines.append("")
    lines.append("| Metric | Score | Description |")
    lines.append("|--------|-------|-------------|")
    lines.append(f"| Precision@5 | {retrieval_metrics.get('precision_at_k', 0):.3f} | Of top 5 results, % that are relevant |")
    lines.append(f"| Recall@5 | {retrieval_metrics.get('recall_at_k', 0):.3f} | Of all relevant chunks, % found in top 5 |")
    lines.append(f"| MRR | {retrieval_metrics.get('mrr', 0):.3f} | Mean Reciprocal Rank of first relevant result |")
    lines.append(f"| Hit Rate | {retrieval_metrics.get('hit_rate', 0):.3f} | % of queries with at least 1 relevant result |")
    lines.append("")

    lines.append("## 2. Generation Metrics (LLM-as-Judge)")
    lines.append("")
    lines.append("| Metric | Score | Description |")
    lines.append("|--------|-------|-------------|")
    lines.append(f"| Faithfulness | {generation_metrics.get('avg_faithfulness', 0):.3f} | Answer grounded in context (no hallucination) |")
    lines.append(f"| Answer Relevancy | {generation_metrics.get('avg_relevancy', 0):.3f} | Answer addresses the question |")
    lines.append("")

    lines.append("## 3. Performance")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Avg Latency | {performance_metrics.get('avg_latency_ms', 0):.0f} ms |")
    lines.append(f"| P95 Latency | {performance_metrics.get('p95_latency_ms', 0):.0f} ms |")
    lines.append("")

    lines.append("## 4. Detailed Results")
    lines.append("")
    lines.append("### Retrieval Results")
    lines.append("")
    lines.append("| # | Query | Retrieved | Relevant | Precision | MRR |")
    lines.append("|---|-------|-----------|----------|-----------|-----|")
    for i, r in enumerate(retrieval_results, 1):
        relevant_set = set(r.relevant_chunk_ids)
        retrieved_set = set(r.retrieved_chunk_ids[:5])
        relevant_retrieved = len(retrieved_set & relevant_set)
        precision = relevant_retrieved / len(retrieved_set) if retrieved_set else 0
        rr = 0.0
        for rank, cid in enumerate(r.retrieved_chunk_ids[:5], 1):
            if cid in relevant_set:
                rr = 1.0 / rank
                break
        lines.append(
            f"| {i} | {r.query[:50]}... | {len(retrieved_set)} | {len(relevant_set)} | {precision:.2f} | {rr:.2f} |"
        )
    lines.append("")

    lines.append("### Generation Results")
    lines.append("")
    lines.append("| # | Query | Faith. | Relev. | Latency |")
    lines.append("|---|-------|--------|--------|---------|")
    for i, g in enumerate(generation_results, 1):
        lines.append(
            f"| {i} | {g.query[:50]}... | {g.faithfulness_score:.2f} | {g.relevancy_score:.2f} | {g.latency_ms:.0f}ms |"
        )
    lines.append("")

    lines.append("### Sample Answers")
    lines.append("")
    for i, g in enumerate(generation_results[:5], 1):
        lines.append(f"**Q{i}:** {g.query}  ")
        lines.append(f"**A{i}:** {g.answer[:300]}{'...' if len(g.answer) > 300 else ''}  ")
        lines.append(f"**Faithfulness:** {g.faithfulness_score:.2f} | **Relevancy:** {g.relevancy_score:.2f}  ")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ Markdown report exported to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="RAG Evaluation — NoteMesh")
    parser.add_argument("--project-id", type=str, help="Project UUID to evaluate")
    parser.add_argument("--output", type=str, default="eval_report.md", help="Markdown output path")
    parser.add_argument("--top-k", type=int, default=5, help="Top K for retrieval")
    parser.add_argument("--dataset", type=str, help="Custom dataset JSON file path")
    parser.add_argument("--provider", type=str, default=None, help="LLM provider (openai/gemini)")
    parser.add_argument("--skip-generation", action="store_true", help="Skip generation eval (faster)")
    args = parser.parse_args()

    # Imports
    from app.services.provider_settings_service import (
        normalize_provider,
        resolve_chat_provider_config,
    )
    from app.storage.db import SessionLocal
    from app.storage.models import Project

    db = SessionLocal()

    try:
        # Find project
        if args.project_id:
            project_id = uuid.UUID(args.project_id)
            project = db.get(Project, project_id)
            if not project:
                print(f"❌ Project {args.project_id} not found")
                return 1
        else:
            project = db.query(Project).first()
            if not project:
                print("❌ No projects found. Create a project and upload sources first.")
                return 1
            project_id = project.id

        print(f"📋 Evaluating project: {project.name} ({project_id})")

        # Load dataset
        if args.dataset:
            raw = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
            dataset = [EvalQuestion(**q) for q in raw]
        else:
            dataset = DEFAULT_TEST_DATASET

        print(f"📝 Test dataset: {len(dataset)} queries")
        print()

        # --- Retrieval Evaluation ---
        print("🔍 Running retrieval evaluation...")
        retrieval_results = run_retrieval_eval(db, project_id, dataset, top_k=args.top_k)
        retrieval_metrics = compute_retrieval_metrics(retrieval_results, k=args.top_k)
        print()

        # --- Generation Evaluation ---
        generation_results: list[GenerationResult] = []
        generation_metrics: dict[str, float] = {"avg_faithfulness": 0, "avg_relevancy": 0}

        if not args.skip_generation:
            # Resolve provider
            provider = args.provider or "openai"
            try:
                answer_provider = normalize_provider(provider)
                gen_config = resolve_chat_provider_config(db, project_id, answer_provider)
            except Exception as exc:
                print(f"⚠ Cannot resolve provider config: {exc}")
                print("  Skipping generation evaluation (use --skip-generation to suppress this)")
                args.skip_generation = True

            if not args.skip_generation:
                print("🤖 Running generation evaluation...")
                generation_results = run_generation_eval(
                    db, project_id, dataset,
                    provider=answer_provider,
                    api_key=gen_config["api_key"],
                    model=gen_config["chat_model"],
                    base_url=gen_config.get("base_url"),
                    top_k=args.top_k,
                )
                generation_metrics = compute_generation_metrics(generation_results)
                print()

        # --- Performance ---
        performance_metrics = compute_performance_metrics(retrieval_results, generation_results)

        # --- Output ---
        print_cli_report(retrieval_metrics, generation_metrics, performance_metrics, len(dataset))

        output_path = Path(args.output)
        export_markdown(
            retrieval_metrics, generation_metrics, performance_metrics,
            retrieval_results, generation_results, output_path,
        )

        return 0

    except Exception as exc:
        print(f"❌ Evaluation failed: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
