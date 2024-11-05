"""Initializing user_id and playlists

Revision ID: f4bd903d0bd0
Revises: 
Create Date: 2024-11-05 08:31:08.280909

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4bd903d0bd0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_id',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=True),
    sa.Column('user_id', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('playlist',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('spotify_id', sa.String(length=50), nullable=False),
    sa.Column('user_id', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user_id.user_id'], ),
    sa.PrimaryKeyConstraint('spotify_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('playlist')
    op.drop_table('user_id')
    # ### end Alembic commands ###
