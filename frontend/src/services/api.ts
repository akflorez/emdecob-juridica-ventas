const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export type ApiErrorPayload = { detail?: any } | any;

export class ApiError extends Error {
  status: number;
  payload?: ApiErrorPayload;

  constructor(status: number, message: string, payload?: ApiErrorPayload) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

function getToken() {
  return localStorage.getItem("emdecob_auth_token");
}

async function parseError(res: Response) {
  const text = await res.text().catch(() => "");
  try {
    return text ? JSON.parse(text) : undefined;
  } catch {
    return text;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  let cleanPath = path.startsWith('/') ? path : `/${path}`;

  // Asegurar que la petición vaya a /api/ para pasar por la regla de Proxy Nginx
  if (!cleanPath.startsWith('/api/') && cleanPath !== '/api') {
    cleanPath = `/api${cleanPath}`;
  }

  const headers = new Headers(options.headers || {});
  const isFormData = options.body instanceof FormData;

  if (!isFormData) headers.set("Content-Type", "application/json");

  if (auth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(cleanPath, { ...options, headers });

  if (!res.ok) {
    const payload = await parseError(res);
    const msg =
      (payload && (payload.detail || payload.message)) || `Error ${res.status}`;
    throw new ApiError(res.status, String(msg), payload);
  }

  if (res.status === 204) return undefined as T;

  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;

  return (await res.text()) as unknown as T;
}

/** ---------------------------
 * AUTH
 * -------------------------- */
export type LoginResponse = { token: string; user: User };

export function login(username: string, password: string) {
  return apiFetch<LoginResponse>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ username, password }) },
    false
  );
}

export function registerCompany(data: any) {
  return apiFetch<{ ok: boolean; message: string }>(
    "/auth/register-company",
    { method: "POST", body: JSON.stringify(data) },
    false
  );
}

export function forgotPassword(email: string) {
  return apiFetch<{ ok: boolean; message: string }>(
    "/auth/forgot-password",
    { method: "POST", body: JSON.stringify({ email }) },
    false
  );
}

export function resetPassword(data: any) {
  return apiFetch<{ message: string }>(
    "/auth/reset-password",
    { method: "POST", body: JSON.stringify(data) },
    false
  );
}

export function changePassword(data: any) {
  return apiFetch<{ message: string }>(
    "/auth/change-password",
    { method: "POST", body: JSON.stringify(data) },
    true
  );
}

export type User = {
  id: number;
  username: string;
  email?: string;
  nombre?: string;
  is_active: boolean;
  is_admin: boolean;
  is_superadmin?: boolean;
  company_id?: number | null;
  role?: string;
  roles?: string[];
  rol?: string;
};

export function getUsers() {
  return apiFetch<User[]>("/auth/users");
}

/** ---------------------------
 * ESTADÍSTICAS
 * -------------------------- */
export type StatsResponse = {
  total_validos: number;
  total_pendientes: number;
  total_invalidos: number;
  total_no_leidos: number;
  total_actualizados_hoy: number;
};

export function getStats() {
  return apiFetch<StatsResponse>("/stats");
}

/** ---------------------------
 * CONSULTA POR RADICADO
 * -------------------------- */
export type CaseByRadicadoResponse = {
  id: number;
  radicado: string;
  id_proceso?: string | null;
  demandante?: string | null;
  demandado?: string | null;
  juzgado?: string | null;
  alias?: string | null;
  fecha_radicacion?: string | null;
  ultima_actuacion?: string | null;
  last_check_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  unread?: boolean;
  has_documents?: boolean;
  note?: string | null;
  is_active?: boolean;
  company_id?: number | null;
  
  despacho?: string | null;
  clase_proceso?: string | null;
  tipo_proceso?: string | null;
  estado?: string | null;
  ponente_juez?: string | null;
  departamento?: string | null;
  municipio?: string | null;
  ubicacion?: string | null;
  fuente_encontrado?: string | null;
  url_fuente?: string | null;
  metodo_busqueda?: string | null;
  confianza_busqueda?: number | null;
  encontrado_en_fuente_alternativa?: boolean;
  requiere_revision?: boolean;
};

export function getCaseByRadicado(radicado: string) {
  const r = encodeURIComponent(radicado.trim());
  return apiFetch<CaseByRadicadoResponse[]>(`/cases/by-radicado/${r}`);
}

export function getCaseById(id: number) {
  return apiFetch<CaseByRadicadoResponse>(`/cases/id/${id}`);
}

/** ---------------------------
 * EVENTOS / ACTUACIONES POR RADICADO
 * -------------------------- */
export type EventOut = {
  id_reg_actuacion?: number | null;
  cons_actuacion?: number | null;
  llave_proceso?: string | null;
  event_date?: string | null;
  title?: string | null;
  detail?: string | null;
  fecha_inicio?: string | null;
  fecha_fin?: string | null;
  fecha_registro?: string | null;
  con_documentos?: boolean;
  cant?: number | null;
};

export function getCaseEvents(radicado: string) {
  const r = encodeURIComponent(radicado.trim());
  return apiFetch<{ items: EventOut[]; total?: number; warning?: string }>(`/cases/by-radicado/${r}/events`);
}

export function getCaseEventsById(id: number) {
  return apiFetch<{ items: EventOut[]; total?: number; warning?: string }>(`/cases/id/${id}/events`);
}

/** ---------------------------
 * DESCARGAR ACTUACIONES EXCEL (un radicado)
 * -------------------------- */
export function downloadEventsExcel(radicado: string) {
  const cleanBaseUrl = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
  const r = encodeURIComponent(radicado.trim());
  window.open(`${cleanBaseUrl}/cases/by-radicado/${r}/events.xlsx`, "_blank");
}

export function downloadEventsByIdExcel(id: number) {
  const cleanBaseUrl = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
  window.open(`${cleanBaseUrl}/cases/id/${id}/events.xlsx`, "_blank");
}

/** ---------------------------
 * DESCARGAR ACTUACIONES MÚLTIPLES
 * -------------------------- */
export async function downloadMultipleEventsExcel(radicados: string[]) {
  const cleanBaseUrl = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
  const token = localStorage.getItem("token") || sessionStorage.getItem("token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const response = await fetch(`${cleanBaseUrl}/cases/events/download-multiple`, {
    method: "POST",
    headers,
    body: JSON.stringify(radicados),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Error descargando archivo");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `actuaciones_multiple_${new Date().toISOString().split("T")[0]}.xlsx`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  a.remove();
}

/** ---------------------------
 * IMPORTAR EXCEL
 * -------------------------- */
export type ImportExcelResponse = {
  ok: boolean;
  created: number;
  updated: number;
  skipped: number;
  skipped_list?: Array<{ radicado: string; motivo: string } | string>;
  invalid_count: number;
  message?: string;
};

export function importExcel(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return apiFetch<ImportExcelResponse>("/cases/import-excel", { method: "POST", body: fd });
}

export function bulkDeleteExcel(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return apiFetch<{ ok: boolean; deleted_cases: number; message: string }>("/cases/bulk-delete-excel", {
    method: "POST",
    body: fd,
  });
}

/** ---------------------------
 * DESCARGAR REPORTE DE INVÁLIDOS (desde importar)
 * -------------------------- */
export function downloadInvalidReport(invalidList: { radicado: string; motivo: string }[]) {
  const header = "Radicado,Motivo\n";
  const rows = invalidList.map((item) => `${item.radicado},"${item.motivo}"`).join("\n");
  const csv = header + rows;

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `radicados_no_encontrados_${new Date().toISOString().split("T")[0]}.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  a.remove();
}

/** ---------------------------
 * LISTAR CASOS
 * -------------------------- */
export type CaseRow = {
  id: number;
  radicado: string;
  demandante?: string | null;
  demandado?: string | null;
  juzgado?: string | null;
  alias?: string | null;
  fecha_radicacion?: string | null;
  ultima_actuacion?: string | null;
  last_check_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  unread?: boolean;
  id_proceso?: string | null;
  has_documents?: boolean;
  cedula?: string | null;
  abogado?: string | null;
  has_tasks?: boolean;
  
  despacho?: string | null;
  clase_proceso?: string | null;
  tipo_proceso?: string | null;
  estado?: string | null;
  ponente_juez?: string | null;
  departamento?: string | null;
  municipio?: string | null;
  ubicacion?: string | null;
  fuente_encontrado?: string | null;
  url_fuente?: string | null;
  metodo_busqueda?: string | null;
  confianza_busqueda?: number | null;
  encontrado_en_fuente_alternativa?: boolean;
  requiere_revision?: boolean;
};

export type CasesResponse = {
  items: CaseRow[];
  total: number;
  page: number;
  page_size: number;
  unread_count?: number;
};

export type GetCasesParams = {
  search?: string;
  juzgado?: string;
  mes_actuacion?: string;
  solo_validos?: boolean;
  solo_pendientes?: boolean;
  solo_no_leidos?: boolean;
  solo_leidos?: boolean;
  solo_actualizados_hoy?: boolean;
  solo_retirados?: boolean;
  con_documentos?: boolean;
  cedula?: string;
  abogado?: string;
  page?: number;
  page_size?: number;
};

export function getCases(params: GetCasesParams) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.juzgado) qs.set("juzgado", params.juzgado);
  if (params.mes_actuacion) qs.set("mes_actuacion", params.mes_actuacion);
  if (params.solo_validos !== undefined) qs.set("solo_validos", String(params.solo_validos));
  if (params.solo_pendientes) qs.set("solo_pendientes", "true");
  if (params.solo_no_leidos) qs.set("solo_no_leidos", "true");
  if (params.solo_leidos) qs.set("solo_leidos", "true");
  if (params.solo_actualizados_hoy) qs.set("solo_actualizados_hoy", "true");
  if (params.solo_retirados) qs.set("solo_retirados", "true");
  if (params.con_documentos !== undefined) qs.set("con_documentos", String(params.con_documentos));
  if (params.cedula) qs.set("cedula", params.cedula);
  if (params.abogado) qs.set("abogado", params.abogado);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return apiFetch<CasesResponse>(`/cases${q ? `?${q}` : ""}`);
}


/** ---------------------------
 * LISTAR ABOGADOS (SUGERENCIAS)
 * -------------------------- */
export function getAbogados() {
  return apiFetch<string[]>("/cases/abogados");
}

/** ---------------------------
 * DESCARGAR CASOS EXCEL
 * -------------------------- */
export async function downloadCasesExcel(params: {
  search?: string;
  juzgado?: string;
  abogado?: string;
  cedula?: string;
  mes_actuacion?: string;
  solo_no_leidos?: boolean;
  solo_actualizados_hoy?: boolean;
  solo_retirados?: boolean;
  company_id?: number;
  page?: number;
  page_size?: number;
  ignore_filters?: boolean;
}) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.juzgado) qs.set("juzgado", params.juzgado);
  if (params.abogado) qs.set("abogado", params.abogado);
  if (params.cedula) qs.set("cedula", params.cedula);
  if (params.mes_actuacion) qs.set("mes_actuacion", params.mes_actuacion);
  if (params.solo_no_leidos) qs.set("solo_no_leidos", "true");
  if (params.solo_actualizados_hoy) qs.set("solo_actualizados_hoy", "true");
  if (params.solo_retirados) qs.set("solo_retirados", "true");
  if (params.page !== undefined) qs.set("page", String(params.page));
  if (params.page_size !== undefined) qs.set("page_size", String(params.page_size));
  if (params.ignore_filters) qs.set("ignore_filters", "true");
  if (params.company_id !== undefined) qs.set("company_id", String(params.company_id));
  const q = qs.toString();
  const token = getToken();

  const res = await fetch(`/api/cases/download?${q}${token ? `&token=${token}` : ""}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al exportar casos");
  }

  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = `casos_juricob_${new Date().toISOString().slice(0, 10)}.xlsx`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);
}

/** ---------------------------
 * ELIMINAR CASO
 * -------------------------- */
export function deleteCase(caseId: number) {
  return apiFetch<{ ok: boolean; message: string }>(`/cases/${caseId}`, {
    method: "DELETE",
  });
}

export function markCaseRead(caseId: number) {
  return apiFetch<{ ok: boolean; id: number }>(`/cases/${caseId}/mark-read`, {
    method: "POST",
  });
}

export function markCaseUnread(caseId: number) {
  return apiFetch<{ ok: boolean; id: number }>(`/cases/${caseId}/mark-unread`, {
    method: "POST",
  });
}

/** ---------------------------
 * MARCAR COMO LEÍDOS (varios)
 * -------------------------- */
export function markReadBulk(caseIds: number[]) {
  return apiFetch<{ ok: boolean; updated: number }>("/cases/mark-read-bulk", {
    method: "POST",
    body: JSON.stringify({ case_ids: caseIds }),
  });
}

export function markUnreadBulk(caseIds: number[]) {
  return apiFetch<{ ok: boolean; updated: number }>("/cases/mark-unread-bulk", {
    method: "POST",
    body: JSON.stringify({ case_ids: caseIds }),
  });
}

/** ---------------------------
 * MARCAR TODOS COMO LEÍDOS
 * -------------------------- */
export function markReadAll(params: {
  search?: string;
  juzgado?: string;
  abogado?: string;
  cedula?: string;
  mes_actuacion?: string;
  solo_no_leidos?: boolean;
  solo_actualizados_hoy?: boolean;
}) {
  return apiFetch<{ ok: boolean; updated: number; total: number }>("/cases/mark-read-all", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

/** ---------------------------
 * ACTUALIZAR TODOS LOS CASOS
 * -------------------------- */
export type RefreshAllResponse = {
  ok: boolean;
  total_cases?: number;
  checked?: number;
  updated_cases: number;
  cases_with_changes: {
    radicado: string;
    demandante?: string;
    demandado?: string;
    juzgado?: string;
  }[];
};

export function refreshAllCases() {
  return apiFetch<RefreshAllResponse>("/cases/refresh-all", { method: "POST" });
}

export type SyncAllPublicationsResponse = {
  ok: boolean;
  message: string;
  total: number;
};

export function syncAllPublications() {
  return apiFetch<SyncAllPublicationsResponse>("/cases/sync-all-publications", { method: "POST" });
}

/** ---------------------------
 * VALIDAR LOTE DE PENDIENTES
 * -------------------------- */
export type ValidateBatchResponse = {
  ok: boolean;
  processed: number;
  validated: number;
  not_found: number;
  remaining: number;
  message: string;
};

export function validateBatch(batchSize: number = 50) {
  return apiFetch<ValidateBatchResponse>(`/cases/validate-batch?batch_size=${batchSize}`, {
    method: "POST",
  });
}

/** ---------------------------
 * RADICADOS NO ENCONTRADOS
 * -------------------------- */
export type InvalidRadicado = {
  id: number;
  radicado: string;
  motivo: string;
  intentos: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type InvalidRadicadosResponse = {
  items: InvalidRadicado[];
  total: number;
  page: number;
  page_size: number;
};

export function getInvalidRadicados(params: { search?: string; page?: number; page_size?: number }) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return apiFetch<InvalidRadicadosResponse>(`/invalid-radicados${q ? `?${q}` : ""}`);
}

export function deleteInvalidRadicado(id: number) {
  return apiFetch<{ ok: boolean }>(`/invalid-radicados/${id}`, { method: "DELETE" });
}

export function retryInvalidRadicado(id: number) {
  return apiFetch<{ ok: boolean; found: boolean; message: string }>(
    `/invalid-radicados/${id}/retry`,
    { method: "POST" }
  );
}

export async function downloadInvalidRadicadosExcel() {
  const token = getToken();
  const res = await fetch(`/api/invalid-radicados/download${token ? `?token=${token}` : ""}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al exportar radicados no encontrados");
  }

  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = `radicados_no_encontrados_${new Date().toISOString().slice(0, 10)}.xlsx`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);
}

/** ---------------------------
 * RADICADOS NO ENCONTRADOS - OPERACIONES MASIVAS
 * -------------------------- */
export type RetryBatchInvalidResponse = {
  ok: boolean;
  processed: number;
  found: number;
  still_not_found: number;
  remaining: number;
  message: string;
};

export function retryBatchInvalidRadicados(batchSize: number = 20) {
  return apiFetch<RetryBatchInvalidResponse>(`/invalid-radicados/retry-batch?batch_size=${batchSize}`, {
    method: "POST",
  });
}

export function retryAllInvalidRadicados() {
  return apiFetch<RetryBatchInvalidResponse>("/invalid-radicados/retry-all", {
    method: "POST",
  });
}

export function deleteAllInvalidRadicados() {
  return apiFetch<{ ok: boolean; deleted: number; message: string }>("/invalid-radicados/delete-all", {
    method: "DELETE",
  });
}

/** ---------------------------
 * CONFIGURACIÓN DE NOTIFICACIONES
 * -------------------------- */
export type NotificationConfigResponse = {
  id: number;
  smtp_host: string;
  smtp_port: number;
  smtp_user?: string | null;
  smtp_from?: string | null;
  notification_emails?: string | null;
  is_active: boolean;
  has_password: boolean;
  updated_at?: string | null;
};

export type NotificationConfigUpdate = {
  smtp_host?: string;
  smtp_port?: number;
  smtp_user?: string;
  smtp_pass?: string;
  smtp_from?: string;
  notification_emails?: string;
  is_active?: boolean;
};

export function getNotificationConfig() {
  return apiFetch<NotificationConfigResponse>("/config/notifications");
}

export function updateNotificationConfig(data: NotificationConfigUpdate) {
  return apiFetch<{ ok: boolean; message: string }>("/config/notifications", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function testNotificationEmail(email: string) {
  return apiFetch<{ ok: boolean; message: string }>("/config/notifications/test", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function sendManualNotification() {
  return apiFetch<{ ok: boolean; sent: boolean; message: string; count: number }>(
    "/config/notifications/send-manual",
    { method: "POST" }
  );
}

export type NotificationLogItem = {
  id: number;
  sent_at?: string | null;
  recipients?: string | null;
  subject?: string | null;
  cases_count: number;
  status: string;
  error_message?: string | null;
};

export type NotificationLogsResponse = {
  items: NotificationLogItem[];
  total: number;
  page: number;
  page_size: number;
};

export function getNotificationLogs(page: number = 1, pageSize: number = 20) {
  return apiFetch<NotificationLogsResponse>(
    `/config/notifications/logs?page=${page}&page_size=${pageSize}`
  );
}

/** ---------------------------
 * BILLING & SUPERADMIN
 * -------------------------- */
export type BillingTier = {
  id?: number;
  min_cases: number;
  max_cases: number | null;
  price: number;
};

export type BillingSimulatorResult = {
  company_id: number;
  company_name: string;
  users_count: number;
  active_cases: number;
  applicable_tier: string;
  total_cost: number;
};

export function getBillingTiers() {
  return apiFetch<{ ok: boolean; tiers: BillingTier[] }>("/api/admin/billing/tiers");
}

export function updateBillingTiers(tiers: BillingTier[]) {
  return apiFetch<{ ok: boolean; message: string }>("/api/admin/billing/tiers", {
    method: "POST",
    body: JSON.stringify({ tiers }),
  });
}

export function getBillingSimulator() {
  return apiFetch<{ ok: boolean; simulator: BillingSimulatorResult[] }>("/api/admin/billing/simulator");
}

/** ---------------------------
 * DOCUMENTOS DE ACTUACIONES
 * Campo real confirmado por Network Inspector en la página oficial de Rama Judicial:
 *   - Endpoint: GET /api/v2/Proceso/DocumentosActuacion/{idRegActuacion}
 *   - Campo ID del documento: "idRegDocumento"  (NO idRegistroDocumento)
 *   - Campo nombre:           "nombre"
 *   - Campo descripción:      "descripcion"
 *   - Campo fecha:            "fechaCarga"
 * -------------------------- */
export type DocumentoActuacion = {
  // ✅ Campo real confirmado por inspección de red
  idRegDocumento?: number;
  // Fallbacks por si la API varía
  idRegistroDocumento?: number;
  idDocumento?: number;
  id?: number;
  // Datos del documento
  nombre?: string;
  nombreDocumento?: string;
  descripcion?: string;
  tipo?: string;
  fechaCarga?: string | null;
  fechaCargue?: string | null;
  // Campos internos de Rama Judicial
  idConexion?: number;
  consActuacion?: number;
  guidDocumento_SXXIN?: string;
};

export type DocumentosActuacionResponse = {
  items: DocumentoActuacion[];
  total?: number;
};

export function getDocumentosActuacion(radicado: string, idRegActuacion: number) {
  const r = encodeURIComponent(radicado.trim());
  return apiFetch<DocumentosActuacionResponse>(
    `/cases/events/${idRegActuacion}/documents?llave_proceso=${r}`
  );
}

export function downloadDocumento(doc: DocumentoActuacion) {
  const cleanBaseUrl = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;

  // ✅ Priorizar el campo real confirmado: idRegDocumento
  const idDocumento =
    doc.idRegDocumento ??
    doc.idRegistroDocumento ??
    doc.idDocumento ??
    doc.id ??
    null;

  if (!idDocumento) {
    console.error("El documento no tiene un ID válido.", doc);
    return;
  }

  const token = localStorage.getItem("token") || localStorage.getItem("access_token");
  const url = `${cleanBaseUrl}/documentos/${idDocumento}/descargar${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  window.open(url, "_blank");
}

/** ---------------------------
 * VALIDACIÓN AUTOMÁTICA
 * -------------------------- */
export type ValidationStatus = {
  running: boolean;
  processed: number;
  validated: number;
  not_found: number;
  errors: number;
  total: number;
  started_at?: string | null;
  last_update?: string | null;
};

export function getValidationStatus() {
  return apiFetch<ValidationStatus>("/validation/status");
}

export function startAutoValidation(batchSize: number = 20) {
  return apiFetch<{ ok: boolean; message: string; stats?: ValidationStatus }>(
    `/validation/start?batch_size=${batchSize}`,
    { method: "POST" }
  );
}

export function stopAutoValidation() {
  return apiFetch<{ ok: boolean; message: string }>("/validation/stop", {
    method: "POST",
  });
}

export function startRetryInvalid() {
  return apiFetch<{ ok: boolean; message: string; stats?: ValidationStatus }>(
    "/validation/retry-invalid/start",
    { method: "POST" }
  );
}

/** ---------------------------
 * AUTO-REFRESH STATUS
 * -------------------------- */
export type AutoRefreshStatus = {
  running: boolean;
  scheduled_hours: string;
  last_run?: string | null;
  next_run?: string | null;
  last_result?: {
    ok?: boolean;
    checked?: number;
    updated_cases?: number;
    errors?: number;
  } | null;
};

export function getAutoRefreshStatus() {
  return apiFetch<AutoRefreshStatus>("/auto-refresh/status");
}

export function runAutoRefreshNow() {
  return apiFetch<{ ok: boolean; message: string }>("/auto-refresh/run-now", {
    method: "POST",
  });
}

/** ---------------------------
 * PUBLICACIONES PROCESALES
 * -------------------------- */
export type CasePublication = {
  id: number;
  case_id: number;
  fecha_publicacion?: string | null;
  tipo_publicacion?: string | null;
  descripcion?: string | null;
  documento_url?: string | null;
  source_url?: string | null;
  source_id?: string | null;
  created_at?: string | null;
  
  url_fuente_principal?: string | null;
  tipo_fuente_principal?: string | null;
  texto_fuente_principal?: string | null;
  validada_por_fuente_principal?: boolean;
  numero_estado?: string | null;
  fecha_estado_electronico?: string | null;
  url_resumen_publicacion?: string | null;
  url_cuadro?: string | null;
  url_providencia?: string | null;
  documentos_complementarios?: string | null;
  match_fuerte?: boolean;
  match_type?: string | null;
  motivo_match?: string | null;
  observacion?: string | null;
  
  // Validation fields
  estado_validacion?: "validado" | "requiere_revision" | "descartado";
  match_score?: number;
  texto_bloque_match?: string | null;
  motivo_descarte?: string | null;
  fuente_principal_validada?: boolean;
  requiere_revision?: boolean;
  elementos_detectados?: any;
  documento_nombre?: string | null;
  extraction_quality?: string | null;
  // Auditoría Manual
  validado_manual?: boolean;
  aprobado_por_id?: number | null;
  approved_at?: string | null;
  descartado_manual?: boolean;
  descartado_por_id?: number | null;
  discarded_at?: string | null;
  observacion_revision?: string | null;
};

export function getCasePublications(radicado: string) {
  const r = encodeURIComponent(radicado.trim());
  return apiFetch<{
    items: CasePublication[];
    company_id?: number | null;
    busquedas?: any[];
    estado_busqueda?: string;
    sync_pub_status?: string;
    sync_pub_progress?: number;
  }>(`/cases/${r}/publicaciones`);
}

export function getCasePublicationsById(id: number) {
  return apiFetch<{
    items: any[];
    company_id?: number | null;
    busquedas?: any[];
    estado_busqueda?: string;
    sync_pub_status?: string;
    sync_pub_progress?: number;
  }>(`/cases/id/${id}/publicaciones`);
}


export function refreshCasePublications(radicado: string) {
  const r = encodeURIComponent(radicado.trim());
  return apiFetch<{ ok: boolean; message?: string; items?: CasePublication[] }>(`/cases/${r}/refresh-publicaciones`, {
    method: "POST",
  });
}

export function refreshCasePublicationsById(id: number) {
  const r = id;
  return apiFetch<{ ok: boolean; message?: string; items?: CasePublication[] }>(`/cases/id/${r}/refresh-publicaciones`, {
    method: "POST",
  });
}

export function descartarPublicacion(pubId: number, motivo: string, observacion?: string) {
  return apiFetch<{ ok: boolean; message: string; id: number }>(`/publicaciones/${pubId}/descartar`, {
    method: "POST",
    body: JSON.stringify({ motivo, observacion }),
  });
}

export function aceptarPublicacion(pubId: number, observacion?: string) {
  return apiFetch<{ ok: boolean; message: string; id: number }>(`/publicaciones/${pubId}/aprobar`, {
    method: "POST",
    body: JSON.stringify({ observacion }),
  });
}

/** ---------------------------
 * BÚSQUEDA MASIVA (NAMES / RADICADOS)
 * -------------------------- */
export interface SearchJobResponse {
  id: number;
  type: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_items: number;
  processed_items: number;
  is_imported: boolean;
  results: any[];
  error?: string;
  created_at?: string;
}

export function uploadNamesSearch(file: File, fromDate?: string, toDate?: string) {
  const fd = new FormData();
  fd.append("file", file);
  const qs = new URLSearchParams();
  if (fromDate) qs.set("from_date", fromDate);
  if (toDate) qs.set("to_date", toDate);
  const q = qs.toString();
  return apiFetch<{ job_id: number }>(`/search/names/upload${q ? `?${q}` : ""}`, { method: "POST", body: fd });
}

export function getSearchJob(jobId: number) {
  return apiFetch<SearchJobResponse>(`/search/jobs/${jobId}`, { cache: "no-store" });
}

export function getLatestSearchJob() {
  return apiFetch<SearchJobResponse | null>("/search/latest", { cache: "no-store" });
}

export function importSearchResults(jobId: number, selectedIndices: number[]) {
  return apiFetch<{ ok: boolean; imported: number }>(`/search/jobs/${jobId}/import`, {
    method: "POST",
    body: JSON.stringify({ indices: selectedIndices }),
  });
}

export function cancelSearchJob(jobId: number) {
  return apiFetch<{ ok: boolean; status: string }>(`/search/jobs/${jobId}/cancel`, {
    method: "POST"
  });
}

export function downloadSearchResultsExcel(jobId: number) {
  const cleanBaseUrl = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
  const token = getToken();
  
  const downloadUrl = `${cleanBaseUrl}/search/jobs/${jobId}/export${token ? `?token=${token}` : ""}`;
  
  window.location.assign(downloadUrl);
}

/** ---------------------------
 * PROYECTOS Y TAREAS (CLICKUP CLONE / GESTIÓN INTERNA)
 * -------------------------- */

export type WorkspaceList = {
  id: number;
  name: string;
  folder_id?: number;
};

export type WorkspaceFolder = {
  id: number;
  name: string;
  lists: WorkspaceList[];
};

export type Workspace = {
  id: number;
  name: string;
  visibility: string;
  folders: WorkspaceFolder[];
  lists: WorkspaceList[];
};

export type ChecklistItem = {
  id: number;
  content: string;
  is_completed: boolean;
};

export type TaskComment = {
  id: number;
  content: string;
  user_id?: number;
  user_name?: string;
  created_at: string;
};

export type Attachment = {
  id: number;
  name: string;
  file_path: string;
  file_type?: string;
  created_at: string;
};

export function addWorkspaceMember(workspaceId: number, userId: number, role: string = "VIEWER") {
  return apiFetch<{ ok: boolean }>(`/projects/workspaces/${workspaceId}/members`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  });
}

export type Tag = {
  id: number;
  name: string;
  color?: string;
};

export type Task = {
  id: number;
  title: string;
  description?: string;
  status: string;
  priority?: string;
  assignee_id?: number;
  list_id: number;
  due_date?: string;
  case_id?: number;
  parent_id?: number;
  created_at: string;
  clickup_id?: string;
  checklists?: ChecklistItem[];
  subtasks?: Task[];
  comments?: TaskComment[];
  assignee_name?: string;
  tags?: Tag[];
  attachments?: Attachment[];
  custom_fields?: string; // JSON string
  assignees?: User[];
  case_radicado?: string;
  case_demandante?: string;
  case_demandado?: string;
};

export function getWorkspaces() {
  return apiFetch<Workspace[]>("/projects/workspaces");
}

export function getTags() {
  return apiFetch<Tag[]>("/projects/tags");
}

export function createTag(name: string, color?: string) {
  return apiFetch<Tag>("/projects/tags", { method: "POST", body: JSON.stringify({ name, color }) });
}

export function updateTag(tagId: number, name: string, color?: string) {
  return apiFetch<Tag>(`/projects/tags/${tagId}`, { method: "PUT", body: JSON.stringify({ name, color }) });
}

export function deleteTag(tagId: number) {
  return apiFetch<{ ok: boolean; message: string }>(`/projects/tags/${tagId}`, { method: "DELETE" });
}

export function createQuickUser(name: string) {
  return apiFetch<User>("/projects/quick-users", { method: "POST", body: JSON.stringify({ name }) });
}

export function getStatuses() {
  return apiFetch<string[]>("/projects/statuses");
}

export function getTasks(params: { list_id?: number; status?: string; assignee_id?: number; radicado?: string }) {
  const qs = new URLSearchParams();
  if (params.list_id) qs.set("list_id", String(params.list_id));
  if (params.status) qs.set("status", params.status);
  if (params.assignee_id) qs.set("assignee_id", String(params.assignee_id));
  if (params.radicado) qs.set("radicado", params.radicado);
  return apiFetch<Task[]>(`/projects/tasks?${qs.toString()}`);
}

export function getCaseTasks(caseId: number) {
  return apiFetch<Task[]>(`/cases/id/${caseId}/tasks`);
}

export function createWorkspace(data: { name: string; description?: string; visibility?: string }) {
  return apiFetch<Workspace>("/projects/workspaces", { method: "POST", body: JSON.stringify(data) });
}

export function updateWorkspace(workspaceId: number, data: { name?: string; description?: string; visibility?: string }) {
  return apiFetch<Workspace>(`/projects/workspaces/${workspaceId}`, { method: "PUT", body: JSON.stringify(data) });
}

export function createFolder(data: { name: string; workspace_id: number }) {
  return apiFetch<WorkspaceFolder>("/projects/folders", { method: "POST", body: JSON.stringify(data) });
}

export function createList(data: { name: string; folder_id?: number; workspace_id: number }) {
  return apiFetch<WorkspaceList>("/projects/lists", { method: "POST", body: JSON.stringify(data) });
}

export function deleteWorkspace(workspaceId: number) {
  return apiFetch<{ ok: boolean; message: string }>(`/projects/workspaces/${workspaceId}`, { method: "DELETE" });
}

export function updateFolder(folderId: number, data: { name: string }) {
  return apiFetch<WorkspaceFolder>(`/projects/folders/${folderId}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deleteFolder(folderId: number) {
  return apiFetch<{ ok: boolean; message: string }>(`/projects/folders/${folderId}`, { method: "DELETE" });
}

export function updateList(listId: number, data: { name: string }) {
  return apiFetch<WorkspaceList>(`/projects/lists/${listId}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deleteList(listId: number) {
  return apiFetch<{ ok: boolean; message: string }>(`/projects/lists/${listId}`, { method: "DELETE" });
}

export function createTask(data: Partial<Task>) {
  return apiFetch<Task>("/projects/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getTaskDetail(taskId: number, token?: string) {
  const headers: any = {};
  if (token) headers["X-ClickUp-Token"] = token;
  return apiFetch<Task>(`/tasks/${taskId}`, { headers });
}

export function updateTask(taskId: number, data: Partial<Task>) {
  return apiFetch<Task>(`/projects/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteTask(taskId: number) {
  return apiFetch<{ ok: boolean; detail: string }>(`/projects/tasks/${taskId}`, {
    method: "DELETE",
  });
}

export function addComment(taskId: number, content: string, token?: string) {
  const headers: any = {};
  if (token) headers["X-ClickUp-Token"] = token;
  return apiFetch<TaskComment>(`/projects/tasks/${taskId}/comments`, {
    method: "POST",
    headers,
    body: JSON.stringify({ content }),
  });
}

export function updateComment(commentId: number, content: string) {
  return apiFetch<TaskComment>(`/tasks/comments/${commentId}`, {
    method: "PATCH",
    body: JSON.stringify({ content }),
  });
}

export function addChecklistItem(taskId: number, content: string) {
  return apiFetch<ChecklistItem>(`/projects/tasks/${taskId}/checklists`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function deleteComment(commentId: number) {
  return apiFetch(`/tasks/comments/${commentId}`, { method: "DELETE" });
}

export function updateChecklistItem(itemId: number, data: { content?: string, is_completed?: boolean }) {
  return apiFetch(`/tasks/checklists/${itemId}`, { 
    method: "PATCH", 
    body: JSON.stringify(data) 
  });
}

export function deleteChecklistItem(itemId: number) {
  return apiFetch(`/tasks/checklists/${itemId}`, { method: "DELETE" });
}

export function importClickUp(token: string) {
  return apiFetch<{ ok: boolean; message: string }>("/projects/import-clickup", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

/** ---------------------------
 * ESTADÍSTICAS AVANZADAS Y EDICIÓN RÁPIDA
 * -------------------------- */

export type DashboardStats = {
  month_actions: number;
  month_name: string;
  unread_total: number;
  lawyer_stats: { name: string; count: number }[];
};

export function getDashboardStats() {
  return apiFetch<DashboardStats>("/cases/stats/dashboard");
}

export function updateCaseLawyer(caseId: number, lawyerName: string) {
  return apiFetch<any>(`/cases/${caseId}/lawyer`, {
    method: "PATCH",
    body: JSON.stringify({ abogado: lawyerName }),
  });
}

export function bulkAssignLawyer(caseIds: number[], lawyerName: string) {
  return apiFetch<{ ok: boolean; message: string; updated: number }>("/cases/bulk-assign-lawyer", {
    method: "POST",
    body: JSON.stringify({ case_ids: caseIds, abogado: lawyerName }),
  });
}

export function updateCaseIdProceso(caseId: number, idProceso: string) {
  return apiFetch<any>(`/cases/${caseId}/id-proceso`, {
    method: "PATCH",
    body: JSON.stringify({ id_proceso: idProceso }),
  });
}

export function searchCaseFallback(radicado: string, companyId?: number, force?: boolean) {
  return apiFetch<any>("/cases/search", {
    method: "POST",
    body: JSON.stringify({ radicado, company_id: companyId, force }),
  });
}

export function getCaseSourcesHistory(radicado: string) {
  const r = encodeURIComponent(radicado.trim());
  return apiFetch<any[]>(`/cases/${r}/fuentes`);
}

export function buscarNuevamente(radicado: string, companyId?: number) {
  const r = encodeURIComponent(radicado.trim());
  return apiFetch<any>(`/cases/${r}/buscar-nuevamente`, {
    method: "POST",
    body: JSON.stringify({ company_id: companyId }),
  });
}

export function updateCaseActiveStatus(caseId: number, isActive: boolean, motivo?: string) {
  return apiFetch<{ ok: boolean; is_active: boolean; message: string }>(`/cases/${caseId}/active`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive, motivo }),
  });
}

/** ---------------------------
 * TABLERO IA & ANALÍTICA JURÍDICA
 * -------------------------- */
export type AIDashboardStatsResponse = {
  total_analyzed: number;
  inactive_over_6_months: number;
  high_risk_count: number;
  upcoming_terms_count: number;
  ai_summaries_pct: number;
  summary_text: string;
};

export type AIProcessItem = {
  id: number;
  radicado: string;
  demandante: string;
  demandado: string;
  juzgado: string;
  dias_sin_movimiento: number;
  nivel_riesgo: "Alto" | "Medio" | "Bajo";
  termino_dias_restantes: number;
  resumen_ia: string;
  recomendacion_ia: string;
  tipo_sentencia?: "Favorables" | "Desfavorables" | "En Trámite";
  is_sic?: boolean;
};

export type AIQueryResponse = {
  summary: string;
  count: number;
  total_analyzed: number;
  cases: AIProcessItem[];
};

export function getAIDashboardStats() {
  return apiFetch<AIDashboardStatsResponse>("/ai/dashboard-stats");
}

export function queryAIProcesses(query: string = "", filterKey: string = "") {
  return apiFetch<AIQueryResponse>("/ai/query", {
    method: "POST",
    body: JSON.stringify({ query, filter_key: filterKey }),
  });
}

