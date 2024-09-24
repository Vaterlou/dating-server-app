"""empty message

Revision ID: 2231b308e851
Revises: a92cd784ab8f
Create Date: 2024-09-24 14:59:09.130176

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2231b308e851'
down_revision = 'a92cd784ab8f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('spatial_ref_sys')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('spatial_ref_sys',
    sa.Column('srid', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('auth_name', sa.VARCHAR(length=256), autoincrement=False, nullable=True),
    sa.Column('auth_srid', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('srtext', sa.VARCHAR(length=2048), autoincrement=False, nullable=True),
    sa.Column('proj4text', sa.VARCHAR(length=2048), autoincrement=False, nullable=True),
    sa.CheckConstraint('srid > 0 AND srid <= 998999', name='spatial_ref_sys_srid_check'),
    sa.PrimaryKeyConstraint('srid', name='spatial_ref_sys_pkey')
    )
    # ### end Alembic commands ###
