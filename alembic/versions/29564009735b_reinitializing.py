"""Reinitializing

Revision ID: 29564009735b
Revises: 
Create Date: 2024-11-27 13:39:48.525662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29564009735b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('artist',
    sa.Column('spotify_id', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('spotify_id')
    )
    op.create_table('user_id',
    sa.Column('user_id', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('album',
    sa.Column('spotify_id', sa.String(length=50), nullable=False),
    sa.Column('artist_id', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('release_date', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.spotify_id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('spotify_id')
    )
    op.create_table('playlist',
    sa.Column('spotify_id', sa.String(length=50), nullable=False),
    sa.Column('user_id', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user_id.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('spotify_id')
    )
    op.create_table('track',
    sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1, increment=1), nullable=False),
    sa.Column('spotify_id', sa.String(length=50), nullable=False),
    sa.Column('playlist_id', sa.String(length=50), nullable=False),
    sa.Column('artist_id', sa.String(length=50), nullable=True),
    sa.Column('album_id', sa.String(length=50), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.ForeignKeyConstraint(['album_id'], ['album.spotify_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.spotify_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['playlist_id'], ['playlist.spotify_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('track')
    op.drop_table('playlist')
    op.drop_table('album')
    op.drop_table('user_id')
    op.drop_table('artist')
    # ### end Alembic commands ###
