"""Catalogo FECHADO de lances. Mapeado a WSTG e OWASP Top 10:2025.

Adicionar um lance = acrescentar um CheckSpec aqui. O agente (e a IA) so
escolhe lances deste catalogo: nunca cria requisicoes novas.
"""

from app.engine.checks import active, cookies, headers, transport
from app.engine.checks.base import CheckSpec
from app.models import Phase, Profile, Severity

P = Phase
H, MED, L = Severity.HIGH, Severity.MEDIUM, Severity.LOW
PASSIVE, ACTIVE = Profile.PASSIVE, Profile.ACTIVE_LIGHT


def _spec(test_id, title, phase, profile, sev, wstg, owasp, fn, *, hyp, exp, imp, approval=False):
    return CheckSpec(test_id, title, phase, profile, sev, wstg, owasp, fn, needs_approval=approval,
                     hypothesis=hyp, expected=exp, impact=imp)


CATALOG: list[CheckSpec] = [
    # --- Abertura (recon) ---
    _spec("TLS-001", "Uso de HTTPS", P.OPENING, PASSIVE, H, "WSTG-CRYP-01", "A04:2025", transport.https_in_use,
          hyp="O site pode estar sendo servido sem criptografia.",
          exp="A origem autorizada usa https://.",
          imp="Sem HTTPS, qualquer pessoa na mesma rede le ou altera senhas, cookies e dados em transito."),
    CheckSpec("TLS-002", "Validade do certificado TLS", P.OPENING, PASSIVE, H, "WSTG-CRYP-01", "A04:2025",
              transport.tls_certificate,
              hypothesis="O certificado pode estar vencido, autoassinado ou emitido para outro dominio.",
              expected="O certificado e validado pela cadeia de confianca do sistema.",
              impact="Certificado invalido acostuma o usuario a ignorar alertas e permite interceptacao (man-in-the-middle)."),
    _spec("REDIR-001", "Redirecionamento de HTTP para HTTPS", P.OPENING, PASSIVE, MED, "WSTG-CRYP-03", "A04:2025",
          transport.http_to_https_redirect,
          hyp="A versao http:// pode responder sem levar o usuario para HTTPS.",
          exp="http:// responde 301/308 apontando para https://.",
          imp="Quem digita o endereco sem https:// navega desprotegido e pode ser interceptado."),
    _spec("INFO-001", "Exposicao de versao do servidor", P.OPENING, PASSIVE, L, "WSTG-INFO-02", "A02:2025",
          headers.version_leak,
          hyp="Os cabecalhos podem revelar o software e a versao do servidor.",
          exp="Server sem numero de versao e sem X-Powered-By.",
          imp="Versao exposta ajuda um atacante a escolher exploits conhecidos para aquela versao."),
    # --- Meio-jogo (configuracao) ---
    _spec("HSTS-001", "Politica HSTS", P.MIDDLEGAME, PASSIVE, MED, "WSTG-CONF-07", "A02:2025", headers.hsts,
          hyp="O navegador pode nao ser obrigado a usar HTTPS nas proximas visitas.",
          exp="Strict-Transport-Security com max-age >= 6 meses.",
          imp="Sem HSTS, um atacante pode rebaixar a conexao para HTTP (ataque de downgrade)."),
    _spec("CSP-001", "Politica de seguranca de conteudo (CSP)", P.MIDDLEGAME, PASSIVE, MED, "WSTG-CONF-12",
          "A02:2025", headers.csp,
          hyp="O site pode nao limitar de onde scripts podem ser carregados.",
          exp="Content-Security-Policy aplicada, sem 'unsafe-inline', 'unsafe-eval' ou '*'.",
          imp="Sem CSP efetiva, uma falha de XSS vira roubo de sessao e de dados com facilidade."),
    _spec("CLICK-001", "Protecao contra clickjacking", P.MIDDLEGAME, PASSIVE, MED, "WSTG-CLNT-09", "A02:2025",
          headers.clickjacking,
          hyp="A pagina pode ser embutida em um iframe de outro site.",
          exp="CSP frame-ancestors ou X-Frame-Options DENY/SAMEORIGIN.",
          imp="Um site falso pode sobrepor a pagina e induzir o usuario a clicar em acoes que ele nao pretendia."),
    _spec("HDR-001", "Cabecalhos de seguranca complementares", P.MIDDLEGAME, PASSIVE, L, "WSTG-CONF-14",
          "A02:2025", headers.misc_headers,
          hyp="Podem faltar cabecalhos basicos de endurecimento.",
          exp="nosniff, Referrer-Policy e Permissions-Policy presentes; X-XSS-Protection ausente ou 0.",
          imp="Aumenta a superficie para ataques de tipo de conteudo e vazamento de URLs para terceiros."),
    _spec("COOKIE-001", "Flags de cookies", P.MIDDLEGAME, PASSIVE, MED, "WSTG-SESS-02", "A07:2025",
          cookies.cookie_flags,
          hyp="Cookies, inclusive de sessao, podem estar sem Secure, HttpOnly ou SameSite.",
          exp="Cookies com Secure, HttpOnly e SameSite=Lax/Strict.",
          imp="Cookie de sessao desprotegido pode ser roubado por script ou enviado sem criptografia (sequestro de conta)."),
    _spec("CORS-001", "Politica de CORS", P.MIDDLEGAME, ACTIVE, H, "WSTG-CLNT-07", "A01:2025", active.cors,
          hyp="O servidor pode aceitar requisicoes de qualquer origem com credenciais.",
          exp="Nenhuma origem arbitraria (nem 'null') e refletida em Access-Control-Allow-Origin.",
          imp="Qualquer site aberto pela vitima pode ler respostas autenticadas da aplicacao."),
    _spec("METHOD-001", "Metodos HTTP habilitados", P.MIDDLEGAME, ACTIVE, L, "WSTG-CONF-06", "A02:2025",
          active.http_methods,
          hyp="O servidor pode anunciar metodos desnecessarios (TRACE, PUT, DELETE).",
          exp="Apenas os metodos usados pela aplicacao (ex.: GET, POST, OPTIONS).",
          imp="Metodos sobrando ampliam a superficie de ataque; TRACE pode ajudar a roubar cabecalhos."),
    # --- Final (ativo leve, com aprovacao humana) ---
    _spec("FILE-001", "Exposicao do repositorio .git", P.ENDGAME, ACTIVE, H, "WSTG-CONF-04", "A02:2025",
          active.git_exposed, approval=True,
          hyp="A pasta .git pode ter sido publicada junto com o site.",
          exp="/.git/HEAD nao acessivel (404/403).",
          imp="Com o .git exposto, o codigo-fonte e o historico (as vezes com senhas) podem ser baixados."),
    _spec("FILE-002", "Exposicao do arquivo .env", P.ENDGAME, ACTIVE, H, "WSTG-CONF-04", "A02:2025",
          active.env_exposed, approval=True,
          hyp="O arquivo de configuracao .env pode estar acessivel publicamente.",
          exp="/.env nao acessivel ou sem formato CHAVE=valor.",
          imp="O .env costuma guardar senhas de banco e chaves de API: exposicao equivale a vazamento de credenciais."),
    _spec("ERR-001", "Detalhes internos na pagina de erro", P.ENDGAME, ACTIVE, MED, "WSTG-ERRH-01", "A10:2025",
          active.error_page, approval=True,
          hyp="Erros podem mostrar stack trace, caminhos de arquivos ou consultas SQL.",
          exp="Pagina de erro generica (404) sem detalhes internos.",
          imp="Detalhes internos ajudam o atacante a mapear tecnologias, arquivos e consultas da aplicacao."),
]

CATALOG_BY_ID: dict[str, CheckSpec] = {c.test_id: c for c in CATALOG}
