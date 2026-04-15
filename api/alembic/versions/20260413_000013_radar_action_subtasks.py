"""radar_action_subtasks_and_assignment

Revision ID: 20260413_000013
Revises: 9744ba6cc488
Create Date: 2026-04-13 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260413_000013'
down_revision: Union[str, Sequence[str], None] = '9744ba6cc488'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add parent_action_id for sub-task tree structure
    op.add_column(
        'radar_actions',
        sa.Column('parent_action_id', sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        'fk_radar_actions_parent_action_id',
        'radar_actions', 'radar_actions',
        ['parent_action_id'], ['id']
    )

    # Add assigned_user_id for proper user assignment (replaces string owner)
    op.add_column(
        'radar_actions',
        sa.Column('assigned_user_id', sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        'fk_radar_actions_assigned_user_id',
        'radar_actions', 'users',
        ['assigned_user_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_radar_actions_assigned_user_id', 'radar_actions', type_='foreignkey')
    op.drop_column('radar_actions', 'assigned_user_id')
    op.drop_constraint('fk_radar_actions_parent_action_id', 'radar_actions', type_='foreignkey')
    op.drop_column('radar_actions', 'parent_action_id')
