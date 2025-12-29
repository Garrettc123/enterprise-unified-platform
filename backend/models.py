from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum, Float, Table, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

# Association table for many-to-many relationships
user_organization = Table(
    'user_organization',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id', ondelete='CASCADE')),
    Column('organization_id', Integer, ForeignKey('organization.id', ondelete='CASCADE')),
    Column('role', String(20), default='member')
)

project_team = Table(
    'project_team',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('project.id', ondelete='CASCADE')),
    Column('user_id', Integer, ForeignKey('user.id', ondelete='CASCADE')),
    Column('role', String(20), default='contributor')
)

class User(Base):
    __tablename__ = 'user'
    __table_args__ = (
        Index('idx_username', 'username'),
        Index('idx_email', 'email'),
    )
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255))
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    avatar_url = Column(String(500))
    bio = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organizations = relationship('Organization', secondary=user_organization, back_populates='members')
    projects = relationship('Project', secondary=project_team, back_populates='team_members')
    api_keys = relationship('APIKey', back_populates='user', cascade='all, delete-orphan')
    audit_logs = relationship('AuditLog', back_populates='user')
    notifications = relationship('Notification', back_populates='user', cascade='all, delete-orphan')

class Organization(Base):
    __tablename__ = 'organization'
    __table_args__ = (
        Index('idx_slug', 'slug'),
    )
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    logo_url = Column(String(500))
    website = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members = relationship('User', secondary=user_organization, back_populates='organizations')
    projects = relationship('Project', back_populates='organization', cascade='all, delete-orphan')
    teams = relationship('Team', back_populates='organization', cascade='all, delete-orphan')

class Project(Base):
    __tablename__ = 'project'
    __table_args__ = (
        Index('idx_organization_id', 'organization_id'),
        Index('idx_status', 'status'),
    )
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    organization_id = Column(Integer, ForeignKey('organization.id', ondelete='CASCADE'), nullable=False)
    created_by = Column(Integer, ForeignKey('user.id'), nullable=False)
    status = Column(String(20), default='active')  # active, archived, completed
    priority = Column(String(20), default='medium')  # low, medium, high, critical
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    budget = Column(Float)
    meta_data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship('Organization', back_populates='projects')
    team_members = relationship('User', secondary=project_team, back_populates='projects')
    tasks = relationship('Task', back_populates='project', cascade='all, delete-orphan')
    milestones = relationship('Milestone', back_populates='project', cascade='all, delete-orphan')

class Task(Base):
    __tablename__ = 'task'
    __table_args__ = (
        Index('idx_project_id', 'project_id'),
        Index('idx_assigned_to', 'assigned_to'),
        Index('idx_status', 'status'),
    )
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    project_id = Column(Integer, ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    assigned_to = Column(Integer, ForeignKey('user.id'))
    created_by = Column(Integer, ForeignKey('user.id'), nullable=False)
    status = Column(String(20), default='todo')  # todo, in_progress, in_review, completed, blocked
    priority = Column(String(20), default='medium')
    story_points = Column(Integer)
    due_date = Column(DateTime)
    start_date = Column(DateTime)
    completed_at = Column(DateTime)
    meta_data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship('Project', back_populates='tasks')
    comments = relationship('Comment', back_populates='task', cascade='all, delete-orphan')
    attachments = relationship('Attachment', back_populates='task', cascade='all, delete-orphan')

class Comment(Base):
    __tablename__ = 'comment'
    __table_args__ = (
        Index('idx_task_id', 'task_id'),
        Index('idx_created_by', 'created_by'),
    )
    
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    task_id = Column(Integer, ForeignKey('task.id', ondelete='CASCADE'), nullable=False)
    created_by = Column(Integer, ForeignKey('user.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    task = relationship('Task', back_populates='comments')

class Milestone(Base):
    __tablename__ = 'milestone'
    __table_args__ = (
        Index('idx_project_id', 'project_id'),
    )
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    project_id = Column(Integer, ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    target_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship('Project', back_populates='milestones')

class Attachment(Base):
    __tablename__ = 'attachment'
    __table_args__ = (
        Index('idx_task_id', 'task_id'),
    )
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(50))
    task_id = Column(Integer, ForeignKey('task.id', ondelete='CASCADE'), nullable=False)
    uploaded_by = Column(Integer, ForeignKey('user.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    task = relationship('Task', back_populates='attachments')

class Team(Base):
    __tablename__ = 'team'
    __table_args__ = (
        Index('idx_organization_id', 'organization_id'),
    )
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    organization_id = Column(Integer, ForeignKey('organization.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    organization = relationship('Organization', back_populates='teams')

class APIKey(Base):
    __tablename__ = 'api_key'
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_key', 'key'),
    )
    
    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship('User', back_populates='api_keys')

class AuditLog(Base):
    __tablename__ = 'audit_log'
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_created_at', 'created_at'),
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer)
    changes = Column(JSON)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship('User', back_populates='audit_logs')

class Notification(Base):
    __tablename__ = 'notification'
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_read', 'is_read'),
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    notification_type = Column(String(50))  # task_assigned, task_updated, comment_added, etc
    related_entity_type = Column(String(50))
    related_entity_id = Column(Integer)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship('User', back_populates='notifications')