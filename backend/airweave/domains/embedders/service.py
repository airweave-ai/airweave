"""EmbedderService — factory for configured embedder instances.

Reads embedding config from the domain YAML file and caches embedder instances
since config is fixed per deployment.
"""

from airweave.core.config import Settings
from airweave.domains.embedders.config import (
    load_embedding_config,
    provider_for_model,
    validate_api_key,
    validate_embedding_config,
)
from airweave.domains.embedders.dense.registry import (
    get_model_spec,
    validate_vector_size,
)
from airweave.domains.embedders.exceptions import UnsupportedProviderError
from airweave.domains.embedders.protocols import (
    DenseEmbedderProtocol,
    SparseEmbedderProtocol,
)
from airweave.domains.embedders.sparse.registry import (
    get_model_spec as get_sparse_model_spec,
)


class EmbedderService:
    """Deployment-level embedder factory.

    Reads embedding config from embedding_config.yml at construction time.
    Callers get configured embedders via ``get_dense_embedder()`` and
    ``get_sparse_embedder()`` — no arguments needed.

    Embedder instances are cached because the config is fixed for the lifetime
    of the service.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        _model_name: str | None = None,
        _dimensions: int | None = None,
        _provider: str | None = None,
    ) -> None:
        """Initialize with deployment settings.

        When the private keyword args are omitted, config is read from the
        domain YAML file.  ``for_model()`` passes them explicitly to skip
        the YAML and use a caller-specified model instead.
        """
        if _model_name is not None:
            # Explicit model — skip YAML, caller already validated
            self._config = None
            self._settings = settings
            self._vector_size = _dimensions
            self._model_name = _model_name
            self._provider = _provider
        else:
            # Normal path — read from embedding_config.yml
            self._config = load_embedding_config()
            validate_embedding_config(self._config, settings)
            self._settings = settings
            self._vector_size = self._config.dimensions
            self._model_name = self._config.model
            self._provider = self._config.provider

        self._dense_embedder: DenseEmbedderProtocol | None = None
        self._sparse_embedder: SparseEmbedderProtocol | None = None

    @classmethod
    def for_model(cls, model: str, dimensions: int, settings: Settings) -> "EmbedderService":
        """Create an embedder service for a specific model+dimensions.

        Used at query time when the collection's stored model differs from
        the current global config.

        Args:
            model: Model name (e.g. "text-embedding-3-small").
            dimensions: Embedding dimensions.
            settings: Application settings (for API key validation).

        Returns:
            Configured EmbedderService instance.
        """
        provider = provider_for_model(model)
        spec = get_model_spec(provider, dimensions, model_name=model)
        validate_vector_size(spec, dimensions)
        validate_api_key(provider, settings)

        return cls(
            settings,
            _model_name=model,
            _dimensions=dimensions,
            _provider=provider,
        )

    @property
    def vector_size(self) -> int:
        """Return the embedding dimensions."""
        return self._vector_size

    @property
    def model_name(self) -> str:
        """Return the embedding model name."""
        return self._model_name

    def get_dense_embedder(self) -> DenseEmbedderProtocol:
        """Return a dense embedder for the configured model.

        The instance is cached — subsequent calls return the same embedder.
        """
        if self._dense_embedder is None:
            self._dense_embedder = self._create_dense_embedder()
        return self._dense_embedder

    def get_sparse_embedder(self) -> SparseEmbedderProtocol:
        """Return a sparse BM25 embedder (always FastEmbed).

        The instance is cached — the BM25 model is only loaded once.
        """
        if self._sparse_embedder is None:
            self._sparse_embedder = self._create_sparse_embedder()
        return self._sparse_embedder

    def _create_dense_embedder(self) -> DenseEmbedderProtocol:
        """Create a new dense embedder instance."""
        model_spec = get_model_spec(self._provider, self._vector_size, model_name=self._model_name)
        validate_vector_size(model_spec, self._vector_size)

        if self._provider == "openai":
            from airweave.domains.embedders.dense.openai import OpenAIDenseEmbedder

            return OpenAIDenseEmbedder(
                model_spec=model_spec,
                target_dimensions=self._vector_size,
                api_key=self._settings.OPENAI_API_KEY,
            )

        if self._provider == "mistral":
            from airweave.domains.embedders.dense.mistral import MistralDenseEmbedder

            return MistralDenseEmbedder(
                model_spec=model_spec,
                target_dimensions=self._vector_size,
                api_key=self._settings.MISTRAL_API_KEY,
            )

        if self._provider == "local":
            from airweave.domains.embedders.dense.local import LocalDenseEmbedder

            return LocalDenseEmbedder(
                model_spec=model_spec,
                target_dimensions=self._vector_size,
                inference_url=self._settings.TEXT2VEC_INFERENCE_URL,
            )

        raise UnsupportedProviderError(f"Unknown embedding provider: {self._provider}")

    def _create_sparse_embedder(self) -> SparseEmbedderProtocol:
        """Create a new sparse embedder instance."""
        from airweave.domains.embedders.sparse.fastembed import FastEmbedSparseEmbedder

        model_spec = get_sparse_model_spec("fastembed")
        return FastEmbedSparseEmbedder(model_spec=model_spec)
