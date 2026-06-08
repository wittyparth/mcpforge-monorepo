"""Credential management business logic — encrypt, store, test, rotate.

F1 / OpenAPI Ingestion feature.  Uses ``app.core.encryption`` for at-rest
Fernet encryption of all credential values.  No plaintext values are logged
or returned from any method in this module.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.credential import Credential
from app.repositories.credential_repo import CredentialRepository
from app.repositories.mcp_server_repo import MCPServerRepository
from app.schemas.credential import CredentialTestResponse

logger = get_logger(__name__)


class CredentialService:
    """Service-layer logic for credential CRUD and connectivity testing.

    All methods verify server ownership before mutating or reading data.
    Encrypted values are never exposed through return types or log output.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.cred_repo = CredentialRepository(session)
        self.server_repo = MCPServerRepository(session)

    async def add_credential(
        self,
        server_id: UUID,
        user_id: UUID,
        env_var_name: str,
        value: str,
        auth_scheme: str = "bearer",
        auth_header_name: str | None = None,
    ) -> Credential:
        """Create and store an encrypted credential for a server.

        Steps
        -----
        1. Verify the server exists and is owned by ``user_id``.
        2. Reject duplicate ``env_var_name`` for the same server (ConflictError).
        3. Encrypt ``value`` via ``app.core.encryption.encrypt``.
        4. Persist via ``CredentialRepository.create``.
        5. Emit an audit log event (no plaintext, no ciphertext).

        Raises
        ------
        NotFoundError
            The ``server_id`` does not exist.
        ForbiddenError
            The ``user_id`` does not own the server.
        ConflictError
            A credential with ``env_var_name`` already exists for this server.
        """
        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise NotFoundError("Server not found")
        if server.user_id != user_id:
            raise ForbiddenError("You do not own this server")

        existing = await self.cred_repo.get_by_server_and_env(server_id, env_var_name)
        if existing:
            raise ConflictError(
                f"Credential '{env_var_name}' already exists for this server"
            )

        encrypted_value = encrypt(value)

        credential = await self.cred_repo.create(
            server_id=server_id,
            user_id=user_id,
            env_var_name=env_var_name,
            encrypted_value=encrypted_value,
            auth_scheme=auth_scheme,
            auth_header_name=auth_header_name,
            encryption_key_id="default",
        )

        logger.info(
            "credential_added",
            server_id=str(server_id),
            env_var_name=env_var_name,
            user_id=str(user_id),
        )

        return credential

    async def list_credentials(
        self,
        server_id: UUID,
        user_id: UUID,
    ) -> list[Credential]:
        """Return all credentials for the given server (newest first).

        Ownership is verified before returning results.
        """
        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise NotFoundError("Server not found")
        if server.user_id != user_id:
            raise ForbiddenError("You do not own this server")

        return await self.cred_repo.get_by_server(server_id)

    async def delete_credential(
        self,
        server_id: UUID,
        env_var_name: str,
        user_id: UUID,
    ) -> None:
        """Delete a single credential identified by ``env_var_name``.

        Raises
        ------
        NotFoundError
            The server or the credential does not exist.
        ForbiddenError
            The ``user_id`` does not own the server.
        """
        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise NotFoundError("Server not found")
        if server.user_id != user_id:
            raise ForbiddenError("You do not own this server")

        cred = await self.cred_repo.get_by_server_and_env(server_id, env_var_name)
        if not cred:
            raise NotFoundError(
                f"Credential '{env_var_name}' not found for this server"
            )

        await self.cred_repo.delete(cred)

        logger.info(
            "credential_deleted",
            server_id=str(server_id),
            env_var_name=env_var_name,
            user_id=str(user_id),
        )

    async def test_credential(
        self,
        server_id: UUID,
        user_id: UUID,
        env_var_name: str,
        test_value: str,
    ) -> CredentialTestResponse:
        """Send a test request to the server's ``base_url`` using ``test_value``.

        The ``test_value`` is plaintext provided by the caller.  It is **never**
        persisted or logged.  If a stored credential exists for
        ``env_var_name``, its ``auth_scheme`` and ``auth_header_name`` are
        reused; otherwise the server-level auth config is used.

        A ``HEAD`` / ``GET`` request is sent with a **5-second timeout**.  The
        response is considered successful if the status code is ``< 400``.

        Returns
        -------
        CredentialTestResponse
            ``success``, ``status_code``, ``latency_ms``, and a sanitised
            ``error`` message if applicable.
        """
        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise NotFoundError("Server not found")
        if server.user_id != user_id:
            raise ForbiddenError("You do not own this server")

        # Determine auth scheme and header name — prefer stored credential,
        # fall back to server-level config.
        stored_cred = await self.cred_repo.get_by_server_and_env(
            server_id, env_var_name
        )
        if stored_cred:
            scheme = stored_cred.auth_scheme
            header_name = stored_cred.auth_header_name
        else:
            scheme = server.auth_scheme
            header_name = server.auth_header_name

        headers = self._build_auth_headers(scheme, test_value, header_name)
        test_url = server.base_url.rstrip("/")

        start = datetime.now(UTC)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(test_url, headers=headers)

            elapsed_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
            success = response.status_code < 400
            error: str | None = None if success else f"HTTP {response.status_code}"

            logger.info(
                "credential_test",
                server_id=str(server_id),
                env_var_name=env_var_name,
                success=success,
                status_code=response.status_code,
                latency_ms=elapsed_ms,
            )

            return CredentialTestResponse(
                success=success,
                status_code=response.status_code,
                latency_ms=elapsed_ms,
                error=error,
            )

        except httpx.TimeoutException:
            elapsed_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
            logger.warning(
                "credential_test_timeout",
                server_id=str(server_id),
                env_var_name=env_var_name,
                latency_ms=elapsed_ms,
            )
            return CredentialTestResponse(
                success=False,
                status_code=None,
                latency_ms=elapsed_ms,
                error="Connection timed out (5s)",
            )

        except httpx.RequestError as e:
            elapsed_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
            logger.warning(
                "credential_test_network_error",
                server_id=str(server_id),
                env_var_name=env_var_name,
                error_type=type(e).__name__,
                latency_ms=elapsed_ms,
            )
            return CredentialTestResponse(
                success=False,
                status_code=None,
                latency_ms=elapsed_ms,
                error=f"Network error: {type(e).__name__}",
            )

    @staticmethod
    async def decrypt_or_none(server_id: UUID) -> str | None:  # noqa: ARG004
        """Retrieve and decrypt a credential for the given server, or return None.

        This is a convenience method for the MCP gateway context where a
        full ``CredentialService`` instance (with a DB session) may not
        be available.  For now it always returns ``None``; the real
        implementation will look up the server's credentials from the
        database and decrypt the first matching value.

        Args:
            server_id: The UUID of the target MCP server.

        Returns:
            The decrypted credential value, or ``None`` if no matching
            credential exists.
        """
        # TODO(phase-2): Implement real credential lookup and decryption.
        return None

    def _build_auth_headers(
        self,
        scheme: str,
        value: str,
        header_name: str | None,
    ) -> dict[str, str]:
        """Construct HTTP authentication headers for the given scheme.

        Mapping
        -------
        * ``api_key`` → ``{header_name or "X-API-Key": value}``
        * ``bearer`` / ``oauth2`` → ``{"Authorization": "Bearer ..."}``
        * ``basic`` → ``{"Authorization": "Basic ..."}`` (base64-encoded)
        * ``header`` → ``{header_name or "X-Custom-Header": value}``
        * anything else → ``{}`` (no auth)
        """
        if scheme == "api_key":
            return {header_name or "X-API-Key": value}
        if scheme in ("bearer", "oauth2"):
            return {"Authorization": f"Bearer {value}"}
        if scheme == "basic":
            encoded = base64.b64encode(value.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        if scheme == "header":
            return {header_name or "X-Custom-Header": value}
        return {}
