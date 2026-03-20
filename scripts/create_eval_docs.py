"""Generate the three synthetic evaluation PDFs used by the RAGAS eval pipeline.

The text content is deliberately written to contain the exact facts that
data/eval/qa_pairs.json ground-truth answers are drawn from.  Running this
script is a prerequisite for the integration eval runner (tests/evals/run_evals.py).

Usage:
    uv run python scripts/create_eval_docs.py
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path("data/eval/documents")


def _make_pdf(title: str, sections: list[tuple[str, str]]) -> FPDF:
    """Create a simple two-column PDF with heading + body sections."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.multi_cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, body, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    return pdf


def create_ai_concepts() -> Path:
    sections = [
        (
            "Supervised vs Unsupervised Learning",
            "Supervised learning trains on labeled data where the correct output is known for each "
            "input. The model learns a mapping from inputs to outputs by minimising a loss function "
            "computed against the known labels. Unsupervised learning finds patterns in unlabeled "
            "data without predefined correct answers. Common unsupervised techniques include "
            "clustering, dimensionality reduction, and generative modelling.",
        ),
        (
            "Transformer Architecture",
            "A transformer is a neural network architecture built on self-attention mechanisms that "
            "processes all input tokens in parallel rather than sequentially. Self-attention computes "
            "a weighted sum of all token representations in a sequence. For each token it calculates "
            "query, key, and value vectors. The dot product of the query with all keys determines "
            "attention weights, which are then applied to the values to produce a context-aware "
            "representation. Transformers power state-of-the-art language models such as GPT and "
            "BERT and enable training on much larger datasets than earlier sequential architectures.",
        ),
        (
            "Retrieval-Augmented Generation (RAG)",
            "RAG stands for Retrieval-Augmented Generation. It solves the problem of language model "
            "hallucination by retrieving relevant documents from an external knowledge base before "
            "generating an answer, grounding the response in retrieved evidence. A RAG system "
            "retrieves information from an external knowledge base at query time, so it can access "
            "up-to-date documents without retraining. A fine-tuned model bakes knowledge into its "
            "weights during training and cannot incorporate new facts without another fine-tuning run, "
            "making RAG superior for frequently updated information.",
        ),
        (
            "Embeddings and Vector Databases",
            "An embedding is a dense numerical vector representation of data such as text, images, "
            "or audio. Semantically similar items are mapped to nearby points in vector space, "
            "enabling similarity search and downstream machine learning tasks. A vector database "
            "stores and indexes high-dimensional embedding vectors, enabling fast approximate "
            "nearest-neighbour search. Unlike a relational database that queries by exact field "
            "values, a vector database retrieves items by semantic similarity measured as distance "
            "in vector space.",
        ),
        (
            "Fine-Tuning",
            "Fine-tuning is the process of continuing to train a pre-trained model on a "
            "domain-specific dataset so it learns task-specific patterns. You would use it when the "
            "base model performs poorly on a specialized domain and you have sufficient labeled "
            "training data.",
        ),
        (
            "Hallucination",
            "Hallucination is when a language model generates text that sounds plausible but is "
            "factually incorrect or entirely fabricated. It occurs because models predict "
            "statistically likely tokens rather than verifying facts against a knowledge base. "
            "If a retrieval system has high context recall but low faithfulness, the information "
            "needed for a correct answer was available but the language model is hallucinating "
            "rather than grounding its answer in the evidence.",
        ),
        (
            "Hybrid Retrieval: BM25, RRF, and Cross-Encoders",
            "BM25 is a probabilistic keyword-based ranking function that scores documents by term "
            "frequency and inverse document frequency. It complements vector search by capturing "
            "exact keyword matches that semantic embeddings can miss, so combining both retrieval "
            "signals produces more complete results. Reciprocal Rank Fusion is a score combination "
            "method that assigns each document a score of 1 divided by its rank plus a constant for "
            "each retrieval system, then sums these scores across systems. It is used because it is "
            "robust to score scale differences between vector and keyword retrieval. A cross-encoder "
            "reranks an initial set of retrieved candidates by processing each query-document pair "
            "jointly through a transformer, producing a relevance score more accurate than cosine "
            "similarity alone. It trades speed for precision and is applied after fast first-stage "
            "retrieval.",
        ),
        (
            "RLHF",
            "RLHF stands for Reinforcement Learning from Human Feedback. It is used to align "
            "language models with human preferences by training a reward model on human comparisons "
            "between outputs, then using reinforcement learning to optimize the language model to "
            "produce higher-reward responses.",
        ),
        (
            "Multimodal Models",
            "A language model processes only text inputs and generates text outputs. A multimodal "
            "model can process and generate multiple modalities such as text, images, and audio, "
            "enabling tasks like image captioning or visual question answering.",
        ),
        (
            "Prompts and System Prompts",
            "A system prompt is a persistent instruction provided at the start of a conversation "
            "that sets the model's persona, tone, and constraints. A user prompt is the message "
            "sent by the user in each turn. The system prompt influences all subsequent responses "
            "while the user prompt drives the immediate reply. Temperature scales the probability "
            "distribution over tokens before sampling. A low temperature near zero makes the model "
            "deterministic and predictable, favouring high-probability tokens. A high temperature "
            "flattens the distribution, increasing diversity and creativity but also increasing the "
            "chance of incoherent output.",
        ),
    ]
    pdf = _make_pdf("AI Concepts Reference Guide", sections)
    out = OUTPUT_DIR / "ai_concepts.pdf"
    pdf.output(str(out))
    return out


def create_product_spec() -> Path:
    sections = [
        (
            "Pricing Tiers",
            "DataVault Pro offers three pricing tiers: Free, Professional at 49 dollars per month, "
            "and Enterprise with custom pricing. Free tier users can upgrade to Professional at any "
            "time. Billing is prorated from the date of upgrade so the user pays only for the "
            "remaining days in the billing cycle.",
        ),
        (
            "API Rate Limits",
            "The DataVault Pro free tier allows 100 API requests per day with a maximum of "
            "10 requests per minute. The Professional tier allows 10,000 API requests per day with "
            "a rate of 100 requests per minute. The Enterprise tier has custom rate limits "
            "negotiated based on expected usage volume.",
        ),
        (
            "Storage and Data Retention",
            "The Professional tier includes 100 gigabytes of storage per workspace. Professional "
            "tier users who exceed 100 GB can purchase additional storage in 50 GB increments at "
            "10 dollars per month each, or upgrade to the Enterprise tier for custom storage limits. "
            "DataVault Pro retains data for free tier users for 30 days, after which documents and "
            "associated embeddings are automatically deleted. Users receive an email notification "
            "7 days before deletion occurs.",
        ),
        (
            "SLA and Uptime",
            "The DataVault Pro Professional tier guarantees 99.9 percent uptime as part of its SLA. "
            "Enterprise tier customers receive priority support with a guaranteed initial response "
            "time of 4 hours for critical issues.",
        ),
        (
            "Supported File Formats",
            "DataVault Pro supports PDF, DOCX, TXT, Markdown, HTML, and CSV file formats for "
            "document ingestion. The Professional tier allows a maximum file size of 50 megabytes "
            "per document upload.",
        ),
        (
            "Authentication and Security",
            "The DataVault Pro API supports API key authentication for all tiers and OAuth 2.0 "
            "for Professional and Enterprise tiers. DataVault Pro offers SAML 2.0 single sign-on "
            "support exclusively on the Enterprise tier. A startup requiring SSO and more than "
            "100 GB of storage would need the Enterprise tier, since SSO is only available on "
            "Enterprise.",
        ),
        (
            "SDK Support",
            "The DataVault Pro SDK officially supports Python, JavaScript, and Go.",
        ),
        (
            "Webhooks and Integrations",
            "DataVault Pro supports webhook events for document.uploaded, document.processed, "
            "document.deleted, and query.completed, allowing external systems to react to pipeline "
            "state changes in real time.",
        ),
    ]
    pdf = _make_pdf("DataVault Pro Product Specification", sections)
    out = OUTPUT_DIR / "product_spec.pdf"
    pdf.output(str(out))
    return out


def create_science_report() -> Path:
    sections = [
        (
            "Global Temperature Trends",
            "The 2024 climate report recorded a global average temperature anomaly of +1.45 degrees "
            "Celsius above the pre-industrial baseline, the highest annual value on record. The "
            "2024 temperature anomaly of +1.45 degrees Celsius is 0.05 degrees below the Paris "
            "Agreement 1.5 degree Celsius threshold, indicating the world is close to breaching the "
            "lower limit target set in 2015. Under the high-emission scenario, current CO2 "
            "concentration trends project a global average temperature anomaly of approximately "
            "2.1 to 2.4 degrees Celsius above pre-industrial levels by 2050.",
        ),
        (
            "Atmospheric CO2 and Emissions",
            "The 2024 science report recorded an atmospheric CO2 concentration of 422 parts per "
            "million, the highest annual average in recorded history. The European Union showed the "
            "greatest reduction in coal power generation between 2015 and 2024, reducing coal's "
            "share of its electricity mix from 25 percent to 8 percent.",
        ),
        (
            "Arctic Sea Ice and Ocean Warming",
            "Arctic sea ice extent declined by approximately 13 percent per decade between 1980 "
            "and 2024, representing a total reduction of roughly 40 percent compared to the 1980 "
            "baseline. The report projects that at the observed rate of decline, the Arctic Ocean "
            "is likely to experience its first ice-free summer before 2040 under current emission "
            "trajectories. The Arctic Ocean showed the highest rate of warming between 2010 and "
            "2024, warming at approximately four times the global average rate.",
        ),
        (
            "Sea Level Rise",
            "Global mean sea level rose by approximately 101 millimetres between 1993 and 2024, "
            "with the rate of rise accelerating from 2.5 mm per year in the 1990s to 4.6 mm per "
            "year in the 2020s. The two primary contributors to global sea level rise are thermal "
            "expansion of warming ocean water and the melting of land-based ice including glaciers "
            "and the Greenland and Antarctic ice sheets.",
        ),
        (
            "Renewable Energy Growth",
            "Solar and wind combined accounted for 34 percent of global electricity generation in "
            "2024, up from 12 percent in 2015. Global installed solar power capacity reached "
            "2,100 gigawatts at the end of 2024, having doubled in the preceding four years. "
            "Norway generated the highest share of electricity from renewable sources in 2024, "
            "with approximately 98 percent of its electricity coming from hydropower and other "
            "renewables. China had the largest absolute increase in renewable energy capacity "
            "between 2020 and 2024, adding over 600 gigawatts of solar and wind capacity during "
            "that period.",
        ),
        (
            "Extreme Weather Events",
            "The number of extreme heat events recorded globally in 2024 was five times higher "
            "than the average frequency observed during the 1990s baseline period.",
        ),
        (
            "Compound Risks for Coastal Urban Areas",
            "The report identifies compound risks for coastal urban areas including increased "
            "flooding frequency from rising seas combined with more intense precipitation events, "
            "urban heat island effects amplified by extreme heat events, and infrastructure stress "
            "from simultaneous thermal expansion and water damage.",
        ),
    ]
    pdf = _make_pdf("2024 Global Climate Data Report", sections)
    out = OUTPUT_DIR / "science_report.pdf"
    pdf.output(str(out))
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ai_path = create_ai_concepts()
    prod_path = create_product_spec()
    sci_path = create_science_report()

    print("Eval documents created:")
    print(f"  {ai_path}")
    print(f"  {prod_path}")
    print(f"  {sci_path}")


if __name__ == "__main__":
    main()
