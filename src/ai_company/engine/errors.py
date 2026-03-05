"""Engine-layer error hierarchy."""


class EngineError(Exception):
    """Base exception for all engine-layer errors."""


class PromptBuildError(EngineError):
    """Raised when system prompt construction fails."""
