"""Initial OpsPilot schema."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from app.db import models  # noqa: F401
    from app.db.base import Base
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.db import models  # noqa: F401
    from app.db.base import Base
    Base.metadata.drop_all(bind=bind)
