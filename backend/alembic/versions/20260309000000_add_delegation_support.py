"""add_delegation_support

Revision ID: 20260309000000
Revises: faf2ebe67bd9
Create Date: 2026-03-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260309000000"
down_revision: Union[str, Sequence[str], None] = "faf2ebe67bd9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add experiment_type to experiments
    op.add_column(
        "experiments",
        sa.Column(
            "experiment_type",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'rating'"),
        ),
    )

    # Add delegation_task_id to raters
    op.add_column(
        "raters",
        sa.Column("delegation_task_id", sa.String(64), nullable=True),
    )

    # Create interaction_logs table
    op.create_table(
        "interaction_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("prolific_pid", sa.String(64), nullable=False),
        sa.Column(
            "experiment_id",
            sa.Integer,
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(64), nullable=False),
        sa.Column("condition", sa.String(16), nullable=False),
        sa.Column("interaction_type", sa.String(32), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.UniqueConstraint(
            "prolific_pid", "task_id", "condition", name="uq_interaction_log"
        ),
    )


def downgrade() -> None:
    op.drop_table("interaction_logs")
    op.drop_column("raters", "delegation_task_id")
    op.drop_column("experiments", "experiment_type")
