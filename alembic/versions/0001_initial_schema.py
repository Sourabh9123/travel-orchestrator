"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    trip_status = postgresql.ENUM(
        "DRAFT", "PLANNING", "VALIDATING", "READY", "BOOKING", "BOOKED", "FAILED", name="tripstatus"
    )
    booking_status = postgresql.ENUM(
        "PENDING", "CONFIRMED", "CANCELLED", "FAILED", name="bookingstatus"
    )
    trip_status.create(op.get_bind(), checkfirst=True)
    booking_status.create(op.get_bind(), checkfirst=True)
    trip_status = postgresql.ENUM(
        "DRAFT",
        "PLANNING",
        "VALIDATING",
        "READY",
        "BOOKING",
        "BOOKED",
        "FAILED",
        name="tripstatus",
        create_type=False,
    )
    booking_status = postgresql.ENUM(
        "PENDING",
        "CONFIRMED",
        "CANCELLED",
        "FAILED",
        name="bookingstatus",
        create_type=False,
    )

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("roles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "trips",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", trip_status, nullable=False),
        sa.Column("origin", sa.String(length=255), nullable=True),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("final_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trips_user_id"), "trips", ["user_id"], unique=False)

    for table_name, columns in {
        "itineraries": [
            sa.Column("day", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        ],
        "activities": [
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("category", sa.String(length=120), nullable=False),
            sa.Column("location", sa.String(length=255), nullable=True),
            sa.Column("price_amount", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        ],
    }.items():
        op.create_table(
            table_name,
            sa.Column("trip_id", sa.UUID(), nullable=False),
            *columns,
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f(f"ix_{table_name}_trip_id"), table_name, ["trip_id"], unique=False)

    op.create_table(
        "flights",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("flight_number", sa.String(length=80), nullable=True),
        sa.Column("origin", sa.String(length=120), nullable=False),
        sa.Column("destination", sa.String(length=120), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flights_trip_id"), "flights", ["trip_id"], unique=False)
    op.create_table(
        "hotels",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("rating", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("nightly_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hotels_trip_id"), "hotels", ["trip_id"], unique=False)
    op.create_table(
        "bookings",
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("booking_type", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("status", booking_status, nullable=False),
        sa.Column("confirmation_code", sa.String(length=120), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_trip_id"), "bookings", ["trip_id"], unique=False)
    op.create_table(
        "conversations",
        sa.Column("trip_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_trip_id"), "conversations", ["trip_id"], unique=False)
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_table(
        "agent_logs",
        sa.Column("trip_id", sa.UUID(), nullable=True),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_logs_agent_name"), "agent_logs", ["agent_name"], unique=False)
    op.create_index(op.f("ix_agent_logs_trip_id"), "agent_logs", ["trip_id"], unique=False)
    op.create_index(op.f("ix_agent_logs_workflow_id"), "agent_logs", ["workflow_id"], unique=False)
    op.create_table(
        "execution_graphs",
        sa.Column("trip_id", sa.UUID(), nullable=True),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("graph", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_execution_graphs_trip_id"),
        "execution_graphs",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_graphs_workflow_id"),
        "execution_graphs",
        ["workflow_id"],
        unique=False,
    )


def downgrade() -> None:
    for table in [
        "execution_graphs",
        "agent_logs",
        "conversations",
        "bookings",
        "hotels",
        "flights",
        "activities",
        "itineraries",
        "trips",
        "users",
    ]:
        op.drop_table(table)
    sa.Enum(name="bookingstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tripstatus").drop(op.get_bind(), checkfirst=True)
