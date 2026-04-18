"""Secret backends -- pluggable encrypted credential storage.

Preserves the Protocol+strategies+factory+config-discriminator
pattern used by the rest of SynthOrg's pluggable subsystems.  Each
concrete backend (env_var, encrypted_sqlite, encrypted_postgres)
owns its own connection / pool so secret material stays isolated
from the main application data plane.
"""

from synthorg.persistence.secret_backends.protocol import SecretBackend

__all__ = ["SecretBackend"]
