from typing import Protocol


class TranslationError(RuntimeError):
    """Raised when a translation provider cannot complete a request."""


class MonthlyTranslationLimitError(TranslationError):
    """Raised before sending a request that exceeds the local monthly limit."""


class TranslationProvider(Protocol):
    """Interface shared by translation providers."""

    name: str

    @property
    def is_available(self) -> bool: ...

    def is_language_supported(self, language_code: str) -> bool: ...

    def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str,
    ) -> str: ...

    def test_connection(self) -> dict[str, object]: ...
