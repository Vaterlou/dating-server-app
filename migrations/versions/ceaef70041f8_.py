"""empty message

Revision ID: ceaef70041f8
Revises: 6392ec12e706
Create Date: 2024-08-21 16:28:59.596244

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = 'ceaef70041f8'
down_revision = '6392ec12e706'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('profile', schema=None) as batch_op:
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('coordinates', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True))
        batch_op.create_index('idx_user_coords', ['coordinates'], unique=False, postgresql_using='gist')
        batch_op.create_index(batch_op.f('ix_user_coordinates'), ['coordinates'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_coordinates'))
        batch_op.drop_index('idx_user_coordinates', postgresql_using='gist')
        batch_op.drop_column('coordinates')

    with op.batch_alter_table('profile', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latitude', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))

    # ### end Alembic commands ###
