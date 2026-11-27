"""OAuth2 login providers (42 and Google) through Authlib's Starlette client.

A provider is enabled only when its client id is configured in .env.
"""

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App

from app.config import Settings, get_settings
from app.services.users import OAuthProfile

FORTYTWO = "42"
GOOGLE = "google"

oauth = OAuth()


def register_providers(settings: Settings) -> None:
    if settings.fortytwo_client_id:
        oauth.register(
            FORTYTWO,
            overwrite=True,
            client_id=settings.fortytwo_client_id,
            client_secret=settings.fortytwo_client_secret.get_secret_value(),
            authorize_url="https://api.intra.42.fr/oauth/authorize",
            access_token_url="https://api.intra.42.fr/oauth/token",
            api_base_url="https://api.intra.42.fr/v2/",
            client_kwargs={"scope": "public", "token_endpoint_auth_method": "client_secret_post"},
        )
    if settings.google_client_id:
        oauth.register(
            GOOGLE,
            overwrite=True,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


register_providers(get_settings())


def get_client(provider: str) -> StarletteOAuth2App | None:
    if provider not in (FORTYTWO, GOOGLE):
        return None
    return oauth.create_client(provider)


def callback_url(provider: str) -> str:
    """Must match the redirect URI registered at the provider exactly."""
    return f"{get_settings().public_api_url}/api/auth/oauth/{provider}/callback"


async def fetch_profile(provider: str, client: StarletteOAuth2App, token: dict) -> OAuthProfile:
    if provider == FORTYTWO:
        response = await client.get("me", token=token)
        response.raise_for_status()
        data = response.json()
        return OAuthProfile(
            provider=FORTYTWO,
            subject=str(data["id"]),
            email=data["email"],
            # 42 accounts are created by the school: the address is trusted.
            email_verified=True,
            username_hint=data.get("login") or "",
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or "",
        )

    # Google is OpenID Connect: Authlib validated the ID token and put its claims here.
    claims = token.get("userinfo") or await client.userinfo(token=token)
    return OAuthProfile(
        provider=GOOGLE,
        subject=str(claims["sub"]),
        email=claims["email"],
        email_verified=bool(claims.get("email_verified")),
        username_hint=claims["email"].split("@")[0],
        first_name=claims.get("given_name") or "",
        last_name=claims.get("family_name") or "",
    )
