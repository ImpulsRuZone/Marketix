from supabase import Client, create_client

from app.config import settings


def get_supabase() -> Client:
    """Create a Supabase client with service-role privileges."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
