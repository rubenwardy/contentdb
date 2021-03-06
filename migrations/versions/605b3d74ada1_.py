"""empty message

Revision ID: 605b3d74ada1
Revises: 28a427cbd4cf
Create Date: 2018-06-11 22:50:36.828818

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '605b3d74ada1'
down_revision = '28a427cbd4cf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('thread',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('package_id', sa.Integer(), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('private', sa.Boolean(), server_default='0', nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['package_id'], ['package.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('thread_reply',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('thread_id', sa.Integer(), nullable=False),
    sa.Column('comment', sa.String(length=500), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['thread_id'], ['thread.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.add_column('package', sa.Column('review_thread_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'package', 'thread', ['review_thread_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'package', type_='foreignkey')
    op.drop_constraint(None, 'package', type_='foreignkey')
    op.drop_column('package', 'review_thread_id')
    op.drop_table('thread_reply')
    op.drop_table('thread')
    # ### end Alembic commands ###
