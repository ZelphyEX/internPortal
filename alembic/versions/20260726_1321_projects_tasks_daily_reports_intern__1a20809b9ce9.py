"""projects, tasks, daily reports, intern profile, comment+module fields

Covers docs/backend-requirements.md:
  mục 1 — intern profile columns on `users` (+ self FK mentor_id)
  mục 2 — `projects`, `project_members`, `project_tags`
  mục 3 — `tasks`
  mục 4 — `daily_reports`
  mục 5 — course metadata on `modules`
  mục 6 — `comments.code_snippet`, `comments.is_resolved`

Hand-adjusted after autogenerate (see CLAUDE.md mục 7):
  * the `department` type is shared by users/modules/projects, so it is created
    once up front and referenced with create_type=False;
  * the self-referencing FK on users.mentor_id is named explicitly, otherwise
    downgrade cannot drop it;
  * downgrade drops the enum types it created, so upgrade stays repeatable.

Revision ID: 1a20809b9ce9
Revises: c91b052bfd47
Create Date: 2026-07-26 13:21:50.070760+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1a20809b9ce9'
down_revision: Union[str, None] = 'c91b052bfd47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_USERS_MENTOR = "fk_users_mentor_id_users"

# Shared by users.department, modules.track and projects.department.
department_enum = postgresql.ENUM(
    "Java Back-End",
    "React Front-End",
    "Cloud & DevOps",
    "Salesforce/ERP",
    "AI & Data Science",
    name="department",
    create_type=False,
)

# Each of these belongs to exactly one new table, so CREATE TYPE is emitted by
# the corresponding create_table().
project_status_enum = sa.Enum(
    "In Planning", "Active", "Under Review", "Completed", name="project_status",
)
task_status_enum = sa.Enum(
    "To Do", "In Progress", "In Review", "Done", "Blocked", name="task_status",
)
task_priority_enum = sa.Enum("Low", "Medium", "High", "Urgent", name="task_priority")
daily_report_status_enum = sa.Enum(
    "Pending", "Approved", "Needs Revision", name="daily_report_status",
)


def upgrade() -> None:
    department_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------ #
    # mục 4 — daily_reports
    # ------------------------------------------------------------------ #
    op.create_table(
        'daily_reports',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('intern_id', sa.BigInteger(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('completed_today', sa.Text(), nullable=False),
        sa.Column('tomorrow_plan', sa.Text(), nullable=True),
        sa.Column('blockers', sa.Text(), nullable=True),
        sa.Column('hours_logged', sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column('status', daily_report_status_enum, nullable=False),
        sa.Column('mentor_comment', sa.Text(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('reviewed_by', sa.BigInteger(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['intern_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('intern_id', 'date', name='uq_daily_reports_intern_date'),
    )
    op.create_index(op.f('ix_daily_reports_date'), 'daily_reports', ['date'], unique=False)
    op.create_index(op.f('ix_daily_reports_intern_id'), 'daily_reports', ['intern_id'], unique=False)

    # ------------------------------------------------------------------ #
    # mục 2 — projects (+ members, tags)
    # ------------------------------------------------------------------ #
    op.create_table(
        'projects',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('department', department_enum, nullable=True),
        sa.Column('status', project_status_enum, nullable=False),
        sa.Column('lead_user_id', sa.BigInteger(), nullable=True),
        sa.Column('progress_percent', sa.Integer(), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lead_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_projects_code'), 'projects', ['code'], unique=True)
    op.create_index(op.f('ix_projects_lead_user_id'), 'projects', ['lead_user_id'], unique=False)
    op.create_table(
        'project_members',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_members_project_user'),
    )
    op.create_index(op.f('ix_project_members_project_id'), 'project_members', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_members_user_id'), 'project_members', ['user_id'], unique=False)
    op.create_table(
        'project_tags',
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('tag_id', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ),
        sa.PrimaryKeyConstraint('project_id', 'tag_id'),
    )

    # ------------------------------------------------------------------ #
    # mục 3 — tasks
    # ------------------------------------------------------------------ #
    op.create_table(
        'tasks',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('project_id', sa.BigInteger(), nullable=True),
        sa.Column('assigned_intern_id', sa.BigInteger(), nullable=True),
        sa.Column('mentor_id', sa.BigInteger(), nullable=True),
        sa.Column('status', task_status_enum, nullable=False),
        sa.Column('priority', task_priority_enum, nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('pr_url', sa.String(length=1024), nullable=True),
        sa.Column('mentor_feedback', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assigned_intern_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['mentor_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tasks_assigned_intern_id'), 'tasks', ['assigned_intern_id'], unique=False)
    op.create_index(op.f('ix_tasks_mentor_id'), 'tasks', ['mentor_id'], unique=False)
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'], unique=False)

    # ------------------------------------------------------------------ #
    # mục 6 — comments
    # ------------------------------------------------------------------ #
    op.add_column('comments', sa.Column('code_snippet', sa.Text(), nullable=True))
    op.add_column(
        'comments',
        sa.Column('is_resolved', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )

    # ------------------------------------------------------------------ #
    # mục 5 — modules course metadata
    # ------------------------------------------------------------------ #
    op.add_column('modules', sa.Column('track', department_enum, nullable=True))
    op.add_column('modules', sa.Column('week_number', sa.Integer(), nullable=True))
    op.add_column('modules', sa.Column('duration_text', sa.String(length=100), nullable=True))
    op.add_column(
        'modules',
        sa.Column(
            'key_skills',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------ #
    # mục 1 — intern profile on users
    # ------------------------------------------------------------------ #
    op.add_column('users', sa.Column('department', department_enum, nullable=True))
    op.add_column('users', sa.Column('mentor_id', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('start_date', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('end_date', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('university', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('major', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('github_url', sa.String(length=512), nullable=True))
    op.add_column('users', sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('users', sa.Column('attendance_rate', sa.Numeric(precision=5, scale=2), nullable=True))
    op.create_index(op.f('ix_users_mentor_id'), 'users', ['mentor_id'], unique=False)
    op.create_foreign_key(FK_USERS_MENTOR, 'users', 'users', ['mentor_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(FK_USERS_MENTOR, 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_mentor_id'), table_name='users')
    for column in (
        'attendance_rate', 'score', 'github_url', 'bio', 'major', 'university',
        'end_date', 'start_date', 'phone', 'mentor_id', 'department',
    ):
        op.drop_column('users', column)

    for column in ('key_skills', 'duration_text', 'week_number', 'track'):
        op.drop_column('modules', column)

    op.drop_column('comments', 'is_resolved')
    op.drop_column('comments', 'code_snippet')

    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_mentor_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_assigned_intern_id'), table_name='tasks')
    op.drop_table('tasks')

    op.drop_table('project_tags')
    op.drop_index(op.f('ix_project_members_user_id'), table_name='project_members')
    op.drop_index(op.f('ix_project_members_project_id'), table_name='project_members')
    op.drop_table('project_members')
    op.drop_index(op.f('ix_projects_lead_user_id'), table_name='projects')
    op.drop_index(op.f('ix_projects_code'), table_name='projects')
    op.drop_table('projects')

    op.drop_index(op.f('ix_daily_reports_intern_id'), table_name='daily_reports')
    op.drop_index(op.f('ix_daily_reports_date'), table_name='daily_reports')
    op.drop_table('daily_reports')

    # Drop the enum types last, so `upgrade` can run again from a clean slate.
    for type_name in (
        'task_priority', 'task_status', 'project_status',
        'daily_report_status', 'department',
    ):
        op.execute(sa.text(f'DROP TYPE IF EXISTS {type_name}'))
