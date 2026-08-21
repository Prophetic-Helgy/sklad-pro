"""номер_документа_nullable

Ревижент: f2c9a7e41b33
Создано: 2026-08-21

Номер документа назначается при проведении («Записать» в 7.1),
поэтому у черновиков он NULL.
"""
import sqlalchemy as sa
from alembic import op

revision = "f2c9a7e41b33"
down_revision = "b53a15aba3d7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("number", existing_type=sa.String(length=30), nullable=True)


def downgrade():
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("number", existing_type=sa.String(length=30), nullable=False)
