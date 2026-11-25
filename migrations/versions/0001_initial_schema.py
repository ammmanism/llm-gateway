"""initial production schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id uuid PRIMARY KEY,
            api_key_hash text NOT NULL UNIQUE,
            name text NOT NULL,
            tier text NOT NULL DEFAULT 'free',
            rate_limit_rpm integer NOT NULL DEFAULT 20,
            rate_limit_tpm integer NOT NULL DEFAULT 10000,
            spend_cap_usd numeric(12, 6),
            alert_threshold numeric(12, 6),
            routing_weights jsonb,
            allowed_models text[],
            cache_threshold double precision NOT NULL DEFAULT 0.92,
            cache_ttl_hours integer NOT NULL DEFAULT 24,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_entries (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            namespace text NOT NULL DEFAULT 'default',
            embedding vector(384) NOT NULL,
            metadata_hash text NOT NULL,
            prompt_hash text NOT NULL,
            query_text text NOT NULL,
            response_text jsonb NOT NULL,
            model text NOT NULL,
            provider text NOT NULL,
            tokens_in integer NOT NULL DEFAULT 0,
            tokens_out integer NOT NULL DEFAULT 0,
            cost_usd numeric(12, 8) NOT NULL DEFAULT 0,
            hit_count integer NOT NULL DEFAULT 0,
            invalidated_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_log (
            id bigserial PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            request_id text NOT NULL,
            is_cache_hit boolean NOT NULL,
            provider text,
            model text,
            tokens_in integer NOT NULL DEFAULT 0,
            tokens_out integer NOT NULL DEFAULT 0,
            cost_usd numeric(12, 8) NOT NULL DEFAULT 0,
            saved_usd numeric(12, 8) NOT NULL DEFAULT 0,
            latency_ms integer NOT NULL DEFAULT 0,
            cache_similarity double precision,
            routing_reason text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tenants_api_key_hash ON tenants(api_key_hash)"
    )
    op.execute(
        (
            "CREATE INDEX IF NOT EXISTS idx_cache_entries_tenant_namespace "
            "ON cache_entries(tenant_id, namespace)"
        )
    )
    op.execute(
        (
            "CREATE INDEX IF NOT EXISTS idx_cache_entries_metadata_hash "
            "ON cache_entries(metadata_hash)"
        )
    )
    op.execute(
        (
            "CREATE INDEX IF NOT EXISTS idx_cache_entries_prompt_hash "
            "ON cache_entries(prompt_hash)"
        )
    )
    op.execute(
        (
            "CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at "
            "ON cache_entries(expires_at)"
        )
    )
    op.execute(
        (
            "CREATE INDEX IF NOT EXISTS idx_usage_log_tenant_created_at "
            "ON usage_log(tenant_id, created_at DESC)"
        )
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cache_entries_embedding_hnsw "
        "ON cache_entries USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS usage_log")
    op.execute("DROP TABLE IF EXISTS cache_entries")
    op.execute("DROP TABLE IF EXISTS tenants")
