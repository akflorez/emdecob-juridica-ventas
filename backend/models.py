from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Text,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Table,
    BigInteger,
    Index,
    Float,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from backend.db import Base

# Tabla de asociación para múltiples responsables por tarea
task_assignees = Table(
    "task_assignees",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    radicado = Column(String(60), index=True, nullable=False)
    id_proceso = Column(String(50), nullable=True, index=True) # ID único de Rama Judicial

    demandante = Column(String(255), nullable=True)
    demandado = Column(String(255), nullable=True)
    juzgado = Column(String(255), nullable=True)
    alias = Column(String(200), nullable=True)
    cedula = Column(String(50), nullable=True)
    abogado = Column(String(200), nullable=True)
    telefono = Column(String(50), nullable=True) # Para mensajería Cally
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    last_hash = Column(String(64), nullable=True)
    current_hash = Column(String(64), nullable=True)
    last_check_at = Column(DateTime, nullable=True)

    fecha_radicacion = Column(Date, nullable=True)
    ultima_actuacion = Column(Date, nullable=True)

    has_documents = Column(Boolean, default=False)
    
    # Seguimiento de progreso para publicaciones
    sync_pub_status = Column(String(100), nullable=True)   # Ej: "Buscando...", "Finalizado"
    sync_pub_progress = Column(Integer, default=0)         # 0 a 100

    is_active = Column(Boolean, default=True, nullable=False) # Para cobro por radicado activo

    # Nuevos campos del motor fallback / fuentes alternativas
    despacho = Column(String(255), nullable=True)
    clase_proceso = Column(String(255), nullable=True)
    tipo_proceso = Column(String(255), nullable=True)
    estado = Column(String(255), nullable=True)
    ponente_juez = Column(String(255), nullable=True)
    departamento = Column(String(255), nullable=True)
    municipio = Column(String(255), nullable=True)
    ubicacion = Column(String(255), nullable=True)
    fuente_encontrado = Column(String(255), nullable=True)
    url_fuente = Column(String(500), nullable=True)
    metodo_busqueda = Column(String(255), nullable=True)
    confianza_busqueda = Column(Integer, nullable=True)
    encontrado_en_fuente_alternativa = Column(Boolean, default=False, nullable=True)
    requiere_revision = Column(Boolean, default=False, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    tasks = relationship("Task", back_populates="case", cascade="all, delete-orphan")
    events = relationship("CaseEvent", back_populates="case", cascade="all, delete-orphan")
    company = relationship("Company", foreign_keys=[company_id])
    user = relationship("User", foreign_keys=[user_id])


class BillingTier(Base):
    """Rangos de cobro para facturación por radicados activos"""
    __tablename__ = "billing_tiers"

    id = Column(Integer, primary_key=True, index=True)
    min_cases = Column(Integer, nullable=False)
    max_cases = Column(Integer, nullable=True) # Null = en adelante
    price = Column(Float, nullable=False)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CaseEvent(Base):
    __tablename__ = "case_events"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)

    event_date = Column(String(60), nullable=True)
    title = Column(String(255), nullable=True)
    detail = Column(Text, nullable=True)
    event_hash = Column(String(64), nullable=False)

    con_documentos = Column(Boolean, default=False)
    id_reg_actuacion = Column(BigInteger, nullable=True)
    cons_actuacion = Column(BigInteger, nullable=True)
    documentos_cache = Column(Text, nullable=True) # JSON con la lista de docs para velocidad
    
    case = relationship("Case", back_populates="events")
    is_current = Column(Boolean, default=True)

    version = Column(Integer, default=1)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("case_id", "event_hash", name="uq_case_event"),
    )


class InvalidRadicado(Base):
    """Radicados que no se encontraron en Rama Judicial"""
    __tablename__ = "invalid_radicados"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    radicado = Column(String(23), index=True, nullable=False)
    motivo = Column(String(255), default="No encontrado en Rama Judicial")
    intentos = Column(Integer, default=1)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("company_id", "radicado", name="uq_invalid_radicado_company"),
    )


class NotificationConfig(Base):
    """Configuración de notificaciones por correo"""
    __tablename__ = "notification_config"

    id = Column(Integer, primary_key=True, index=True)

    smtp_host = Column(String(255), default="smtp.gmail.com")
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(255), nullable=True)
    smtp_pass = Column(String(255), nullable=True)
    smtp_from = Column(String(255), nullable=True)

    notification_emails = Column(Text, nullable=True)

    is_active = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NotificationLog(Base):
    """Historial de notificaciones enviadas"""
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)

    sent_at = Column(DateTime, server_default=func.now(), nullable=False)
    recipients = Column(Text, nullable=True)
    subject = Column(String(500), nullable=True)
    cases_count = Column(Integer, default=0)
    status = Column(String(50), default="sent")
    error_message = Column(Text, nullable=True)


# --- RBAC y Multiempresa (SaaS) ---

class Company(Base):
    """Organizaciones/Empresas (Tenants)"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    nit = Column(String(50), nullable=True)
    logo_base64 = Column(Text, nullable=True)
    estado = Column(String(50), default="activo") # activa, suspendida_pago, inactiva, demo, vencida
    limite_usuarios = Column(Integer, default=5)
    
    suspension_reason = Column(Text, nullable=True)
    suspended_at = Column(DateTime, nullable=True)
    suspended_by = Column(Integer, nullable=True)
    reactivated_at = Column(DateTime, nullable=True)
    reactivated_by = Column(Integer, nullable=True)
    payment_status = Column(String(50), default="al_dia") # al_dia, en_mora, suspendido, exonerado, demo
    last_payment_date = Column(DateTime, nullable=True)
    next_payment_due = Column(Date, nullable=True)
    billing_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    users = relationship("User", back_populates="company")

class Role(Base):
    """Roles de usuarios"""
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False) # ej: SUPERADMIN, COMPANY_ADMIN, OPERATOR
    description = Column(String(255), nullable=True)

class Permission(Base):
    """Permisos granulares"""
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False) # ej: casos.ver, publicaciones.aprobar

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    """Usuarios del sistema"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True) # Nullable para el SuperAdmin root
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True) # Permitir nulo inicialmente para migracion
    hashed_password = Column(String(255), nullable=False)
    nombre = Column(String(255), nullable=True)       # nombre visible
    telefono = Column(String(50), nullable=True)     # contacto para reportes
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_superadmin = Column(Boolean, default=False)
    role = Column(String(100), default="USER")
    cases_view_scope = Column(String(50), default="OWN")
    sync_with_clickup = Column(Boolean, default=True, nullable=False)
    clickup_api_token = Column(String(255), nullable=True)
    
    company = relationship("Company", back_populates="users")
    roles = relationship("Role", secondary=user_roles, backref="users")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PasswordResetToken(Base):
    """Tokens temporales para recuperación de contraseña"""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    ip_request = Column(String(100), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    user = relationship("User", backref="reset_tokens")


class CasePublication(Base):
    """Publicaciones procesales (Estados/Edictos) del portal nuevo"""
    __tablename__ = "case_publications"
    __table_args__ = (
        UniqueConstraint('case_id', 'source_id', name='uq_case_publication_case_source'),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)

    fecha_publicacion = Column(Date, nullable=True)
    tipo_publicacion = Column(String(255), nullable=True)
    descripcion = Column(Text, nullable=True)
    documento_url = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)     # URL original del portal
    source_id = Column(String(255), unique=False, index=True, nullable=True) # ID único del portal

    # Nuevos campos para validación y detalle
    url_fuente_principal = Column(Text, nullable=True)
    tipo_fuente_principal = Column(String(100), nullable=True)
    texto_fuente_principal = Column(Text, nullable=True)
    validada_por_fuente_principal = Column(Boolean, default=False, nullable=True)
    numero_estado = Column(String(100), nullable=True)
    fecha_estado_electronico = Column(Date, nullable=True)
    url_resumen_publicacion = Column(Text, nullable=True)
    url_cuadro = Column(Text, nullable=True)
    url_providencia = Column(Text, nullable=True)
    documentos_complementarios = Column(Text, nullable=True) # JSON serializado
    match_fuerte = Column(Boolean, default=False, nullable=True)
    match_type = Column(String(100), nullable=True)
    motivo_match = Column(Text, nullable=True)
    observacion = Column(Text, nullable=True)

    # Campos de Validación Estricta
    estado_validacion = Column(String(50), default="requiere_revision", nullable=True) # validado, requiere_revision, descartado
    match_score = Column(Integer, default=0, nullable=True)
    texto_bloque_match = Column(Text, nullable=True)
    motivo_descarte = Column(Text, nullable=True)
    fuente_principal_validada = Column(Boolean, default=False, nullable=True)
    requiere_revision = Column(Boolean, default=True, nullable=True)
    elementos_detectados = Column(Text, nullable=True) # JSON
    documento_nombre = Column(Text, nullable=True)
    extraction_quality = Column(String(50), nullable=True)
    validated_at = Column(DateTime, nullable=True)
    
    # Trazabilidad de validación/descarte manual
    validado_manual = Column(Boolean, default=False, nullable=True)
    aprobado_por_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    descartado_manual = Column(Boolean, default=False, nullable=True)
    descartado_por_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    discarded_at = Column(DateTime, nullable=True)
    observacion_revision = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AuditLog(Base):
    """Registro de acciones de auditoría (para trazabilidad y compliance)"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    accion = Column(String(100), nullable=False, index=True) # ej: APPROVE_PUBLICATION
    entidad = Column(String(100), nullable=True, index=True) # ej: CasePublication
    entidad_id = Column(Integer, nullable=True, index=True)
    
    ip = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True) # Detalles extra (ej: motivo_descarte)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class CasePublicationSearch(Base):
    """Historial y estado de las búsquedas de publicaciones procesales"""
    __tablename__ = "publicaciones_busquedas"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    radicado = Column(String(60), index=True, nullable=False)
    fecha_actuacion = Column(Date, nullable=False)
    fecha_inicio_busqueda = Column(Date, nullable=False)
    fecha_fin_busqueda = Column(Date, nullable=False)
    despacho_codigo = Column(String(20), nullable=True)
    estado = Column(String(50), default="pendiente", nullable=False)
    estado_busqueda = Column(String(50), default="pendiente", nullable=False)
    fecha_ultima_busqueda = Column(DateTime, nullable=True)
    intento_manual = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    debug = Column(Text, nullable=True)
    
    # Nuevos campos para Background Worker Queue
    mes_busqueda = Column(String(20), index=True, nullable=True)
    prioridad = Column(Integer, default=0, index=True)
    intentos = Column(Integer, default=0)
    ultimo_error = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(100), nullable=True)
    next_retry_at = Column(DateTime, index=True, nullable=True)
    force = Column(Boolean, default=False)
    source_trigger = Column(String(100), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint('company_id', 'radicado', 'mes_busqueda', name='uix_pub_search_company_radicado_mes'),
        Index('idx_pub_search_queue_worker', 'estado', 'prioridad', 'created_at'),
        Index('idx_pub_search_retry', 'estado', 'next_retry_at'),
    )


class SearchJob(Base):
    """Trabajos de búsqueda masiva (nombres o radicados)"""
    __tablename__ = "search_jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    job_type = Column(String(50), nullable=False) # 'name', 'radicado'
    status = Column(String(50), default="pending") # 'pending', 'processing', 'completed', 'failed'
    
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    is_imported = Column(Boolean, default=False)
    
    # Almacena los resultados encontrados (radicados, etc) antes de importar
    results_json = Column(Text, nullable=True) 
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# =========================
# GESTOR DE PROYECTOS (ESTILO CLICKUP)
# =========================

class Workspace(Base):
    """Ambientes principales de trabajo (Ej: Civil, Laboral, FNA)"""
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    visibility = Column(String(50), default="TEAM_COLLABORATION")
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Referencia a ClickUp para sincronización
    clickup_id = Column(String(100), unique=True, index=True, nullable=True)
    
    folders = relationship("Folder", back_populates="workspace", cascade="all, delete-orphan")
    lists = relationship("ProjectList", back_populates="workspace", cascade="all, delete-orphan")
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class WorkspaceMember(Base):
    """Miembros de un ambiente y sus permisos"""
    __tablename__ = "workspace_members"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # ADMIN, EDITOR, VIEWER
    role = Column(String(50), default="VIEWER")
    
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
    )


class Folder(Base):
    """Carpetas dentro de un Ambiente"""
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    
    # Referencia a ClickUp para sincronización
    clickup_id = Column(String(100), unique=True, index=True, nullable=True)

    workspace = relationship("Workspace", back_populates="folders")
    lists = relationship("ProjectList", back_populates="folder", cascade="all, delete-orphan")
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ProjectList(Base):
    """Listas de tareas (Ej: Pendientes, Revisión, Finalizados)"""
    __tablename__ = "project_lists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    
    # Referencia a ClickUp para sincronización
    clickup_id = Column(String(100), unique=True, index=True, nullable=True)

    folder = relationship("Folder", back_populates="lists")
    workspace = relationship("Workspace", back_populates="lists")
    tasks = relationship("Task", back_populates="project_list", cascade="all, delete-orphan")
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# =========================
# ASOCIACIONES DE ETIQUETAS
# =========================
task_tags = Table(
    'task_tags',
    Base.metadata,
    Column('task_id', Integer, ForeignKey('tasks.id', ondelete="CASCADE"), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete="CASCADE"), primary_key=True)
)

class Tag(Base):
    """Etiquetas personalizadas para clasificación en proyectos."""
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    color = Column(String(50), default="#3b82f6") # Hex code
    
    tasks = relationship("Task", secondary=task_tags, back_populates="tags")


class Task(Base):
    """Tareas individuales con jerarquía (soporta subtareas)"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    
    # To do, In Progress, Done, etc.
    status = Column(String(50), default="To Do")
    priority = Column(String(50), nullable=True) # Low, Normal, High, Urgent
    
    due_date = Column(DateTime, nullable=True)
    
    list_id = Column(Integer, ForeignKey("project_lists.id", ondelete="CASCADE"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Vinculación clave con los expedientes/casos jurídicos
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Soporte para subtareas (recursivo)
    parent_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    subtasks = relationship("Task", backref=backref("parent", remote_side="Task.id"), cascade="all, delete-orphan")
    
    # Referencia a ClickUp para evitar duplicados en importación
    clickup_id = Column(String(100), unique=True, index=True, nullable=True)
    assignee_name = Column(String(200), nullable=True) # Nombre real de ClickUp
    custom_fields = Column(Text, nullable=True) # JSON con campos personalizados
    
    project_list = relationship("ProjectList", back_populates="tasks")
    case = relationship("Case", back_populates="tasks")
    
    # Colecciones de checklist y tags
    checklists = relationship("TaskChecklistItem", back_populates="task", cascade="all, delete-orphan")
    comments = relationship("TaskComment", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=task_tags, back_populates="tasks")
    attachments = relationship("TaskAttachment", cascade="all, delete-orphan")
    # Soporte para múltiples responsables
    assignees = relationship("User", secondary=task_assignees)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class TaskComment(Base):
    """Comentarios en las tareas"""
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    user_name = Column(String(255), nullable=True) # Nombre del autor (ej: de ClickUp)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class TaskChecklistItem(Base):
    """Sub-elementos tipo checklist rápidos dentro de una tarea"""
    __tablename__ = "task_checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    content = Column(String(500), nullable=False)
    is_completed = Column(Boolean, default=False)
    
    task = relationship("Task", back_populates="checklists")
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class TaskAttachment(Base):
    """Archivos o imágenes adjuntas a una tarea"""
    __tablename__ = "task_attachments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class IntegrationConfig(Base):
    """Configuración de integraciones externas (Cally, etc)"""
    __tablename__ = "integration_config"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    service_name = Column(String(100), unique=True, index=True, nullable=False)
    clickup_id = Column(String(100), unique=True, index=True, nullable=True)
    api_key = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    settings = Column(Text, nullable=True) # JSON flexible

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class CaseSourceCheck(Base):
    """Historial y logs de consultas de radicados en micrositios oficiales"""
    __tablename__ = "case_source_checks"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    radicado = Column(String(100), nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    source_url = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, default="pending", index=True) # pending, success, no_result, error, skipped, unsupported
    checked_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    records_found = Column(Integer, default=0)
    raw_summary = Column(Text, nullable=True) # JSON raw response summary

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class CaseSearchSourceResult(Base):
    """Historial y logs de consultas de radicados en el motor fallback con fuentes alternativas"""
    __tablename__ = "case_search_source_results"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    radicado = Column(String(60), index=True, nullable=False)
    fuente = Column(String(100), nullable=True)
    tipo_fuente = Column(String(100), nullable=True)
    url = Column(String(500), nullable=True)
    encontrado = Column(Boolean, default=False, nullable=False)
    confianza = Column(Integer, default=0, nullable=True)
    estado = Column(String(50), nullable=True)
    mensaje = Column(Text, nullable=True)
    datos_extraidos_json = Column(Text, nullable=True)
    raw_response = Column(String(50000), nullable=True) # Limit response size to 50k chars
    error_type = Column(String(100), nullable=True)
    http_status = Column(Integer, nullable=True)
    duration_ms = Column(Integer, default=0)
    source_order = Column(Integer, nullable=True)
    force = Column(Boolean, default=False, nullable=True)
    requiere_revision = Column(Boolean, default=False, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    case = relationship("Case", backref=backref("search_source_results", cascade="all, delete-orphan"))
    user = relationship("User", backref=backref("case_searches"))


class ExcelImportJob(Base):
    """Seguimiento de importaciones de Excel"""
    __tablename__ = "excel_import_jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    usuario_username = Column(String(255), nullable=True)
    estado = Column(String(50), default="pendiente", nullable=False) # 'pendiente', 'procesando', 'finalizado', 'error'
    total_filas = Column(Integer, default=0)
    filas_procesadas = Column(Integer, default=0)
    filas_creadas = Column(Integer, default=0)
    filas_actualizadas = Column(Integer, default=0)
    errores_parciales = Column(Text, nullable=True)

    fecha_inicio = Column(DateTime, server_default=func.now(), nullable=False)
    fecha_fin = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)