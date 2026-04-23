"""add audit evidence tables

Revision ID: b1c2d3e4f5a6
Revises: aec45213e565
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = 'aec45213e565'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'operation_audit_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trace_id', sa.String(), nullable=False),
        sa.Column('parent_trace_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('event_stage', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('operation_batch_id', sa.Integer(), sa.ForeignKey('operation_batch.id'), nullable=True),
        sa.Column('import_job_id', sa.Integer(), sa.ForeignKey('import_job.id'), nullable=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('student.id'), nullable=True),
        sa.Column('student_no', sa.String(), nullable=True),
        sa.Column('mobile_account_id', sa.Integer(), sa.ForeignKey('mobile_account.id'), nullable=True),
        sa.Column('mobile_account', sa.String(), nullable=True),
        sa.Column('operator_id', sa.Integer(), sa.ForeignKey('admin_user.id'), nullable=True),
        sa.Column('idempotency_key', sa.String(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('decision_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_oae_event_type_created', 'operation_audit_event', ['event_type', 'created_at'])
    op.create_index('ix_oae_trace_id', 'operation_audit_event', ['trace_id'])
    op.create_index('ix_oae_operation_batch_id', 'operation_audit_event', ['operation_batch_id'])

    op.create_table(
        'entity_change_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trace_id', sa.String(), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('change_type', sa.String(), nullable=False),
        sa.Column('before_json', sa.JSON(), nullable=True),
        sa.Column('after_json', sa.JSON(), nullable=True),
        sa.Column('change_reason', sa.String(), nullable=True),
        sa.Column('operation_batch_id', sa.Integer(), nullable=True),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('mobile_account_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ecl_trace_id', 'entity_change_log', ['trace_id'])
    op.create_index('ix_ecl_entity', 'entity_change_log', ['entity_type', 'entity_id'])
    op.create_index('ix_ecl_created_at', 'entity_change_log', ['created_at'])

    op.create_table(
        'daily_audit_run',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_date', sa.Date(), nullable=False),
        sa.Column('scope_start_at', sa.DateTime(), nullable=True),
        sa.Column('scope_end_at', sa.DateTime(), nullable=True),
        sa.Column('overall_status', sa.String(), nullable=False),
        sa.Column('hard_failures', sa.Integer(), nullable=False),
        sa.Column('warnings', sa.Integer(), nullable=False),
        sa.Column('llm_status', sa.String(), nullable=True),
        sa.Column('summary_json', sa.JSON(), nullable=False),
        sa.Column('report_markdown', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('audit_date'),
    )

    op.create_table(
        'daily_audit_issue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_run_id', sa.Integer(), sa.ForeignKey('daily_audit_run.id'), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('rule_code', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('detail_json', sa.JSON(), nullable=False),
        sa.Column('sample_refs_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('daily_audit_issue')
    op.drop_table('daily_audit_run')
    op.drop_index('ix_ecl_created_at', 'entity_change_log')
    op.drop_index('ix_ecl_entity', 'entity_change_log')
    op.drop_index('ix_ecl_trace_id', 'entity_change_log')
    op.drop_table('entity_change_log')
    op.drop_index('ix_oae_operation_batch_id', 'operation_audit_event')
    op.drop_index('ix_oae_trace_id', 'operation_audit_event')
    op.drop_index('ix_oae_event_type_created', 'operation_audit_event')
    op.drop_table('operation_audit_event')
