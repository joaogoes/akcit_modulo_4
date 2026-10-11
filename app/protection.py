"""Proteção de segredos em repouso.

No Windows usa o DPAPI (`CryptProtectData`): o segredo só pode ser decifrado pelo mesmo
usuário do Windows, na mesma máquina. Não há dependências externas (só `ctypes`).
"""

import ctypes
import sys
from typing import Protocol


class ProtectionError(Exception):
    """Falha ao proteger ou ao recuperar um segredo."""


class SecretProtector(Protocol):
    """Cifra e decifra segredos."""

    def protect(self, plain: bytes) -> bytes: ...

    def unprotect(self, protected: bytes) -> bytes: ...


class _Blob(ctypes.Structure):
    """`DATA_BLOB` do Windows."""

    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.c_void_p)]


_UI_FORBIDDEN = 0x01  # nunca abrir janelas
_ENTROPY = b"dashboard-atividades/tokens"  # amarra o segredo a esta aplicação


class DpapiProtector:
    """Implementação com o DPAPI do Windows (escopo do usuário atual)."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise ProtectionError("O DPAPI só está disponível no Windows.")
        self._crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        pointer, void = ctypes.POINTER(_Blob), ctypes.c_void_p
        for function in (self._crypt32.CryptProtectData, self._crypt32.CryptUnprotectData):
            function.argtypes = [pointer, void, pointer, void, void, ctypes.c_uint32, pointer]
            function.restype = ctypes.c_int
        self._kernel32.LocalFree.argtypes = [void]
        self._kernel32.LocalFree.restype = void

    def protect(self, plain: bytes) -> bytes:
        return self._transform(self._crypt32.CryptProtectData, plain, "Não foi possível proteger o token.")

    def unprotect(self, protected: bytes) -> bytes:
        return self._transform(
            self._crypt32.CryptUnprotectData,
            protected,
            "Não foi possível decifrar o token salvo.",
        )

    def _transform(self, function, data: bytes, message: str) -> bytes:
        source = ctypes.create_string_buffer(data, len(data))
        entropy = ctypes.create_string_buffer(_ENTROPY, len(_ENTROPY))
        incoming = _Blob(len(data), ctypes.addressof(source))
        extra = _Blob(len(_ENTROPY), ctypes.addressof(entropy))
        outgoing = _Blob()
        ok = function(
            ctypes.byref(incoming), None, ctypes.byref(extra), None, None, _UI_FORBIDDEN, ctypes.byref(outgoing)
        )
        if not ok:
            raise ProtectionError(f"{message} ({ctypes.WinError(ctypes.get_last_error()).strerror})")
        try:
            return ctypes.string_at(outgoing.pbData, outgoing.cbData)
        finally:
            self._kernel32.LocalFree(outgoing.pbData)


def default_protector() -> SecretProtector | None:
    """O DPAPI no Windows; `None` nos demais sistemas (não há armazenamento protegido)."""
    return DpapiProtector() if sys.platform == "win32" else None
