"""add_user_profile_table

Revision ID: f105cb510f6c
Revises: 
Create Date: 2026-02-12 17:05:05.968497

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f105cb510f6c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_profile table."""
    op.create_table(
        'user_profile',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('phone_number', sa.String(20), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('job_title', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('timezone', sa.String(50), server_default='UTC', nullable=True),
        sa.Column('language', sa.String(10), server_default='en', nullable=True),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('github_url', sa.String(500), nullable=True),
        sa.Column('twitter_url', sa.String(500), nullable=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('date_of_birth', sa.DateTime(), nullable=True),
        sa.Column('profile_visibility', sa.String(20), server_default='public', nullable=True),
        sa.Column('notification_preferences', sa.JSON(), server_default='{}', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index('idx_userprofile_user_id', 'user_profile', ['user_id'])


def downgrade() -> None:
    """Drop user_profile table."""
    op.drop_index('idx_userprofile_user_id', table_name='user_profile')
    op.drop_table('user_profile')
