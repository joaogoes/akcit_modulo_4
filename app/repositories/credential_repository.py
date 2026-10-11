"""Persistência dos tokens de acesso por provedor, sempre cifrados (RF-22)."""

from datetime import UTC, datetime

from app.models import Provider
from app.protection import ProtectionError, SecretProtector
from app.repositories.database import Database


class CredentialRepository:
    """Guarda um token por provedor; o valor só existe em claro na memória, nunca no banco."""

    def __init__(self, db: Database, protector: SecretProtector | None) -> None:
        self._db = db
        self._protector = protector

    @property
    def secure_storage(self) -> bool:
        """Se há como cifrar os tokens neste sistema."""
        return self._protector is not None

    def save(self, provider: Provider, token: str) -> None:
        """Cifra e grava o token, substituindo o anterior do mesmo provedor."""
        protector = self._require_protector()
        protected = protector.protect(token.encode("utf-8"))
        self._db.execute(
            "INSERT INTO credentials (provider, secret, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(provider) DO UPDATE SET secret = excluded.secret, updated_at = excluded.updated_at",
            (provider.value, protected, datetime.now(UTC).isoformat()),
        )

    def get(self, provider: Provider) -> str | None:
        """Token em claro, ou `None` se não houver; `ProtectionError` se não puder ser decifrado."""
        row = self._db.fetch_one("SELECT secret FROM credentials WHERE provider = ?", (provider.value,))
        if row is None:
            return None
        try:
            return self._require_protector().unprotect(bytes(row["secret"])).decode("utf-8")
        except ProtectionError as exc:
            raise ProtectionError(
                f"Não foi possível ler o token salvo para o {provider.label}; salve-o novamente "
                "(ele só pode ser lido pelo mesmo usuário do Windows, na máquina em que foi salvo)."
            ) from exc

    def updated_at(self, provider: Provider) -> datetime | None:
        """Quando o token foi salvo, ou `None` se não houver."""
        row = self._db.fetch_one("SELECT updated_at FROM credentials WHERE provider = ?", (provider.value,))
        return datetime.fromisoformat(row["updated_at"]) if row else None

    def delete(self, provider: Provider) -> bool:
        """Remove o token; devolve se existia."""
        return self._db.execute("DELETE FROM credentials WHERE provider = ?", (provider.value,)).rowcount > 0

    def _require_protector(self) -> SecretProtector:
        if self._protector is None:
            raise ProtectionError(
                "O armazenamento protegido de tokens só existe no Windows; "
                "neste sistema use as variáveis de ambiente GITHUB_TOKEN e AZURE_DEVOPS_TOKEN."
            )
        return self._protector
