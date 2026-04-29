"""add charge raw records

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'charge_raw_record',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('import_job_id', sa.Integer(), nullable=False),
        sa.Column('row_no', sa.Integer(), nullable=False),
        sa.Column('sheet_name', sa.String(), nullable=True),
        sa.Column('source_month', sa.String(), nullable=True),
        sa.Column('parsed_charge_time', sa.DateTime(), nullable=True),
        sa.Column('raw_time_text', sa.Text(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('row_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['import_job_id'], ['import_job.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_charge_raw_record_charge_time', 'charge_raw_record', ['parsed_charge_time'])
    op.create_index('ix_charge_raw_record_import_job', 'charge_raw_record', ['import_job_id'])
    op.create_index('ix_charge_raw_record_row_hash', 'charge_raw_record', ['row_hash'])
    op.create_index('ix_charge_raw_record_source_month', 'charge_raw_record', ['source_month'])


def downgrade():
    op.drop_index('ix_charge_raw_record_source_month', 'charge_raw_record')
    op.drop_index('ix_charge_raw_record_row_hash', 'charge_raw_record')
    op.drop_index('ix_charge_raw_record_import_job', 'charge_raw_record')
    op.drop_index('ix_charge_raw_record_charge_time', 'charge_raw_record')
    op.drop_table('charge_raw_record')
