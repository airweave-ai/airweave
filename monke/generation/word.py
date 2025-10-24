"""Word-specific generation adapter: document content generator."""

from typing import List, Tuple

from monke.client.llm import LLMClient
from monke.generation.schemas.word import WordDocumentContent


async def generate_word_document(model: str, token: str, doc_type: str) -> WordDocumentContent:
    """Generate realistic Word document content with embedded verification token.

    Args:
        model: LLM model to use
        token: Unique verification token to embed in content
        doc_type: Type of document (e.g., 'Report', 'Memo', 'Proposal')

    Returns:
        WordDocumentContent with title, content, and summary
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate realistic content for a Word document of type '{doc_type}'. "
        f"Create a professional document with a title, detailed content (3-5 paragraphs), "
        f"and a brief summary. "
        f"You MUST include the literal token '{token}' naturally within the content text. "
        "The document should look professional and realistic (e.g., business report, project proposal, meeting notes). "
        "Return JSON with: title (string), content (string with markdown formatting), "
        "summary (string)."
    )

    doc_content = await llm.generate_structured(WordDocumentContent, instruction)

    # Ensure token appears somewhere in the content
    if token not in doc_content.content and token not in doc_content.title:
        # Add token to the end of the content if not present
        doc_content.content = f"{doc_content.content}\n\nReference ID: {token}"

    return doc_content


async def generate_documents_content(
    model: str, tokens: List[str], base_name: str = "Test Document"
) -> Tuple[List[str], List[WordDocumentContent]]:
    """Generate content for multiple Word documents.

    Args:
        model: LLM model to use
        tokens: List of verification tokens (one per document)
        base_name: Base name for the documents

    Returns:
        Tuple of (list of filenames, list of document content)
    """
    documents = []
    filenames = []

    doc_types = [
        "Business Report",
        "Project Proposal",
        "Meeting Notes",
        "Technical Specification",
        "Strategic Plan",
    ]

    for i, token in enumerate(tokens):
        doc_type = doc_types[i] if i < len(doc_types) else f"Document {i + 1}"
        doc_content = await generate_word_document(model, token, doc_type)
        documents.append(doc_content)

        # Generate filename
        safe_title = doc_content.title.replace(" ", "_")[:40]
        filename = f"Monke_{safe_title}.docx"
        filenames.append(filename)

    return filenames, documents

