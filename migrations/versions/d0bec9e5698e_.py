"""empty message

Revision ID: d0bec9e5698e
Revises: aa6d7b595a94
Create Date: 2018-05-29 21:23:43.847738

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0bec9e5698e'
down_revision = 'aa6d7b595a94'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('license', sa.Column('is_foss', sa.Boolean(), nullable=False, server_default="true"))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('license', 'is_foss')
    # ### end Alembic commands ###
