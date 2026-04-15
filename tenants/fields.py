"""
Encrypted model fields using Fernet symmetric encryption.

Values are transparently encrypted before writing to the database and
decrypted when read.  The encryption key is derived from the Django
``FIELD_ENCRYPTION_KEY`` setting (a URL-safe base64-encoded 32-byte key).

Generate a key once with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Then set it in your ``.env``::

    FIELD_ENCRYPTION_KEY=<generated-key>
"""

import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

_fernet_instance = None


def _get_fernet():
    """Return a cached Fernet instance (created on first call)."""
    global _fernet_instance
    if _fernet_instance is None:
        key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
        if not key:
            raise RuntimeError(
                'FIELD_ENCRYPTION_KEY is not set.  Generate one with:\n'
                '  python -c "from cryptography.fernet import Fernet; '
                "print(Fernet.generate_key().decode())\""
            )
        if isinstance(key, str):
            key = key.encode()
        _fernet_instance = Fernet(key)
    return _fernet_instance


# Prefix stored in the DB column so we can distinguish encrypted values
# from legacy plaintext values during the migration window.
_ENC_PREFIX = 'enc::'


class EncryptedCharField(models.CharField):
    """CharField that encrypts its value at rest using Fernet.

    * ``from_db_value`` decrypts when reading from the database.
    * ``get_prep_value`` encrypts when writing to the database.
    * Legacy plaintext values (without the ``enc::`` prefix) are returned
      as-is so existing rows keep working until they are re-saved.
    """

    def get_prep_value(self, value):
        """Encrypt before storing."""
        value = super().get_prep_value(value)
        if value is None or value == '':
            return value
        # Already encrypted (e.g. bulk update that passes raw DB value)
        if isinstance(value, str) and value.startswith(_ENC_PREFIX):
            return value
        token = _get_fernet().encrypt(value.encode()).decode()
        return f'{_ENC_PREFIX}{token}'

    def from_db_value(self, value, expression, connection):
        """Decrypt when reading from the database."""
        if value is None or value == '':
            return value
        if isinstance(value, str) and value.startswith(_ENC_PREFIX):
            token = value[len(_ENC_PREFIX):]
            try:
                return _get_fernet().decrypt(token.encode()).decode()
            except InvalidToken:
                logger.error('Failed to decrypt field – wrong FIELD_ENCRYPTION_KEY?')
                return ''
        # Legacy plaintext value – return as-is
        return value

    def get_internal_type(self):
        # Fernet output is ~2.4x the input length; use TextField storage
        # if the column needs more room.  For CharField(max_length=255) the
        # encrypted output fits comfortably in 512 chars.
        return 'CharField'
