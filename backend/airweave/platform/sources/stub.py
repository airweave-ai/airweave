"""Stub source implementation for testing purposes.

Generates deterministic test entities with configurable distribution and speed.
All content is generated locally with no external API calls.
"""

import asyncio
import os
import random
import tempfile
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from airweave.platform.configs.auth import StubAuthConfig
from airweave.platform.configs.config import StubConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.stub import (
    CodeStubFileEntity,
    LargeStubEntity,
    LargeStubFileEntity,
    MediumStubEntity,
    SmallStubEntity,
    SmallStubFileEntity,
    StubContainerEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

# Word lists for deterministic content generation
NOUNS = [
    "project",
    "task",
    "document",
    "report",
    "meeting",
    "analysis",
    "review",
    "strategy",
    "plan",
    "update",
    "milestone",
    "feature",
    "bug",
    "request",
    "issue",
    "ticket",
    "story",
    "epic",
    "sprint",
    "release",
    "deployment",
    "integration",
    "module",
    "component",
    "service",
    "system",
    "database",
    "workflow",
    "process",
    "procedure",
    "guideline",
    "specification",
]

VERBS = [
    "implement",
    "review",
    "update",
    "create",
    "delete",
    "modify",
    "analyze",
    "test",
    "deploy",
    "configure",
    "optimize",
    "refactor",
    "debug",
    "fix",
    "document",
    "design",
    "plan",
    "schedule",
    "track",
    "monitor",
    "verify",
    "validate",
    "approve",
    "reject",
    "complete",
    "start",
    "finish",
    "pause",
]

ADJECTIVES = [
    "important",
    "urgent",
    "critical",
    "minor",
    "major",
    "quick",
    "detailed",
    "comprehensive",
    "preliminary",
    "final",
    "draft",
    "approved",
    "pending",
    "active",
    "inactive",
    "completed",
    "in-progress",
    "blocked",
    "ready",
    "new",
    "updated",
    "legacy",
    "modern",
    "automated",
    "manual",
    "secure",
]

AUTHORS = [
    "Alice Smith",
    "Bob Johnson",
    "Charlie Brown",
    "Diana Prince",
    "Eve Wilson",
    "Frank Miller",
    "Grace Lee",
    "Henry Davis",
    "Ivy Chen",
    "Jack Thompson",
]

STATUSES = ["active", "pending", "completed", "in-progress", "blocked", "draft"]
PRIORITIES = ["low", "normal", "high", "critical"]
CATEGORIES = ["engineering", "product", "design", "marketing", "operations", "research"]

# Code templates for code file generation
PYTHON_TEMPLATE = '''"""Module {module_name}: {description}."""

from typing import Any, Dict, List, Optional


class {class_name}:
    """A class that {class_description}."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the {class_name}.

        Args:
            name: Name identifier for this instance.
            config: Optional configuration dictionary.
        """
        self.name = name
        self.config = config or {{}}
        self._data: List[Any] = []

    def {method1}(self, item: Any) -> bool:
        """Process an item and add to internal storage.

        Args:
            item: The item to process.

        Returns:
            True if processing succeeded, False otherwise.
        """
        if item is None:
            return False
        self._data.append(item)
        return True

    def {method2}(self) -> List[Any]:
        """Retrieve all stored data.

        Returns:
            List of all processed items.
        """
        return list(self._data)

    def {method3}(self, key: str) -> Optional[Any]:
        """Get configuration value by key.

        Args:
            key: Configuration key to look up.

        Returns:
            Configuration value or None if not found.
        """
        return self.config.get(key)


def {function1}(data: List[Any]) -> int:
    """Calculate the total count of valid items.

    Args:
        data: List of items to count.

    Returns:
        Count of non-None items.
    """
    return sum(1 for item in data if item is not None)


def {function2}(items: List[str], prefix: str = "") -> List[str]:
    """Format items with optional prefix.

    Args:
        items: List of strings to format.
        prefix: Optional prefix to add.

    Returns:
        Formatted list of strings.
    """
    return [f"{{prefix}}{{item}}" for item in items]
'''

JS_TEMPLATE = """/**
 * {module_name} - {description}
 */

/**
 * {class_name} - {class_description}
 */
class {class_name} {{
  /**
   * Create a new {class_name} instance.
   * @param {{string}} name - Instance name
   * @param {{Object}} options - Configuration options
   */
  constructor(name, options = {{}}) {{
    this.name = name;
    this.options = options;
    this._items = [];
  }}

  /**
   * {method1} - Add an item to the collection.
   * @param {{*}} item - Item to add
   * @returns {{boolean}} Success status
   */
  {method1}(item) {{
    if (item === null || item === undefined) {{
      return false;
    }}
    this._items.push(item);
    return true;
  }}

  /**
   * {method2} - Get all items.
   * @returns {{Array}} All items
   */
  {method2}() {{
    return [...this._items];
  }}

  /**
   * {method3} - Get option by key.
   * @param {{string}} key - Option key
   * @returns {{*}} Option value
   */
  {method3}(key) {{
    return this.options[key];
  }}
}}

/**
 * {function1} - Process data array.
 * @param {{Array}} data - Input data
 * @returns {{number}} Processed count
 */
function {function1}(data) {{
  return data.filter(item => item != null).length;
}}

/**
 * {function2} - Format items with prefix.
 * @param {{string[]}} items - Items to format
 * @param {{string}} prefix - Prefix string
 * @returns {{string[]}} Formatted items
 */
function {function2}(items, prefix = '') {{
  return items.map(item => `${{prefix}}${{item}}`);
}}

export {{ {class_name}, {function1}, {function2} }};
"""


# Special tokens that may appear in AI-generated content and need to be handled by chunkers
SPECIAL_TOKENS = [
    "<|endoftext|>",  # OpenAI GPT end-of-text token
    "<|fim_prefix|>",  # Codex fill-in-middle tokens
    "<|fim_suffix|>",
    "<|fim_middle|>",
    "<|im_start|>",  # ChatML tokens
    "<|im_end|>",
]


class ContentGenerator:
    """Generates deterministic content using seeded random."""

    def __init__(
        self,
        seed: int,
        inject_special_tokens: bool = False,
        custom_content_prefix: Optional[str] = None,
    ):
        """Initialize with a random seed.

        Args:
            seed: Random seed for reproducible generation.
            inject_special_tokens: If True, randomly inject special tokenizer tokens.
            custom_content_prefix: Optional string to prepend to all content.
        """
        self.rng = random.Random(seed)
        self.base_time = datetime(2024, 1, 1, 0, 0, 0)
        self.inject_special_tokens = inject_special_tokens
        self.custom_content_prefix = custom_content_prefix

    def _pick(self, items: List[str]) -> str:
        """Pick a random item from list."""
        return self.rng.choice(items)

    def _maybe_inject_special_tokens(self, text: str) -> str:
        """Optionally inject special tokens into text.

        Args:
            text: Original text content.

        Returns:
            Text with special tokens injected if configured.
        """
        result = text

        # Add custom prefix if configured
        if self.custom_content_prefix:
            result = f"{self.custom_content_prefix}\n\n{result}"

        # Inject special tokens randomly throughout the text if configured
        if self.inject_special_tokens:
            # Insert 1-3 special tokens at random positions
            num_tokens = self.rng.randint(1, 3)
            words = result.split()
            for _ in range(num_tokens):
                if words:
                    token = self.rng.choice(SPECIAL_TOKENS)
                    pos = self.rng.randint(0, len(words))
                    words.insert(pos, token)
            result = " ".join(words)

        return result

    def _pick_n(self, items: List[str], n: int) -> List[str]:
        """Pick n unique random items from list."""
        return self.rng.sample(items, min(n, len(items)))

    def _generate_sentence(self, word_count: int = 10) -> str:
        """Generate a random sentence."""
        words = []
        for i in range(word_count):
            if i % 3 == 0:
                words.append(self._pick(ADJECTIVES))
            elif i % 3 == 1:
                words.append(self._pick(NOUNS))
            else:
                words.append(self._pick(VERBS))
        sentence = " ".join(words)
        return sentence.capitalize() + "."

    def _generate_paragraph(self, sentence_count: int = 5) -> str:
        """Generate a random paragraph."""
        sentences = [
            self._generate_sentence(self.rng.randint(8, 15)) for _ in range(sentence_count)
        ]
        return " ".join(sentences)

    def _generate_timestamp(self, days_offset: int = 0) -> datetime:
        """Generate a timestamp offset from base time."""
        return self.base_time + timedelta(
            days=days_offset,
            hours=self.rng.randint(0, 23),
            minutes=self.rng.randint(0, 59),
        )

    def generate_title(self) -> str:
        """Generate a random title."""
        adj = self._pick(ADJECTIVES)
        noun = self._pick(NOUNS)
        verb = self._pick(VERBS)
        return f"{adj.capitalize()} {noun} to {verb}"

    def generate_small_content(self) -> str:
        """Generate small content (~100-200 chars)."""
        content = self._generate_paragraph(2)
        return self._maybe_inject_special_tokens(content)

    def generate_medium_content(self) -> str:
        """Generate medium content (~500-1000 chars)."""
        paragraphs = [self._generate_paragraph(4) for _ in range(2)]
        content = "\n\n".join(paragraphs)
        return self._maybe_inject_special_tokens(content)

    def generate_large_content(self) -> str:
        """Generate large content (~3000-5000 chars)."""
        sections = []
        for i in range(5):
            section_title = f"## Section {i + 1}: {self.generate_title()}"
            section_content = "\n\n".join([self._generate_paragraph(5) for _ in range(3)])
            sections.append(f"{section_title}\n\n{section_content}")
        content = "\n\n".join(sections)
        return self._maybe_inject_special_tokens(content)

    def generate_small_file_content(self) -> Tuple[str, str]:
        """Generate small file content (~1-5 KB).

        Returns:
            Tuple of (content, extension).
        """
        lines = [f"Row {i + 1}: {self._generate_sentence(6)}" for i in range(50)]
        content = "\n".join(lines)
        return self._maybe_inject_special_tokens(content), ".txt"

    def generate_large_file_content(self) -> Tuple[str, str]:
        """Generate large file content (~50-100 KB).

        Returns:
            Tuple of (content, extension).
        """
        sections = []
        for i in range(20):
            section_title = f"# Chapter {i + 1}: {self.generate_title()}"
            paragraphs = [self._generate_paragraph(8) for _ in range(10)]
            sections.append(f"{section_title}\n\n" + "\n\n".join(paragraphs))
        content = "\n\n".join(sections)
        return self._maybe_inject_special_tokens(content), ".txt"

    def generate_code_file_content(self) -> Tuple[str, str, Dict[str, Any]]:
        """Generate code file content (~2-10 KB).

        Returns:
            Tuple of (content, extension, metadata).
        """
        is_python = self.rng.choice([True, False])
        template = PYTHON_TEMPLATE if is_python else JS_TEMPLATE

        class_name = f"{self._pick(ADJECTIVES).title()}{self._pick(NOUNS).title()}"
        module_name = f"{self._pick(NOUNS)}_{self._pick(VERBS)}"
        method1 = f"{self._pick(VERBS)}_item"
        method2 = f"get_{self._pick(NOUNS)}"
        method3 = f"get_{self._pick(NOUNS)}_config"
        function1 = f"count_{self._pick(NOUNS)}"
        function2 = f"format_{self._pick(NOUNS)}"

        content = template.format(
            module_name=module_name,
            description=self._generate_sentence(6),
            class_name=class_name,
            class_description=self._generate_sentence(5).lower().rstrip("."),
            method1=method1,
            method2=method2,
            method3=method3,
            function1=function1,
            function2=function2,
        )

        metadata = {
            "functions": [function1, function2],
            "classes": [class_name],
            "imports": ["typing"] if is_python else [],
        }

        extension = ".py" if is_python else ".js"
        return content, extension, metadata


@source(
    name="Stub",
    short_name="stub",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class=StubAuthConfig,
    config_class=StubConfig,
    labels=["Internal", "Testing"],
    supports_continuous=False,
    internal=True,
)
class StubSource(BaseSource):
    """Stub source connector for testing purposes.

    Generates deterministic test entities with configurable distribution and speed.
    No external API calls are made - all content is generated locally.
    """

    def __init__(self):
        """Initialize the stub source."""
        super().__init__()
        self.seed: int = 42
        self.entity_count: int = 10
        self.generation_delay_ms: int = 0
        self.fail_after: int = -1  # Raise after N entities (-1 = never)
        self.weights: Dict[str, int] = {}
        self.generator: Optional[ContentGenerator] = None
        self._temp_dir: Optional[str] = None

    @classmethod
    async def create(
        cls,
        credentials: Optional[StubAuthConfig] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "StubSource":
        """Create a new stub source instance.

        Args:
            credentials: Optional auth config (not used for stub).
            config: Source configuration parameters.

        Returns:
            Configured StubSource instance.
        """
        instance = cls()
        config = config or {}

        instance.seed = config.get("seed", 42)
        instance.entity_count = config.get("entity_count", 10)
        instance.generation_delay_ms = config.get("generation_delay_ms", 0)
        instance.fail_after = config.get("fail_after", -1)

        # Parse distribution weights
        instance.weights = {
            "small": config.get("small_entity_weight", 30),
            "medium": config.get("medium_entity_weight", 30),
            "large": config.get("large_entity_weight", 10),
            "small_file": config.get("small_file_weight", 15),
            "large_file": config.get("large_file_weight", 5),
            "code_file": config.get("code_file_weight", 10),
        }

        # Normalize weights
        total_weight = sum(instance.weights.values())
        if total_weight == 0:
            # Default to equal distribution if all weights are 0
            instance.weights = {k: 1 for k in instance.weights}
            total_weight = len(instance.weights)

        # Parse special token injection config
        inject_special_tokens = config.get("inject_special_tokens", False)
        custom_content_prefix = config.get("custom_content_prefix", None)

        instance.generator = ContentGenerator(
            seed=instance.seed,
            inject_special_tokens=inject_special_tokens,
            custom_content_prefix=custom_content_prefix,
        )

        return instance

    def _normalize_weights(self) -> List[Tuple[str, float]]:
        """Normalize weights to cumulative probabilities.

        Returns:
            List of (entity_type, cumulative_probability) tuples.
        """
        total = sum(self.weights.values())
        if total == 0:
            total = 1

        cumulative = []
        running_total = 0.0
        for entity_type, weight in self.weights.items():
            running_total += weight / total
            cumulative.append((entity_type, running_total))
        return cumulative

    def _select_entity_type(self, index: int) -> str:
        """Select entity type based on weighted distribution.

        Uses the entity index combined with seed for deterministic selection.

        Args:
            index: Entity index.

        Returns:
            Selected entity type string.
        """
        # Use index-based random for deterministic selection
        rng = random.Random(self.seed + index)
        roll = rng.random()

        cumulative = self._normalize_weights()
        for entity_type, threshold in cumulative:
            if roll <= threshold:
                return entity_type

        # Fallback to last type
        return cumulative[-1][0]

    async def _create_file(self, content: str, extension: str, name: str) -> str:
        """Create a temporary file with content.

        Args:
            content: File content.
            extension: File extension.
            name: Base filename.

        Returns:
            Path to the created file.
        """
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="stub_source_")

        filename = f"{name}{extension}"
        filepath = os.path.join(self._temp_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    async def _generate_small_entity(
        self, index: int, breadcrumbs: List[Breadcrumb]
    ) -> SmallStubEntity:
        """Generate a small stub entity.

        Args:
            index: Entity index.
            breadcrumbs: Parent breadcrumbs.

        Returns:
            SmallStubEntity instance.
        """
        gen = self.generator
        created = gen._generate_timestamp(index)
        modified = gen._generate_timestamp(index + 1)

        return SmallStubEntity(
            stub_id=f"small-{self.seed}-{index}",
            title=gen.generate_title(),
            content=gen.generate_small_content(),
            author=gen._pick(AUTHORS),
            tags=gen._pick_n(NOUNS, 3),
            created_at=created,
            modified_at=modified,
            sequence_number=index,
            breadcrumbs=breadcrumbs,
        )

    async def _generate_medium_entity(
        self, index: int, breadcrumbs: List[Breadcrumb]
    ) -> MediumStubEntity:
        """Generate a medium stub entity.

        Args:
            index: Entity index.
            breadcrumbs: Parent breadcrumbs.

        Returns:
            MediumStubEntity instance.
        """
        gen = self.generator
        created = gen._generate_timestamp(index)
        modified = gen._generate_timestamp(index + 2)
        due = gen._generate_timestamp(index + 30)

        return MediumStubEntity(
            stub_id=f"medium-{self.seed}-{index}",
            title=gen.generate_title(),
            description=gen.generate_medium_content(),
            status=gen._pick(STATUSES),
            priority=gen._pick(PRIORITIES),
            assignee=gen._pick(AUTHORS),
            tags=gen._pick_n(NOUNS, 4),
            notes=gen._generate_paragraph(2),
            created_at=created,
            modified_at=modified,
            due_date=due,
            sequence_number=index,
            breadcrumbs=breadcrumbs,
        )

    async def _generate_large_entity(
        self, index: int, breadcrumbs: List[Breadcrumb]
    ) -> LargeStubEntity:
        """Generate a large stub entity.

        Args:
            index: Entity index.
            breadcrumbs: Parent breadcrumbs.

        Returns:
            LargeStubEntity instance.
        """
        gen = self.generator
        created = gen._generate_timestamp(index)
        modified = gen._generate_timestamp(index + 5)
        published = gen._generate_timestamp(index + 3)
        content = gen.generate_large_content()

        return LargeStubEntity(
            stub_id=f"large-{self.seed}-{index}",
            title=gen.generate_title(),
            summary=gen._generate_paragraph(3),
            content=content,
            author=gen._pick(AUTHORS),
            category=gen._pick(CATEGORIES),
            tags=gen._pick_n(NOUNS, 5),
            sections=[f"Section {i + 1}" for i in range(5)],
            references=[f"Reference {i + 1}" for i in range(3)],
            created_at=created,
            modified_at=modified,
            published_at=published,
            word_count=len(content.split()),
            sequence_number=index,
            breadcrumbs=breadcrumbs,
        )

    async def _generate_small_file_entity(
        self, index: int, breadcrumbs: List[Breadcrumb]
    ) -> SmallStubFileEntity:
        """Generate a small stub file entity.

        Args:
            index: Entity index.
            breadcrumbs: Parent breadcrumbs.

        Returns:
            SmallStubFileEntity instance.
        """
        gen = self.generator
        content, extension = gen.generate_small_file_content()
        filename = f"small_file_{self.seed}_{index}"
        filepath = await self._create_file(content, extension, filename)
        created = gen._generate_timestamp(index)
        modified = gen._generate_timestamp(index + 1)

        return SmallStubFileEntity(
            stub_id=f"small-file-{self.seed}-{index}",
            file_name=f"{filename}{extension}",
            description=gen._generate_sentence(8),
            file_extension=extension,
            created_at=created,
            modified_at=modified,
            sequence_number=index,
            breadcrumbs=breadcrumbs,
            # FileEntity fields
            url=f"stub://file/small/{filename}{extension}",
            size=len(content.encode("utf-8")),
            file_type="text",
            mime_type="text/plain",
            local_path=filepath,
        )

    async def _generate_large_file_entity(
        self, index: int, breadcrumbs: List[Breadcrumb]
    ) -> LargeStubFileEntity:
        """Generate a large stub file entity.

        Args:
            index: Entity index.
            breadcrumbs: Parent breadcrumbs.

        Returns:
            LargeStubFileEntity instance.
        """
        gen = self.generator
        content, extension = gen.generate_large_file_content()
        filename = f"large_file_{self.seed}_{index}"
        filepath = await self._create_file(content, extension, filename)
        created = gen._generate_timestamp(index)
        modified = gen._generate_timestamp(index + 3)

        return LargeStubFileEntity(
            stub_id=f"large-file-{self.seed}-{index}",
            file_name=f"{filename}{extension}",
            description=gen._generate_sentence(10),
            file_extension=extension,
            summary=gen._generate_paragraph(3),
            author=gen._pick(AUTHORS),
            category=gen._pick(CATEGORIES),
            page_count=len(content) // 3000 + 1,
            created_at=created,
            modified_at=modified,
            sequence_number=index,
            breadcrumbs=breadcrumbs,
            # FileEntity fields
            url=f"stub://file/large/{filename}{extension}",
            size=len(content.encode("utf-8")),
            file_type="document",
            mime_type="text/plain",
            local_path=filepath,
        )

    async def _generate_code_file_entity(
        self, index: int, breadcrumbs: List[Breadcrumb]
    ) -> CodeStubFileEntity:
        """Generate a code stub file entity.

        Args:
            index: Entity index.
            breadcrumbs: Parent breadcrumbs.

        Returns:
            CodeStubFileEntity instance.
        """
        gen = self.generator
        content, extension, metadata = gen.generate_code_file_content()
        filename = f"code_file_{self.seed}_{index}"
        filepath = await self._create_file(content, extension, filename)
        created = gen._generate_timestamp(index)
        modified = gen._generate_timestamp(index + 2)

        language = "python" if extension == ".py" else "javascript"

        return CodeStubFileEntity(
            stub_id=f"code-file-{self.seed}-{index}",
            file_name=f"{filename}{extension}",
            description=gen._generate_sentence(8),
            functions=metadata["functions"],
            classes=metadata["classes"],
            imports=metadata["imports"],
            created_at=created,
            modified_at=modified,
            sequence_number=index,
            breadcrumbs=breadcrumbs,
            # FileEntity fields
            url=f"stub://file/code/{filename}{extension}",
            size=len(content.encode("utf-8")),
            file_type="code",
            mime_type=f"text/{'x-python' if extension == '.py' else 'javascript'}",
            local_path=filepath,
            # CodeFileEntity fields
            repo_name="stub-repository",
            path_in_repo=f"src/{filename}{extension}",
            repo_owner="stub-owner",
            language=language,
            commit_id=f"stub-commit-{self.seed}-{index}",
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all stub entities.

        Yields:
            BaseEntity instances according to configured distribution.
        """
        self.logger.info(
            f"Starting stub entity generation: count={self.entity_count}, "
            f"seed={self.seed}, delay={self.generation_delay_ms}ms, "
            f"fail_after={self.fail_after}"
        )
        self.logger.info(f"Entity distribution weights: {self.weights}")

        # First yield the container entity
        container_id = f"stub-container-{self.seed}"
        container = StubContainerEntity(
            container_id=container_id,
            container_name=f"Stub Container (seed={self.seed})",
            description=f"Test container with {self.entity_count} entities",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            seed=self.seed,
            entity_count=self.entity_count,
            breadcrumbs=[],
        )
        yield container
        self.logger.info(f"Yielded container entity: {container_id}")

        # Create breadcrumb for child entities
        container_breadcrumb = Breadcrumb(
            entity_id=container_id,
            name=container.container_name,
            entity_type="StubContainerEntity",
        )
        breadcrumbs = [container_breadcrumb]

        # Track entity type counts for logging
        type_counts: Dict[str, int] = {
            "small": 0,
            "medium": 0,
            "large": 0,
            "small_file": 0,
            "large_file": 0,
            "code_file": 0,
        }

        # Generate entities according to distribution (container counts as 1)
        for i in range(self.entity_count - 1):
            entity_type = self._select_entity_type(i)
            type_counts[entity_type] += 1

            # Generate entity based on type using dispatch map
            generators = {
                "small": self._generate_small_entity,
                "medium": self._generate_medium_entity,
                "large": self._generate_large_entity,
                "small_file": self._generate_small_file_entity,
                "large_file": self._generate_large_file_entity,
                "code_file": self._generate_code_file_entity,
            }
            generator = generators.get(entity_type, self._generate_small_entity)
            entity = await generator(i, breadcrumbs)

            yield entity

            # Simulate failure after N entities if configured
            if self.fail_after >= 0 and (i + 1) >= self.fail_after:
                raise RuntimeError(
                    f"Stub source simulated failure after {i + 1} entities "
                    f"(fail_after={self.fail_after})"
                )

            # Apply generation delay if configured
            if self.generation_delay_ms > 0:
                await asyncio.sleep(self.generation_delay_ms / 1000.0)

            # Log progress every 100 entities
            if (i + 1) % 100 == 0:
                self.logger.info(f"Generated {i + 1}/{self.entity_count} entities")

        self.logger.info(f"Completed stub entity generation. Distribution: {type_counts}")

    async def validate(self) -> bool:
        """Validate the stub source configuration.

        Always returns True since stub source doesn't require external validation.

        Returns:
            True (stub source is always valid).
        """
        return True
