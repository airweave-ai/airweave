"""Google Docs-specific generation adapter: document generator."""

from typing import List

from monke.client.llm import LLMClient
from monke.generation.schemas.google_docs import GoogleDocsDocument


async def generate_google_doc(
    model: str, token: str, doc_title: str
) -> GoogleDocsDocument:
    """Generate realistic Google Docs document content with embedded verification token.

    Args:
        model: LLM model to use
        token: Unique verification token to embed in content
        doc_title: Title for the document

    Returns:
        GoogleDocsDocument with title and content
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate realistic content for a Google Docs document titled '{doc_title}'. "
        f"Create 3-5 paragraphs of professional text (e.g., project proposal, meeting notes, or report). "
        f"You MUST include the literal token '{token}' naturally within the content. "
        "The content should look professional and realistic. "
        "Return JSON with: title (string), content (string with plain text, use \\n for newlines)."
    )

    doc = await llm.generate_structured(GoogleDocsDocument, instruction)
    doc.title = doc_title

    # Ensure token appears in the content
    if token not in doc.content:
        # Add token to the end if not present
        doc.content = f"{doc.content}\n\nVerification: {token}"

    return doc


async def generate_documents(
    model: str, tokens: List[str], base_name: str = "Test Document"
) -> List[GoogleDocsDocument]:
    """Generate multiple Google Docs documents.

    Args:
        model: LLM model to use
        tokens: List of verification tokens (one per document)
        base_name: Base name for the documents

    Returns:
        List of GoogleDocsDocument objects
    """
    documents = []

    doc_types = [
        "Project Proposal",
        "Meeting Notes",
        "Technical Report",
        "Design Document",
        "Research Summary",
    ]

    for i, token in enumerate(tokens):
        doc_type = doc_types[i] if i < len(doc_types) else f"Document {i + 1}"
        doc_title = f"{base_name} - {doc_type}"
        doc = await generate_google_doc(model, token, doc_title)
        documents.append(doc)

    return documents
