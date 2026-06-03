# RAG Evaluation Report — NoteMesh

**Date:** 2026-06-02 09:44 UTC  
**Test Queries:** 15  

## 1. Retrieval Metrics

| Metric | Score | Description |
|--------|-------|-------------|
| Precision@5 | 0.529 | Of top 5 results, % that are relevant |
| Recall@5 | 0.449 | Of all relevant chunks, % found in top 5 |
| MRR | 0.804 | Mean Reciprocal Rank of first relevant result |
| Hit Rate | 0.929 | % of queries with at least 1 relevant result |

## 2. Generation Metrics (LLM-as-Judge)

| Metric | Score | Description |
|--------|-------|-------------|
| Faithfulness | 0.000 | Answer grounded in context (no hallucination) |
| Answer Relevancy | 0.000 | Answer addresses the question |

## 3. Performance

| Metric | Value |
|--------|-------|
| Avg Latency | 2351 ms |
| P95 Latency | 11416 ms |

## 4. Detailed Results

### Retrieval Results

| # | Query | Retrieved | Relevant | Precision | MRR |
|---|-------|-----------|----------|-----------|-----|
| 1 | Gradient descent là gì?... | 5 | 7 | 0.60 | 1.00 |
| 2 | What is the difference between supervised and unsu... | 5 | 5 | 0.60 | 1.00 |
| 3 | Overfitting là gì và cách khắc phục?... | 5 | 4 | 0.40 | 1.00 |
| 4 | Explain the bias-variance tradeoff... | 5 | 13 | 1.00 | 1.00 |
| 5 | Cross-validation hoạt động như thế nào?... | 5 | 9 | 0.40 | 0.50 |
| 6 | What is a neural network?... | 5 | 9 | 0.80 | 1.00 |
| 7 | CNN và RNN khác nhau như thế nào?... | 5 | 7 | 0.60 | 1.00 |
| 8 | Transfer learning là gì?... | 5 | 0 | 0.00 | 0.00 |
| 9 | Explain the attention mechanism in transformers... | 5 | 2 | 0.00 | 0.00 |
| 10 | Batch normalization có tác dụng gì?... | 5 | 10 | 1.00 | 1.00 |
| 11 | Precision và Recall khác nhau như thế nào?... | 5 | 3 | 0.40 | 1.00 |
| 12 | AUC-ROC là gì?... | 5 | 1 | 0.20 | 0.25 |
| 13 | Random Forest hoạt động như thế nào?... | 5 | 7 | 0.60 | 1.00 |
| 14 | SVM là gì và khi nào nên sử dụng?... | 5 | 4 | 0.20 | 0.50 |
| 15 | PCA dùng để làm gì?... | 5 | 7 | 0.60 | 1.00 |

### Generation Results

| # | Query | Faith. | Relev. | Latency |
|---|-------|--------|--------|---------|
| 1 | Gradient descent là gì?... | 0.00 | 0.00 | 47104ms |
| 2 | What is the difference between supervised and unsu... | 0.00 | 0.00 | 903ms |
| 3 | Overfitting là gì và cách khắc phục?... | 0.00 | 0.00 | 686ms |
| 4 | Explain the bias-variance tradeoff... | 0.00 | 0.00 | 638ms |
| 5 | Cross-validation hoạt động như thế nào?... | 0.00 | 0.00 | 667ms |
| 6 | What is a neural network?... | 0.00 | 0.00 | 658ms |
| 7 | CNN và RNN khác nhau như thế nào?... | 0.00 | 0.00 | 703ms |
| 8 | Transfer learning là gì?... | 0.00 | 0.00 | 731ms |
| 9 | Explain the attention mechanism in transformers... | 0.00 | 0.00 | 698ms |
| 10 | Batch normalization có tác dụng gì?... | 0.00 | 0.00 | 694ms |
| 11 | Precision và Recall khác nhau như thế nào?... | 0.00 | 0.00 | 676ms |
| 12 | AUC-ROC là gì?... | 0.00 | 0.00 | 688ms |
| 13 | Random Forest hoạt động như thế nào?... | 0.00 | 0.00 | 673ms |
| 14 | SVM là gì và khi nào nên sử dụng?... | 0.00 | 0.00 | 683ms |
| 15 | PCA dùng để làm gì?... | 0.00 | 0.00 | 700ms |

### Sample Answers

**Q1:** Gradient descent là gì?  
**A1:** ERROR: Request timed out.  
**Faithfulness:** 0.00 | **Relevancy:** 0.00  

**Q2:** What is the difference between supervised and unsupervised learning?  
**A2:** ERROR: OpenAI request failed during generation.  
**Faithfulness:** 0.00 | **Relevancy:** 0.00  

**Q3:** Overfitting là gì và cách khắc phục?  
**A3:** ERROR: OpenAI request failed during generation.  
**Faithfulness:** 0.00 | **Relevancy:** 0.00  

**Q4:** Explain the bias-variance tradeoff  
**A4:** ERROR: OpenAI request failed during generation.  
**Faithfulness:** 0.00 | **Relevancy:** 0.00  

**Q5:** Cross-validation hoạt động như thế nào?  
**A5:** ERROR: OpenAI request failed during generation.  
**Faithfulness:** 0.00 | **Relevancy:** 0.00  
