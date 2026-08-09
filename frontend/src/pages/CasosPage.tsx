import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  FolderOpen,
  Search,
  Eye,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Bell,
  Download,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Calendar,
  List,
  Trash2,
  Clock,
  Upload,
  ChevronDown,
  ArrowLeft,
  Mail,
  MailOpen,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import {
  getCases,
  markCaseRead,
  markCaseUnread,
  markReadAll,
  downloadMultipleEventsExcel,
  refreshAllCases,
  syncAllPublications,
  downloadCasesExcel,
  getInvalidRadicados,
  deleteInvalidRadicado,
  retryInvalidRadicado,
  retryBatchInvalidRadicados,
  deleteAllInvalidRadicados,
  getStats,
  getAbogados,
  validateBatch,
  deleteCase,
  getDashboardStats,
  updateCaseLawyer,
  bulkAssignLawyer,
  type CaseRow,
  type CasesResponse,
  type InvalidRadicado,
  type StatsResponse,
  type DashboardStats,
} from "@/services/api";
import { LawyerCombobox } from "@/components/LawyerCombobox";

type FilterTab = "todos" | "pendientes" | "no_leidos" | "hoy" | "no_encontrados" | "retirados";

const generateMonthOptions = () => {
  const options = [];
  const now = new Date();
  for (let i = 0; i < 24; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = d.toLocaleDateString("es-CO", { year: "numeric", month: "long" });
    options.push({ value, label });
  }
  return options;
};

const MONTH_OPTIONS = generateMonthOptions();
const POLL_INTERVAL = 30_000; // 30 segundos

export default function CasosPage() {
  const { user } = useAuth();
  const isSuperAdmin = user?.is_superadmin || (user?.is_admin && !user?.company_id) || user?.role === 'SUPERADMIN';
  const [activeTab, setActiveTab] = useState<FilterTab>("todos");
  const [stats, setStats] = useState<StatsResponse | null>(null);

  const [rows, setRows] = useState<CaseRow[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isDownloading, setIsDownloading] = useState(false);

  const [isValidatingBatch, setIsValidatingBatch] = useState(false);
  const [isMarkingAllRead, setIsMarkingAllRead] = useState(false);

  const [invalidRows, setInvalidRows] = useState<InvalidRadicado[]>([]);
  const [invalidTotal, setInvalidTotal] = useState(0);
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isRetryingAll, setIsRetryingAll] = useState(false);
  const [isDeletingAll, setIsDeletingAll] = useState(false);

  const [searchInput, setSearchInput] = useState("");
  const [juzgadoInput, setJuzgadoInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState<string | undefined>(undefined);
  const [appliedJuzgado, setAppliedJuzgado] = useState<string | undefined>(undefined);
  const [selectedMonth, setSelectedMonth] = useState<string>("");
  const [appliedMonth, setAppliedMonth] = useState<string | undefined>(undefined);
  const [cedulaInput, setCedulaInput] = useState("");
  const [abogadoInput, setAbogadoInput] = useState("");
  const [appliedCedula, setAppliedCedula] = useState<string | undefined>(undefined);
  const [appliedAbogado, setAppliedAbogado] = useState<string | undefined>(undefined);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [showStats, setShowStats] = useState(true);
  const [pageInput, setPageInput] = useState("1");
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);

  const [caseToDelete, setCaseToDelete] = useState<CaseRow | null>(null);
  const [isDeletingCase, setIsDeletingCase] = useState(false);
  
  const [isUpdatingMetadata, setIsUpdatingMetadata] = useState(false);
  const [abogadosList, setAbogadosList] = useState<string[]>([]);
  const [isSyncingPublications, setIsSyncingPublications] = useState(false);
  const [bulkSyncProgress, setBulkSyncProgress] = useState<{running: boolean; reviewed: number; total: number; percent: number} | null>(null);
  
  const [isMassAssignOpen, setIsMassAssignOpen] = useState(false);
  const [massAssignLawyer, setMassAssignLawyer] = useState("");
  const [isAssigningLawyer, setIsAssigningLawyer] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const API_BASE = (import.meta.env.VITE_API_BASE_URL as string || 'http://localhost:8000').replace(/\/$/, '');

  const { toast } = useToast();
  const navigate = useNavigate();

  // Polling del progreso de sincronización masiva
  useEffect(() => {
    let interval: any;
    if (isSyncingPublications || (bulkSyncProgress && bulkSyncProgress.running)) {
      interval = setInterval(async () => {
        try {
          const resp = await fetch(`${API_BASE}/bulk-sync/publications-status`);
          const data = await resp.json();
          setBulkSyncProgress(data);
          if (!data.running) {
            setIsSyncingPublications(false);
            clearInterval(interval);
          }
        } catch (e) {
          console.error('Error polling bulk sync status:', e);
        }
      }, 10000);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [isSyncingPublications, bulkSyncProgress, API_BASE]);

  const formatDate = (dateString?: string | null) => {
    if (!dateString) return "—";
    const dateToUse = dateString.includes("T") ? dateString : `${dateString}T12:00:00`;
    const d = new Date(dateToUse);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("es-CO", { year: "numeric", month: "short", day: "numeric" });
  };

  const formatDateTime = (dateString?: string | null) => {
    if (!dateString) return "—";
    const d = new Date(dateString);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("es-CO", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  const getAbogadoColor = (name: string) => {
    if (!name) return "";
    const firstWord = name.trim().split(" ")[0].toLowerCase();
    const femaleExceptions = ["carmen", "luz", "marisol", "maribel", "beatriz", "ines", "flor", "rut", "miriam", "judith", "ivonne"];
    const maleExceptions = ["jose", "andrea"]; 
    const isFemale = firstWord.endsWith("a") && firstWord !== "jose" || femaleExceptions.includes(firstWord);
    
    return isFemale 
      ? "bg-pink-100 text-pink-800 border-pink-200 dark:bg-pink-900/40 dark:text-pink-200 dark:border-pink-800" 
      : "bg-sky-100 text-sky-800 border-sky-200 dark:bg-sky-900/40 dark:text-sky-200 dark:border-sky-800";
  };

  const fetchStats = useCallback(async () => {
    try {
      const [statsData, abogadosData, dashboardData] = await Promise.all([
        getStats(),
        getAbogados(),
        getDashboardStats()
      ]);
      setStats(statsData);
      setAbogadosList(abogadosData || []);
      setDashboardStats(dashboardData);
    } catch (error) {
      console.error("Error cargando stats/abogados:", error);
    }
  }, []);

  const fetchCases = useCallback(async (silent = false) => {
    if (activeTab === "no_encontrados") return;
    if (!silent) setIsLoading(true);
    try {
      const response: CasesResponse = await getCases({
        search: appliedSearch,
        juzgado: appliedJuzgado,
        mes_actuacion: appliedMonth,
        solo_validos: activeTab !== "pendientes" && activeTab !== "retirados",
        solo_pendientes: activeTab === "pendientes",
        solo_no_leidos: activeTab === "no_leidos",
        solo_actualizados_hoy: activeTab === "hoy",
        solo_retirados: activeTab === "retirados",
        cedula: appliedCedula,
        abogado: appliedAbogado,
        page,
        page_size: pageSize,
      });

      const items = response.items || [];
      const totalCount = response.total || 0;

      setRows(items);
      setTotal(totalCount);
      setUnreadCount(response.unread_count || 0);

      const tp = Math.max(1, Math.ceil(totalCount / pageSize));
      setTotalPages(tp);
      if (page > tp) setPage(tp);
    } catch (error: any) {
      if (!silent) {
        toast({ title: "Error al cargar casos", description: error?.message || "Error desconocido", variant: "destructive" });
      }
      if (!silent) { setRows([]); setTotal(0); setTotalPages(1); }
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [activeTab, appliedSearch, appliedJuzgado, appliedMonth, appliedCedula, appliedAbogado, page, pageSize, toast]);

  const fetchInvalidRadicados = useCallback(async (silent = false) => {
    if (activeTab !== "no_encontrados") return;
    if (!silent) setIsLoading(true);
    try {
      const response = await getInvalidRadicados({ search: appliedSearch, page, page_size: pageSize });
      const items = response.items || [];
      const totalCount = response.total || 0;
      setInvalidRows(items);
      setInvalidTotal(totalCount);
      const tp = Math.max(1, Math.ceil(totalCount / pageSize));
      setTotalPages(tp);
      if (page > tp) setPage(tp);
    } catch (error: any) {
      if (!silent) {
        toast({ title: "Error al cargar no encontrados", description: error?.message || "Error desconocido", variant: "destructive" });
        setInvalidRows([]); setInvalidTotal(0); setTotalPages(1);
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [activeTab, appliedSearch, page, pageSize, toast]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    if (activeTab === "no_encontrados") fetchInvalidRadicados();
    else fetchCases();
  }, [activeTab, fetchCases, fetchInvalidRadicados]);

  useEffect(() => {
    const runPoll = async () => {
      try {
        const statsData = await getStats();
        setStats(statsData);

        if (activeTab === "no_encontrados") {
          const resp = await getInvalidRadicados({ search: appliedSearch, page, page_size: pageSize });
          setInvalidRows(resp.items || []);
          setInvalidTotal(resp.total || 0);
          const tp = Math.max(1, Math.ceil((resp.total || 0) / pageSize));
          setTotalPages(tp);
        } else {
          const resp = await getCases({
            search: appliedSearch,
            juzgado: appliedJuzgado,
            mes_actuacion: appliedMonth,
            solo_validos: activeTab !== "pendientes" && activeTab !== "retirados",
            solo_pendientes: activeTab === "pendientes",
            solo_no_leidos: activeTab === "no_leidos",
            solo_actualizados_hoy: activeTab === "hoy",
            solo_retirados: activeTab === "retirados",
            cedula: appliedCedula,
            abogado: appliedAbogado,
            page,
            page_size: pageSize,
          });
          setRows(resp.items || []);
          setTotal(resp.total || 0);
          setUnreadCount(resp.unread_count || 0);
          const tp = Math.max(1, Math.ceil((resp.total || 0) / pageSize));
          setTotalPages(tp);
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    };

    const interval = setInterval(runPoll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [activeTab, appliedSearch, appliedJuzgado, appliedMonth, appliedCedula, appliedAbogado, page, pageSize]);

  useEffect(() => {
    setPageInput(String(page));
  }, [page]);

  const handleTabChange = (tab: FilterTab) => {
    setActiveTab(tab);
    setPage(1); setPageInput("1");
    setSelectedIds(new Set());
    setAppliedSearch(undefined); setAppliedJuzgado(undefined); setAppliedMonth(undefined);
    setAppliedCedula(undefined); setAppliedAbogado(undefined);
    setSearchInput(""); setJuzgadoInput(""); setSelectedMonth("");
    setCedulaInput(""); setAbogadoInput("");
  };

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1); setPageInput("1");
    setSelectedIds(new Set());
    setAppliedSearch(searchInput.trim() || undefined);
    setAppliedJuzgado(juzgadoInput.trim() || undefined);
    setAppliedCedula(cedulaInput.trim() || undefined);
    setAppliedAbogado(abogadoInput.trim() || undefined);
    setAppliedMonth(selectedMonth || undefined);
  };

  const handleClearFilters = () => {
    setSearchInput(""); setJuzgadoInput(""); setSelectedMonth("");
    setCedulaInput(""); setAbogadoInput("");
    setAppliedSearch(undefined); setAppliedJuzgado(undefined); setAppliedMonth(undefined);
    setAppliedCedula(undefined); setAppliedAbogado(undefined);
    setPage(1); setPageInput("1");
  };

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    try {
      const result = await refreshAllCases();
      toast({ title: "Actualización completada", description: `Se verificaron ${result.checked || 0} casos. ${result.updated_cases || 0} con cambios.` });
      await fetchCases();
      await fetchStats();
    } catch (error: any) {
      toast({ title: "Error actualizando", description: error?.message || "Error desconocido", variant: "destructive" });
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleSyncAllPublicaciones = async () => {
    if (bulkSyncProgress?.running) {
      toast({
        title: 'Sincronización en curso',
        description: `Revisados ${bulkSyncProgress.reviewed} de ${bulkSyncProgress.total} radicados (${bulkSyncProgress.percent}%)`,
      });
      return;
    }
    if (!confirm('¿Iniciar sincronización masiva de Publicaciones Procesales para todos los casos?\n\nEste proceso se ejecuta en segundo plano y puede tardar varios minutos.')) return;
    setIsSyncingPublications(true);
    setBulkSyncProgress(null);
    try {
      const result = await syncAllPublications();
      if (!result.ok) {
        toast({ title: 'Aviso', description: result.message });
      } else {
        toast({
          title: 'Sincronización iniciada',
          description: result.message || `Se procesarán ${result.total} casos en segundo plano.`,
        });
      }
    } catch (error: any) {
      toast({ title: 'Error', description: error?.message || 'No se pudo iniciar la sincronización', variant: 'destructive' });
      setIsSyncingPublications(false);
    }
  };

  const handleValidateBatch = async () => {
    setIsValidatingBatch(true);
    try {
      const result = await validateBatch(50);
      toast({ title: "Validación completada", description: result.message });
      await fetchCases();
      await fetchStats();
    } catch (error: any) {
      toast({ title: "Error validando", description: error?.message || "Error desconocido", variant: "destructive" });
    } finally {
      setIsValidatingBatch(false);
    }
  };

  const handleMarkAllRead = async () => {
    if (!confirm(`¿Marcar todos los casos ${activeTab === "no_leidos" ? "sin leer" : "visibles"} como leídos?`)) return;
    setIsMarkingAllRead(true);
    try {
      const result = await markReadAll({ 
        search: appliedSearch, 
        juzgado: appliedJuzgado, 
        abogado: appliedAbogado,
        cedula: appliedCedula,
        mes_actuacion: appliedMonth,
        solo_no_leidos: activeTab === "no_leidos", 
        solo_actualizados_hoy: activeTab === "hoy" 
      });
      toast({ title: "Marcados como leídos", description: `Se marcaron ${result.updated} caso(s) como leídos` });
      await fetchCases();
      await fetchStats();
    } catch (error: any) {
      toast({ title: "Error", description: error?.message || "Error desconocido", variant: "destructive" });
    } finally {
      setIsMarkingAllRead(false);
    }
  };

  const handleRetryBatchInvalid = async () => {
    setIsRetryingAll(true);
    try {
      const result = await retryBatchInvalidRadicados(20);
      toast({ title: "Reintento completado", description: result.message });
      await fetchInvalidRadicados();
      await fetchStats();
    } catch (error: any) {
      toast({ title: "Error reintentando", description: error?.message || "Error desconocido", variant: "destructive" });
    } finally {
      setIsRetryingAll(false);
    }
  };

  const handleDeleteAllInvalid = async () => {
    if (!confirm(`¿Eliminar TODOS los ${invalidTotal} radicados no encontrados?\n\nEsta acción no se puede deshacer.`)) return;
    setIsDeletingAll(true);
    try {
      const result = await deleteAllInvalidRadicados();
      toast({ title: "Eliminados", description: result.message || "Radicados no encontrados eliminados correctamente." });
      await fetchInvalidRadicados();
      await fetchStats();
    } catch (error: any) {
      const msg = error?.detail ? (typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)) : (error?.message || "Error desconocido");
      toast({ title: "Error eliminando", description: msg, variant: "destructive" });
    } finally {
      setIsDeletingAll(false);
    }
  };

  const handleDeleteCase = async () => {
    if (!caseToDelete) return;
    setIsDeletingCase(true);
    try {
      await deleteCase(caseToDelete.id);
      toast({ title: "Caso eliminado", description: `El radicado ${caseToDelete.radicado} fue eliminado correctamente` });
      setCaseToDelete(null);
      await fetchCases();
      await fetchStats();
    } catch (error: any) {
      const msg = error?.detail ? (typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)) : (error?.message || "Error desconocido");
      toast({ title: "Error eliminando", description: msg, variant: "destructive" });
    } finally {
      setIsDeletingCase(false);
    }
  };

  const onOpenCase = async (c: CaseRow) => {
    if (c.unread) {
      try {
        await markCaseRead(c.id);
        setRows((prev) => prev.map((x) => (x.id === c.id ? { ...x, unread: false } : x)));
        setUnreadCount((n) => Math.max(0, n - 1));
        fetchStats();
      } catch {}
    }
    window.open(`/casos/id/${c.id}`, "_blank");
  };

  const onToggleReadStatus = async (c: CaseRow, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      if (c.unread) {
        await markCaseRead(c.id);
        setRows((prev) => prev.map((x) => (x.id === c.id ? { ...x, unread: false } : x)));
        setUnreadCount((n) => Math.max(0, n - 1));
        toast({ title: "Marcado como leído", description: `El radicado ${c.radicado} ahora está marcado como leído.` });
      } else {
        await markCaseUnread(c.id);
        setRows((prev) => prev.map((x) => (x.id === c.id ? { ...x, unread: true } : x)));
        setUnreadCount((n) => n + 1);
        toast({ title: "Marcado como no leído", description: `El radicado ${c.radicado} ahora está marcado como no leído.` });
      }
      fetchStats();
    } catch (err: any) {
      toast({ title: "Error", description: err.message || "No se pudo cambiar el estado", variant: "destructive" });
    }
  };

  const toggleSelect = (id: number) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === rows.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(rows.map((r) => r.id)));
  };

  const handleDownloadSelected = async () => {
    if (selectedIds.size === 0) {
      toast({ title: "Selecciona casos", description: "Debes seleccionar al menos un caso para descargar", variant: "destructive" });
      return;
    }
    setIsDownloading(true);
    try {
      const radicados = rows.filter((r) => selectedIds.has(r.id)).map((r) => r.radicado);
      await downloadMultipleEventsExcel(radicados);
      toast({ title: "Descarga completada", description: `Se descargaron las actuaciones de ${radicados.length} caso(s)` });
      setSelectedIds(new Set());
    } catch (error: any) {
      toast({ title: "Error al descargar", description: error?.message || "Error desconocido", variant: "destructive" });
    } finally {
      setIsDownloading(false);
    }
  };

  const handleMassAssignLawyer = async () => {
    if (selectedIds.size === 0) return;
    const lawyerVal = massAssignLawyer.trim() || "sin_asignar";
    setIsAssigningLawyer(true);
    try {
      const idsArray = Array.from(selectedIds);
      const result = await bulkAssignLawyer(idsArray, lawyerVal);
      
      setRows(prev => prev.map(r => 
        selectedIds.has(r.id) ? { ...r, abogado: lawyerVal === "sin_asignar" ? null : lawyerVal } : r
      ));
      
      toast({ title: "Asignación masiva completada", description: `Se actualizaron ${result.updated} casos correctamente.` });
      setIsMassAssignOpen(false);
      setMassAssignLawyer("");
      setSelectedIds(new Set());
      fetchStats();
    } catch (err: any) {
      const errorMsg = err.detail ? (typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)) : (err.message || err.toString());
      toast({ title: "Error al asignar abogado", description: errorMsg, variant: "destructive" });
    } finally {
      setIsAssigningLawyer(false);
    }
  };

  const handleUpdateMetadataClick = () => {
    fileInputRef.current?.click();
  };

  const handleMetadataFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUpdatingMetadata(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const token = localStorage.getItem("emdecob_auth_token");
      const resp = await fetch(`${API_BASE}/cases/bulk-update-metadata`, {
        method: "POST",
        body: formData,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Error al actualizar metadatos");

      toast({
        title: "Actualización exitosa",
        description: `Se actualizaron ${data.updated_count} casos correctamente.`,
      });
      await fetchCases();
      await fetchStats();
    } catch (error: any) {
      toast({
        title: "Error al actualizar",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setIsUpdatingMetadata(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDownloadExcel = async (mode: "page" | "filtered" | "all" = "filtered") => {
    if (activeTab === "pendientes") return;

    try {
      if (activeTab === "no_encontrados") {
        await downloadInvalidRadicadosExcel();
        return;
      }

      const params: any = {};
      if (mode === "page") {
        params.page = page;
        params.page_size = pageSize;
        params.search = appliedSearch;
        params.juzgado = appliedJuzgado;
        params.abogado = appliedAbogado;
        params.cedula = appliedCedula;
        params.mes_actuacion = appliedMonth;
        params.solo_no_leidos = activeTab === "no_leidos";
        params.solo_actualizados_hoy = activeTab === "hoy";
        params.solo_retirados = activeTab === "retirados";
      } else if (mode === "filtered") {
        params.search = appliedSearch;
        params.juzgado = appliedJuzgado;
        params.abogado = appliedAbogado;
        params.cedula = appliedCedula;
        params.mes_actuacion = appliedMonth;
        params.solo_no_leidos = activeTab === "no_leidos";
        params.solo_actualizados_hoy = activeTab === "hoy";
        params.solo_retirados = activeTab === "retirados";
      } else if (mode === "all") {
        params.ignore_filters = true;
        params.solo_retirados = activeTab === "retirados";
      }

      await downloadCasesExcel(params);
      toast({ title: "Descargando...", description: "El archivo Excel se descargará en unos segundos" });
    } catch (error: any) {
      const msg = error?.detail ? (typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)) : (error?.message || "No se pudo generar el archivo");
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
  };

  const handleRetryInvalid = async (item: InvalidRadicado) => {
    setRetryingId(item.id);
    try {
      const result = await retryInvalidRadicado(item.id);
      if (result.found) {
        toast({ title: "¡Radicado encontrado!", description: "El radicado fue agregado a los casos válidos" });
        fetchStats();
      } else {
        toast({ title: "Sigue sin aparecer", description: "El radicado continúa sin encontrarse en Rama Judicial", variant: "destructive" });
      }
      fetchInvalidRadicados();
    } catch (error: any) {
      toast({ title: "Error", description: error?.message || "Error al reintentar", variant: "destructive" });
    } finally {
      setRetryingId(null);
    }
  };

  const handleDeleteInvalid = async (item: InvalidRadicado) => {
    setDeletingId(item.id);
    try {
      await deleteInvalidRadicado(item.id);
      toast({ title: "Eliminado", description: "El radicado fue eliminado de la lista" });
      fetchInvalidRadicados();
      fetchStats();
    } catch (error: any) {
      const msg = error?.detail ? (typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)) : (error?.message || "Error al eliminar");
      toast({ title: "Error", description: msg, variant: "destructive" });
    } finally {
      setDeletingId(null);
    }
  };

  const handlePageInputChange = (e: React.ChangeEvent<HTMLInputElement>) => setPageInput(e.target.value);

  const handlePageInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newPage = parseInt(pageInput, 10);
    if (!isNaN(newPage) && newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
    } else {
      setPageInput(String(page));
      toast({ title: "Página inválida", description: `Ingresa un número entre 1 y ${totalPages}`, variant: "destructive" });
    }
  };

  const handleMonthChange = (val: string) => setSelectedMonth(val === "all" ? "" : val);

  const canPaginate = totalPages > 1;
  const currentTotal = activeTab === "no_encontrados" ? invalidTotal : total;
  const showingFrom = currentTotal === 0 ? 0 : (page - 1) * pageSize + 1;
  const showingTo = Math.min(page * pageSize, currentTotal);

  const lawyerOptions = Array.from(new Set([
    ...(dashboardStats?.lawyer_stats?.map(s => s.name) || []),
    ...rows.map(r => r.abogado).filter(Boolean),
    ...abogadosList
  ])).filter(name => name !== "sin_asignar") as string[];

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ─── BANNER PROGRESO SINCRONIZACIÓN MASIVA ─── */}
      {(bulkSyncProgress?.running || isSyncingPublications) && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 animate-in fade-in slide-in-from-top-2 duration-500">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 text-emerald-600 animate-spin" />
              <span className="font-semibold text-emerald-700 dark:text-emerald-400">
                Sincronizando Publicaciones Procesales...
              </span>
            </div>
            <span className="text-sm font-bold text-emerald-700 dark:text-emerald-400">
              {bulkSyncProgress
                ? `${bulkSyncProgress.reviewed} / ${bulkSyncProgress.total} radicados (${bulkSyncProgress.percent}%)`
                : 'Iniciando...'}
            </span>
          </div>
          {/* Barra de progreso manual con div */}
          <div className="w-full bg-emerald-100 dark:bg-emerald-900/30 rounded-full h-3 overflow-hidden">
            <div
              className="h-3 bg-emerald-500 rounded-full transition-all duration-700 ease-in-out"
              style={{ width: `${bulkSyncProgress?.percent ?? 2}%` }}
            />
          </div>
          <div className="flex items-center justify-between mt-2 text-xs text-emerald-600/70 dark:text-emerald-400/70">
            <span>Revisando el portal de Publicaciones Procesales de Rama Judicial para cada radicado</span>
            {(bulkSyncProgress?.errors ?? 0) > 0 && (
              <span className="text-amber-600 font-medium">{bulkSyncProgress!.errors} con error</span>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Todos los Casos</h1>
          <p className="text-muted-foreground mt-2">
                      {activeTab === "todos" && "Todos los procesos válidos encontrados en Rama Judicial"}
            {activeTab === "pendientes" && "Radicados importados pendientes de validar"}
            {activeTab === "no_leidos" && "Procesos con actuaciones pendientes por revisar"}
            {activeTab === "hoy" && "Procesos con actuaciones del día de hoy"}
            {activeTab === "no_encontrados" && "Radicados que no se encontraron en Rama Judicial"}
            {activeTab === "retirados" && "Radicados retirados de gestión activa — el historial se conserva"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {unreadCount > 0 && activeTab !== "pendientes" && activeTab !== "no_encontrados" && (
            <div className="flex items-center gap-2 bg-primary/10 text-primary px-4 py-2 rounded-lg animate-pulse">
              <Bell className="h-5 w-5" />
              <span className="font-semibold">{unreadCount} sin leer</span>
            </div>
          )}

          <Button 
            onClick={() => setShowStats(!showStats)} 
            variant="outline" 
            size="sm" 
            className={`transition-all duration-300 ${showStats ? "border-primary/50 text-primary bg-primary/5" : "border-muted-foreground text-muted-foreground"}`}
          >
            {showStats ? <ChevronDown className="h-4 w-4 mr-2 rotate-180 transition-transform" /> : <ChevronDown className="h-4 w-4 mr-2 transition-transform" />}
            {showStats ? "Contraer Indicadores" : "Expandir Indicadores"}
          </Button>

          {isSuperAdmin && !import.meta.env.PROD && (
            <Button
              onClick={handleSyncAllPublicaciones}
              disabled={false}
              variant="outline"
              size="sm"
              className={`border-emerald-500/50 hover:bg-emerald-500/10 dark:text-emerald-400 ${
                bulkSyncProgress?.running
                  ? 'text-emerald-600 border-emerald-500'
                  : 'text-emerald-700'
              }`}
            >
              {(isSyncingPublications || bulkSyncProgress?.running)
                ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                : <RefreshCw className="h-4 w-4 mr-2" />}
              {bulkSyncProgress?.running
                ? `Publicaciones: ${bulkSyncProgress.reviewed}/${bulkSyncProgress.total}`
                : 'Sincronizar publicaciones'}
            </Button>
          )}
          <Button onClick={handleRefreshAll} disabled={isRefreshing} variant="default" size="sm">
            {isRefreshing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
            Actualizar todo
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center">
              <RefreshCw className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase opacity-70">Actuaciones {dashboardStats?.month_name || 'Abril'}</p>
              <h3 className="text-2xl font-bold">{dashboardStats?.month_actions || 0}</h3>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-orange-500/10 to-orange-500/5 border-orange-500/20">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="h-12 w-12 rounded-full bg-orange-500/20 flex items-center justify-center">
              <Calendar className="h-6 w-6 text-orange-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase opacity-70">Top Abogado</p>
              <h3 className="text-lg font-bold truncate">
                {dashboardStats?.lawyer_stats?.[0]?.name || 'N/A'} 
                <span className="text-xs font-normal ml-2">({dashboardStats?.lawyer_stats?.[0]?.count || 0})</span>
              </h3>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-pink-500/10 to-pink-500/5 border-pink-500/20">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="h-12 w-12 rounded-full bg-pink-500/20 flex items-center justify-center">
              <Bell className="h-6 w-6 text-pink-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase opacity-70">Sin leer (Global)</p>
              <h3 className="text-2xl font-bold">{dashboardStats?.unread_total || 0}</h3>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 border-emerald-500/20">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="h-12 w-12 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <CheckCircle2 className="h-6 w-6 text-emerald-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase opacity-70">Día más activo</p>
              <h3 className="text-2xl font-bold">Lunes</h3>
            </div>
          </CardContent>
        </Card>
      </div>

      {showStats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
          <Button variant={activeTab === "todos" ? "default" : "outline"} className="h-auto py-4 flex flex-col items-center gap-2" onClick={() => handleTabChange("todos")}>
            <List className="h-6 w-6 text-primary" />
            <div className="text-center">
              <div className="text-sm font-medium">Validados</div>
              <div className="text-lg font-bold opacity-90">{stats?.total_validos || 0}</div>
            </div>
          </Button>

          <Button variant={activeTab === "pendientes" ? "secondary" : "outline"} className={`h-auto py-4 flex flex-col items-center gap-2 ${activeTab === "pendientes" ? "bg-yellow-500/20 border-yellow-500 text-yellow-700 dark:text-yellow-300" : ""}`} onClick={() => handleTabChange("pendientes")}>
            <Clock className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
            <div className="text-center">
              <div className="text-sm font-medium">Pendientes</div>
              <div className="text-lg font-bold opacity-90">{stats?.total_pendientes || 0}</div>
            </div>
          </Button>

          <Button variant={activeTab === "no_leidos" ? "default" : "outline"} className="h-auto py-4 flex flex-col items-center gap-2" onClick={() => handleTabChange("no_leidos")}>
            <Bell className="h-6 w-6 text-primary" />
            <div className="text-center">
              <div className="text-sm font-medium">Sin Leer</div>
              <div className="text-lg font-bold opacity-90">{stats?.total_no_leidos || 0}</div>
            </div>
          </Button>

          <Button variant={activeTab === "hoy" ? "default" : "outline"} className="h-auto py-4 flex flex-col items-center gap-2" onClick={() => handleTabChange("hoy")}>
            <Calendar className="h-6 w-6 text-primary" />
            <div className="text-center">
              <div className="text-sm font-medium">Hoy</div>
              <div className="text-lg font-bold opacity-90">{stats?.total_actualizados_hoy || 0}</div>
            </div>
          </Button>

          <Button variant={activeTab === "no_encontrados" ? "destructive" : "outline"} className="h-auto py-4 flex flex-col items-center gap-2" onClick={() => handleTabChange("no_encontrados")}>
            <AlertTriangle className="h-6 w-6 text-destructive" />
            <div className="text-center">
              <div className="text-sm font-medium">No Encontrados</div>
              <div className="text-lg font-bold opacity-90">{stats?.total_invalidos || 0}</div>
            </div>
          </Button>

          <Button
            variant={activeTab === "retirados" ? "secondary" : "outline"}
            className={`h-auto py-4 flex flex-col items-center gap-2 ${
              activeTab === "retirados"
                ? "bg-amber-500/20 border-amber-500 text-amber-700 dark:text-amber-300"
                : "border-amber-500/30 text-amber-600 hover:bg-amber-500/10 hover:border-amber-500/60"
            }`}
            onClick={() => handleTabChange("retirados")}
          >
            <ArrowLeft className="h-6 w-6 text-amber-500" />
            <div className="text-center">
              <div className="text-sm font-medium">Retirados</div>
              <div className="text-lg font-bold opacity-90">—</div>
            </div>
          </Button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5 text-primary" />
            Filtros de Búsqueda
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleFilter} className="flex flex-col gap-3">
            <div className="flex flex-col sm:flex-row gap-3">
              <Input
                placeholder={activeTab === "no_encontrados" || activeTab === "pendientes" ? "Buscar radicado..." : "Buscar por radicado, demandante o demandado..."}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="flex-1"
              />
              {activeTab !== "no_encontrados" && activeTab !== "pendientes" && (
                <Input placeholder="Filtrar por juzgado..." value={juzgadoInput} onChange={(e) => setJuzgadoInput(e.target.value)} className="sm:w-64" />
              )}
            </div>

            {["todos", "no_leidos", "hoy", "retirados"].includes(activeTab) && (
              <div className="flex flex-wrap gap-3 items-end">
                <div className="w-full sm:w-44">
                  <label className="text-xs text-muted-foreground mb-1 block">Cédula</label>
                  <Input placeholder="Filtrar por cédula..." value={cedulaInput} onChange={(e) => setCedulaInput(e.target.value)} />
                </div>
                <div className="w-full sm:flex-1 sm:min-w-[220px]">
                  <label className="text-xs text-muted-foreground mb-1 block">Abogado</label>
                  <Input 
                    placeholder="Escribir o seleccionar abogado..." 
                    value={abogadoInput} 
                    onChange={(e) => setAbogadoInput(e.target.value)} 
                    list="abogados-list"
                    className="w-full"
                  />
                  <datalist id="abogados-list">
                    {abogadosList.map(a => <option key={a} value={a} />)}
                  </datalist>
                </div>
                <div className="w-full sm:w-52">
                  <label className="text-xs text-muted-foreground mb-1 block">Mes actuación</label>
                  <Select value={selectedMonth || "all"} onValueChange={handleMonthChange}>
                    <SelectTrigger><SelectValue placeholder="Todos los meses" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos los meses</SelectItem>
                      {MONTH_OPTIONS.map((opt) => <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={isLoading}><Search className="mr-2 h-4 w-4" />Filtrar</Button>
                  {(appliedSearch || appliedJuzgado || appliedMonth || appliedCedula || appliedAbogado) && <Button type="button" variant="outline" onClick={handleClearFilters}>Limpiar</Button>}
                </div>
              </div>
            )}

            {!["todos", "no_leidos", "hoy", "retirados"].includes(activeTab) && (
              <div className="flex gap-2">
                <Button type="submit" disabled={isLoading}><Search className="mr-2 h-4 w-4" />Filtrar</Button>
                {(appliedSearch || appliedJuzgado) && <Button type="button" variant="outline" onClick={handleClearFilters}>Limpiar</Button>}
              </div>
            )}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <CardTitle>
                {activeTab === "todos" && `Casos validados (${total})`}
                {activeTab === "pendientes" && `Pendientes de validar (${total})`}
                {activeTab === "no_leidos" && `Casos sin leer (${total})`}
                {activeTab === "hoy" && `Actualizados hoy (${total})`}
                {activeTab === "no_encontrados" && `No encontrados (${invalidTotal})`}
                {activeTab === "retirados" && `Radicados retirados (${total})`}
              </CardTitle>
              <span className="text-sm text-muted-foreground">Mostrando {showingFrom}-{showingTo} de {currentTotal}</span>
            </div>

            <div className="flex items-center gap-2">
              {activeTab === "todos" && (
                <>
                  <input
                    type="file"
                    ref={fileInputRef}
                    className="hidden"
                    accept=".xlsx,.xls,.csv"
                    onChange={handleMetadataFileChange}
                  />
                  <Button onClick={handleUpdateMetadataClick} disabled={isUpdatingMetadata} variant="outline" size="sm" className="border-primary/50 text-primary hover:bg-primary/10">
                    {isUpdatingMetadata ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
                    Cargar Abogados
                  </Button>
                </>
              )}
              {activeTab !== "no_encontrados" && activeTab !== "pendientes" && unreadCount > 0 && (
                <Button onClick={handleMarkAllRead} disabled={isMarkingAllRead} variant="outline" size="sm">
                  {isMarkingAllRead ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
                  Marcar leídos
                </Button>
              )}
              {activeTab !== "no_encontrados" && activeTab !== "pendientes" && selectedIds.size > 0 && (
                <>
                  <Button onClick={() => setIsMassAssignOpen(true)} variant="outline" size="sm" className="border-primary/50 text-primary hover:bg-primary/10">
                    Asignar Abogado
                  </Button>
                  <Button onClick={handleDownloadSelected} disabled={isDownloading} variant="outline" size="sm">
                    {isDownloading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
                    Descargar {selectedIds.size}
                  </Button>
                </>
              )}
              {activeTab === "no_encontrados" && invalidTotal > 0 && (
                <Button variant="outline" size="sm" onClick={() => handleDownloadExcel()}>
                  <Download className="h-4 w-4 mr-2" />Exportar
                </Button>
              )}
              {activeTab !== "pendientes" && activeTab !== "no_encontrados" && total > 0 && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm">
                      <Download className="h-4 w-4 mr-2" />Exportar
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-64 bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 shadow-xl rounded-lg p-1.5 z-[100]">
                    <DropdownMenuItem 
                      onClick={() => handleDownloadExcel("page")} 
                      className="cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-900 rounded-md p-2 text-sm flex flex-col items-start"
                    >
                      <span className="font-semibold text-zinc-900 dark:text-zinc-100">Exportar página actual</span>
                      <span className="text-xs text-zinc-500">Solo los {rows.length} casos visibles en esta hoja</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem 
                      onClick={() => handleDownloadExcel("filtered")} 
                      className="cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-900 rounded-md p-2 text-sm flex flex-col items-start mt-0.5"
                    >
                      <span className="font-semibold text-zinc-900 dark:text-zinc-100">Exportar con filtros aplicados</span>
                      <span className="text-xs text-zinc-500">Todos los casos según búsqueda y filtros actuales</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem 
                      onClick={() => handleDownloadExcel("all")} 
                      className="cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-900 rounded-md p-2 text-sm flex flex-col items-start mt-0.5"
                    >
                      <span className="font-semibold text-zinc-900 dark:text-zinc-100">Exportar todos los casos</span>
                      <span className="text-xs text-zinc-500">Todo el listado completo (sin filtros de búsqueda)</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : activeTab === "no_encontrados" ? (
            invalidRows.length === 0 ? (
              <div className="text-center py-12">
                <CheckCircle2 className="h-12 w-12 mx-auto text-green-500 mb-4" />
                <p className="text-muted-foreground">No hay radicados no encontrados</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <span className="text-destructive text-sm font-medium">⚠️ {invalidTotal} radicados no encontrados en Rama Judicial</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={handleRetryBatchInvalid} disabled={isRetryingAll}>
                      {isRetryingAll ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                      Reintentar 20
                    </Button>
                    <Button size="sm" variant="destructive" onClick={handleDeleteAllInvalid} disabled={isDeletingAll}>
                      {isDeletingAll ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Trash2 className="h-4 w-4 mr-2" />}
                      Eliminar todos
                    </Button>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Radicado</TableHead>
                        <TableHead>Motivo</TableHead>
                        <TableHead className="text-center">Intentos</TableHead>
                        <TableHead>Último intento</TableHead>
                        <TableHead className="text-right">Acciones</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {invalidRows.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell className="font-mono text-sm">{item.radicado}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">{item.motivo}</TableCell>
                          <TableCell className="text-center"><Badge variant="outline">{item.intentos}</Badge></TableCell>
                          <TableCell className="text-sm text-muted-foreground">{formatDateTime(item.updated_at)}</TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button variant="outline" size="sm" onClick={() => handleRetryInvalid(item)} disabled={retryingId === item.id}>
                                {retryingId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                              </Button>
                              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => handleDeleteInvalid(item)} disabled={deletingId === item.id}>
                                {deletingId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )
          ) : activeTab === "pendientes" ? (
            rows.length === 0 ? (
              <div className="text-center py-12">
                <CheckCircle2 className="h-12 w-12 mx-auto text-green-500 mb-4" />
                <p className="text-muted-foreground">No hay radicados pendientes de validar</p>
                <p className="text-sm text-muted-foreground mt-2">Todos los radicados importados han sido validados</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <span className="text-yellow-700 dark:text-yellow-300 text-sm font-medium">⚠️ {total} radicados pendientes de validar contra Rama Judicial</span>
                  <Button size="sm" className="bg-yellow-600 hover:bg-yellow-500 text-white" onClick={handleValidateBatch} disabled={isValidatingBatch}>
                    {isValidatingBatch ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                    Validar 50 radicados
                  </Button>
                </div>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Radicado</TableHead>
                        <TableHead>Fecha importación</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((c) => (
                        <TableRow key={c.id}>
                          <TableCell className="font-mono text-sm">{c.radicado}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">{formatDateTime(c.created_at)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )
          ) : rows.length === 0 ? (
            <div className="text-center py-12">
              <FolderOpen className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No se encontraron casos</p>
            </div>
          ) : (
            <div className="overflow-x-auto w-full">
              <Table className="w-full min-w-[900px]">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10 px-2">
                      <Checkbox checked={selectedIds.size === rows.length && rows.length > 0} onCheckedChange={toggleSelectAll} />
                    </TableHead>
                    <TableHead className="min-w-[180px]">Radicado</TableHead>
                    <TableHead className="hidden md:table-cell">Demandante</TableHead>
                    <TableHead className="hidden lg:table-cell">Demandado</TableHead>
                    <TableHead>Abogado</TableHead>
                    <TableHead>Cédula</TableHead>
                    <TableHead className="hidden xl:table-cell">Juzgado</TableHead>
                    <TableHead className="w-24">Últ. Act.</TableHead>
                    <TableHead className="w-20 text-center">Gestión</TableHead>
                    <TableHead className="w-28 text-center">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow 
                      key={row.id} 
                      className={`cursor-pointer transition-colors ${row.unread ? "bg-primary/10 font-semibold hover:bg-primary/15" : "hover:bg-muted/40"}`}
                      onClick={() => onOpenCase(row)}
                    >
                      <TableCell className="px-2" onClick={(e) => e.stopPropagation()}>
                        <Checkbox checked={selectedIds.has(row.id)} onCheckedChange={() => toggleSelect(row.id)} />
                      </TableCell>
                      <TableCell className="font-mono py-4">
                        <div className="flex items-center gap-2">
                          {row.unread && <Badge variant="default" className="animate-pulse text-[11px] px-1.5 py-0.5">NUEVO</Badge>}
                          <span className={`${row.unread ? "text-primary font-bold" : "font-medium"} text-sm tracking-tight`}>{row.radicado}</span>
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell max-w-[140px] truncate text-sm">{row.demandante || "—"}</TableCell>
                      <TableCell className="hidden lg:table-cell max-w-[140px] truncate text-sm">{row.demandado || "—"}</TableCell>
                      <TableCell className="max-w-[200px]" onClick={(e) => e.stopPropagation()}>
                        <LawyerCombobox
                          options={lawyerOptions}
                          value={row.abogado || ""}
                          onChange={async (val) => {
                            const newVal = val.trim() || "sin_asignar";
                            const oldVal = row.abogado || "sin_asignar";
                            if (newVal.toLowerCase() === oldVal.toLowerCase()) return;
                            try {
                              await updateCaseLawyer(row.id, newVal);
                              setRows(prev => prev.map(r => r.id === row.id ? { ...r, abogado: newVal === "sin_asignar" ? null : newVal } : r));
                              toast({ title: "Abogado actualizado", description: "El cambio se guardó correctamente" });
                              fetchStats();
                            } catch (err: any) {
                              const errorMsg = err.detail ? (typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)) : (err.message || err.toString());
                              toast({ title: "Error", description: errorMsg, variant: "destructive" });
                            }
                          }}
                          className={`h-8 text-xs font-medium w-full ${getAbogadoColor(row.abogado || "")}`}
                        />
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{row.cedula || "—"}</TableCell>
                      <TableCell className="hidden xl:table-cell text-xs text-muted-foreground max-w-[150px] truncate">{row.juzgado || "—"}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{formatDate(row.ultima_actuacion)}</TableCell>
                      <TableCell className="text-center">
                        {row.has_tasks ? (
                          <Badge variant="outline" className="bg-green-100 text-green-700 border-green-200 dark:bg-green-900/40 dark:text-green-200 dark:border-green-800">
                            <CheckCircle2 className="h-3 w-3 mr-1" /> SÍ
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground text-[10px]">Sin tarea</span>
                        )}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-center gap-1">
                          <Button variant={row.unread ? "default" : "outline"} size="sm" className="h-8 px-2" onClick={() => onOpenCase(row)} title="Abrir caso">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className={`h-8 px-2 ${row.unread ? "text-primary border-primary/30 hover:bg-primary/5 bg-primary/5" : "text-muted-foreground hover:text-foreground"}`}
                            onClick={(e) => onToggleReadStatus(row, e)}
                            title={row.unread ? "Marcar como leído" : "Marcar como no leído"}
                          >
                            {row.unread ? <Mail className="h-4 w-4" /> : <MailOpen className="h-4 w-4" />}
                          </Button>
                          <Button variant="outline" size="sm" className="h-8 px-2 text-destructive border-destructive/50 hover:bg-destructive/10" onClick={() => setCaseToDelete(row)} title="Eliminar caso">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {canPaginate && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground">Página {page} de {totalPages}</p>
              <div className="flex items-center gap-4">
                <form onSubmit={handlePageInputSubmit} className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Ir a:</span>
                  <Input type="number" min={1} max={totalPages} value={pageInput} onChange={handlePageInputChange} className="w-20 h-9 text-center" />
                  <Button type="submit" variant="outline" size="sm">Ir</Button>
                </form>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
                    <ChevronLeft className="h-4 w-4" />Anterior
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
                    Siguiente<ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={!!caseToDelete} onOpenChange={() => setCaseToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar este caso?</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>Estás a punto de eliminar el siguiente radicado:</p>
              <p className="font-mono text-sm bg-muted p-2 rounded">{caseToDelete?.radicado}</p>
              <p className="text-destructive font-medium">Esta acción no se puede deshacer. Se eliminarán también todas las actuaciones asociadas.</p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletingCase}>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteCase} disabled={isDeletingCase} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {isDeletingCase ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Trash2 className="h-4 w-4 mr-2" />}
              Sí, eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={isMassAssignOpen} onOpenChange={setIsMassAssignOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Asignar Abogado Masivamente</AlertDialogTitle>
            <AlertDialogDescription>
              Asignarás el siguiente abogado a {selectedIds.size} caso(s) seleccionado(s). Puedes seleccionar uno existente o escribir uno nuevo.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <label htmlFor="mass-lawyer" className="mb-2 block text-sm font-medium">Nombre del Abogado</label>
            <LawyerCombobox
              options={lawyerOptions}
              value={massAssignLawyer}
              onChange={(val) => setMassAssignLawyer(val)}
              className="w-full"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isAssigningLawyer} onClick={() => setMassAssignLawyer("")}>Cancelar</AlertDialogCancel>
            <Button onClick={handleMassAssignLawyer} disabled={isAssigningLawyer}>
              {isAssigningLawyer ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Confirmar Asignación
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
