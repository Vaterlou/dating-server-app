"""empty message

Revision ID: b20a1d83b397
Revises: 
Create Date: 2024-09-19 16:32:52.968817

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b20a1d83b397'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # op.drop_table('spatial_ref_sys')
    with op.batch_alter_table('match', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_match_created_at'), ['created_at'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('match', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_match_created_at'))
        batch_op.drop_column('created_at')

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
