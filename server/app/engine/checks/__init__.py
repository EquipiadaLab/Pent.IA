"""Catalogo FECHADO de lances. Mapeado a WSTG e OWASP Top 10:2025.

Adicionar um lance = acrescentar um CheckSpec aqui. O agente (nem o LLM)
nunca cria requisicoes fora deste catalogo.
"""

from app.engine.checks import active, cookies, headers, transport
from app.engine.checks.base import CheckSpec
from app.models import Phase, Profile, Severity

P = Phase
H, MED, L = Severity.HIGH, Severity.MEDIUM, Severity.LOW
PASSIVE, ACTIVE = Profile.PASSIVE, Profile.ACTIVE_LIGHT

CATALOG: list[CheckSpec] = [
    # --- Abertura (recon) ---
    CheckSpec("TLS-001", "HTTPS em uso", P.OPENING, PASSIVE, H, "WSTG-CRYP-01", "A04:2025", transport.https_in_use),
    CheckSpec("TLS-002", "Certificado TLS valido", P.OPENING, PASSIVE, H, "WSTG-CRYP-01", "A04:2025", transport.tls_certificate),
    CheckSpec("REDIR-001", "Redirecionamento HTTP para HTTPS", P.OPENING, PASSIVE, MED, "WSTG-CRYP-03", "A04:2025", transport.http_to_https_redirect),
    CheckSpec("INFO-001", "Vazamento de versao", P.OPENING, PASSIVE, L, "WSTG-INFO-02", "A02:2025", headers.version_leak),
    # --- Meio-jogo (configuracao) ---
    CheckSpec("HSTS-001", "HSTS", P.MIDDLEGAME, PASSIVE, MED, "WSTG-CONF-07", "A02:2025", headers.hsts),
    CheckSpec("CSP-001", "Content-Security-Policy", P.MIDDLEGAME, PASSIVE, MED, "WSTG-CONF-12", "A02:2025", headers.csp),
    CheckSpec("CLICK-001", "Protecao contra clickjacking", P.MIDDLEGAME, PASSIVE, MED, "WSTG-CLNT-09", "A02:2025", headers.clickjacking),
    CheckSpec("HDR-001", "Cabecalhos complementares", P.MIDDLEGAME, PASSIVE, L, "WSTG-CONF-14", "A02:2025", headers.misc_headers),
    CheckSpec("COOKIE-001", "Flags de cookies", P.MIDDLEGAME, PASSIVE, MED, "WSTG-SESS-02", "A07:2025", cookies.cookie_flags),
    CheckSpec("CORS-001", "CORS com origem refletida", P.MIDDLEGAME, ACTIVE, H, "WSTG-CLNT-07", "A01:2025", active.cors),
    CheckSpec("METHOD-001", "Metodos HTTP permitidos", P.MIDDLEGAME, ACTIVE, L, "WSTG-CONF-06", "A02:2025", active.http_methods),
    # --- Final (ativo leve, com aprovacao humana) ---
    CheckSpec("FILE-001", "Repositorio .git exposto", P.ENDGAME, ACTIVE, H, "WSTG-CONF-04", "A02:2025", active.git_exposed, needs_approval=True),
    CheckSpec("FILE-002", "Arquivo .env exposto", P.ENDGAME, ACTIVE, H, "WSTG-CONF-04", "A02:2025", active.env_exposed, needs_approval=True),
    CheckSpec("ERR-001", "Pagina de erro com stack trace", P.ENDGAME, ACTIVE, MED, "WSTG-ERRH-01", "A10:2025", active.error_page, needs_approval=True),
]
