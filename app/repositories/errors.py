"""Erros de persistência."""


class NotFoundError(Exception):
    """Registro inexistente."""


class DuplicateRepositoryError(Exception):
    """Repositório já cadastrado."""
