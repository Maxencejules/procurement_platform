"""Enforce one decision per step, unique step order, and valid money.

Revision ID: 0002
Revises: 0001

Existing invalid data intentionally fails this migration for operator review;
do not silently discard decisions or rewrite historical amounts.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_decision_step", "approval_decisions", ["step_id"])
    op.create_unique_constraint("uq_request_step_order", "approval_steps", ["purchase_request_id", "step_order"])
    op.create_check_constraint(
        "ck_request_amount", "purchase_requests", "amount > 0 AND amount <= 9999999999.99"
    )


def downgrade():
    op.drop_constraint("ck_request_amount", "purchase_requests", type_="check")
    op.drop_constraint("uq_request_step_order", "approval_steps", type_="unique")
    op.drop_constraint("uq_decision_step", "approval_decisions", type_="unique")
