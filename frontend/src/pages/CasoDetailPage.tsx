import { useState, useEffect, useMemo, Fragment } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, Calendar, Clock, FileText, Loader2, Filter, AlertCircle, 
  Download, User as UserIcon, Users, Building2, Hash, Paperclip, ChevronDown,
  FileDown, RefreshCw, ArrowRight, UserCheck, Edit3, ChevronRight,
  ExternalLink
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { 
  getCaseByRadicado, 
  getCaseEvents, 
  downloadEventsExcel, 
  downloadEventsByIdExcel,
  getCaseById, 
  getCaseEventsById, 
  getCasePublicationsById,
  getCaseTasks,
  getTasks,
  getUsers,
  getWorkspaces,
  updateCaseLawyer,
  getDocumentosActuacion,
  createTask,
  createList,
  createWorkspace,
  getCaseSourcesHistory,
  buscarNuevamente,
  markCaseRead,
  updateCaseActiveStatus,
  type User,
  type Task as TaskType,
  type CasePublication,
  type Workspace,
  apiFetch
} from '@/services/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PublicacionesPanel } from '@/components/PublicacionesPanel';
import { useAuth } from '@/contexts/AuthContext';
import { CheckCircle2, ListPlus, MoreVertical, MessageSquare, Plus, Flag, Trash2, Zap, Database } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from '@/components/ui/select';
import { TaskDrawer } from '@/components/TaskDrawer';

type DocsState = {
  items: any[];
  rawResponse: any;
  error?: string;
};

export default function CasoDetailPage() {
  const { radicado, id } = useParams<{ radicado: string, id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  
  const isSuperAdmin = user?.is_superadmin || (user?.is_admin && !user?.company_id) || user?.role === 'SUPERADMIN';
  
  const [caseData, setCaseData] = useState<any>(null);
  const [multisourceChecks, setMultisourceChecks] = useState<any[]>([]);
  const [isLoadingMultisource, setIsLoadingMultisource] = useState(false);
  const [isCheckingMultisource, setIsCheckingMultisource] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const [eventsWarning, setEventsWarning] = useState<string | null>(null);
  const [publications, setPublications] = useState<CasePublication[]>([]);
  const [tasks, setTasks] = useState<TaskType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
  const [isLoadingPubs, setIsLoadingPubs] = useState(false);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [multipleCases, setMultipleCases] = useState<any[] | null>(null);
  const [selectedTask, setSelectedTask] = useState<TaskType | null>(null);
  const [systemUsers, setSystemUsers] = useState<User[]>([]);
  const [clickupToken, setClickupToken] = useState<string | null>(null);

  // Workspaces and lists state for task destination
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | undefined>(undefined);
  const [selectedListId, setSelectedListId] = useState<number | string | undefined>(undefined);
  const [newListName, setNewListName] = useState('');
  const [isRetiring, setIsRetiring] = useState(false);
  const [retiroMotivo, setRetiroMotivo] = useState('');

  const getWorkspaceLists = (ws: Workspace) => {
    const directLists = ws.lists || [];
    const folderLists = (ws.folders || []).flatMap(f => f.lists || []);
    const allLists = [...directLists, ...folderLists];
    return Array.from(new Map(allLists.map(l => [l.id, l])).values());
  };

  const getAllWorkspaceListsSorted = () => {
    const allLists: Array<{ id: number; name: string; wsId: number; wsName: string; isCurrentWs: boolean }> = [];
    workspaces.forEach(ws => {
      const isCurrentWs = ws.id === selectedWorkspaceId;
      const direct = ws.lists || [];
      const fromFolders = (ws.folders || []).flatMap(f => f.lists || []);
      
      direct.forEach(l => {
        allLists.push({ id: l.id, name: l.name, wsId: ws.id, wsName: ws.name, isCurrentWs });
      });
      fromFolders.forEach(l => {
        allLists.push({ id: l.id, name: l.name, wsId: ws.id, wsName: ws.name, isCurrentWs });
      });
    });

    // Sort: Prioritize current workspace lists first, then alphabetically by workspace and list name
    allLists.sort((a, b) => {
      if (a.isCurrentWs && !b.isCurrentWs) return -1;
      if (!a.isCurrentWs && b.isCurrentWs) return 1;
      const wsComp = a.wsName.localeCompare(b.wsName);
      if (wsComp !== 0) return wsComp;
      return a.name.localeCompare(b.name);
    });

    // Deduplicate by list ID
    const seen = new Set();
    return allLists.filter(item => {
      const duplicate = seen.has(item.id);
      seen.add(item.id);
      return !duplicate;
    });
  };

  // Inline task creation form states
  const [showCreateTaskForm, setShowCreateTaskForm] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDescription, setNewTaskDescription] = useState('');
  const [newTaskAssigneeId, setNewTaskAssigneeId] = useState<number | undefined>(undefined);
  const [newTaskGestiones, setNewTaskGestiones] = useState<Array<{
    title: string;
    due_date: string;
    priority: string;
    assignee_id: number | undefined;
  }>>([{ title: '', due_date: '', priority: 'normal', assignee_id: undefined }]);
  
  const [searchText, setSearchText] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const [expandedDocs, setExpandedDocs] = useState<Record<number, DocsState>>({});
  const [loadingDocs, setLoadingDocs] = useState<Record<number, boolean>>({});

  const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
  const cleanBaseUrl = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL;

  useEffect(() => {
    const token = localStorage.getItem('clickup_token');
    if (token) setClickupToken(token);
  }, []);

  useEffect(() => {
    if (!radicado && !id) return;

    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      setMultipleCases(null);
      
      try {
        let result: any = null;
        let activeRadicado = '';

        if (id) {
          result = await getCaseById(Number(id));
          activeRadicado = result.radicado;
          
          setIsLoadingEvents(true);
          setIsLoadingPubs(true);
          try {
            const [eventsResult, pubsResult] = await Promise.all([
              getCaseEventsById(Number(id)),
              getCasePublicationsById(Number(id))
            ]);
            setEvents(eventsResult.items || []);
            setEventsWarning(eventsResult.warning || null);
            setPublications(pubsResult.items || []);
            if (pubsResult && (pubsResult as any).sync_pub_status !== undefined) {
              setCaseData((prev: any) => prev ? {
                ...prev,
                sync_pub_status: (pubsResult as any).sync_pub_status,
                sync_pub_progress: (pubsResult as any).sync_pub_progress
              } : null);
            }
          } catch (e) {
            console.error('Error cargando adicionales por ID:', e);
          } finally {
            setIsLoadingEvents(false);
            setIsLoadingPubs(false);
          }
        } else if (radicado) {
          const decoded = decodeURIComponent(radicado);
          const results = await getCaseByRadicado(decoded);
          
          if (results.length === 1) {
            result = results[0];
            activeRadicado = result.radicado;
            
            setIsLoadingEvents(true);
            setIsLoadingPubs(true);
            try {
              const [eventsResult, pubsResult] = await Promise.all([
                getCaseEventsById(result.id),
                getCasePublicationsById(result.id)
              ]);
              setEvents(eventsResult.items || []);
              setEventsWarning(eventsResult.warning || null);
              setPublications(pubsResult.items || []);
              if (pubsResult && (pubsResult as any).sync_pub_status !== undefined) {
                setCaseData((prev: any) => prev ? {
                  ...prev,
                  sync_pub_status: (pubsResult as any).sync_pub_status,
                  sync_pub_progress: (pubsResult as any).sync_pub_progress
                } : null);
              }
            } catch (e) {
              console.error('Error cargando adicionales por radicado:', e);
            } finally {
              setIsLoadingEvents(false);
              setIsLoadingPubs(false);
            }
          } else if (results.length > 1) {
            setMultipleCases(results);
            setIsLoading(false);
            return;
          } else {
            throw new Error("No se encontró el caso");
          }
        }

        if (!result) return;
        
        setCaseData(result);
        if (result.id) {
          fetchMultisourceChecks(result.id);
        }
        
        // Cargar tareas relacionadas
        setIsLoadingTasks(true);
        try {
          const tResult = await getTasks({ radicado: activeRadicado });
          setTasks(tResult);
        } catch (e) {
          console.error("Error cargando tareas:", e);
        } finally {
          setIsLoadingTasks(false);
        }

        if (result.id && result.unread) {
          try { await markCaseRead(result.id); } catch {}
        }
      } catch (e: any) {
        console.error('Error:', e);
        setError(e?.message || 'Error al cargar el caso');
        toast({
          title: 'Error al cargar el caso',
          description: e?.message || 'Error desconocido',
          variant: 'destructive',
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
    getUsers().then(setSystemUsers).catch(console.error);
    getWorkspaces().then(wsList => {
      const uniqueWS = Array.from(new Map(wsList.map(ws => [ws.id, ws])).values());
      setWorkspaces(uniqueWS);
      if (uniqueWS.length > 0) {
        // Encontrar la primera lista disponible en cualquier workspace
        let defaultListId: number | undefined = undefined;
        let defaultWsId = uniqueWS[0].id;
        
        for (const ws of uniqueWS) {
          const direct = ws.lists || [];
          const fromFolders = (ws.folders || []).flatMap(f => f.lists || []);
          const wsLists = [...direct, ...fromFolders];
          if (wsLists.length > 0) {
            defaultListId = wsLists[0].id;
            defaultWsId = ws.id;
            break;
          }
        }
        
        setSelectedWorkspaceId(defaultWsId);
        if (defaultListId) {
          setSelectedListId(defaultListId);
        }
      }
    }).catch(console.error);
  }, [radicado, id, toast]);

  const fetchMultisourceChecks = async (caseId: number) => {
    setIsLoadingMultisource(true);
    try {
      if (caseData?.radicado) {
        const res = await getCaseSourcesHistory(caseData.radicado);
        setMultisourceChecks(res || []);
      } else {
        const res = await apiFetch<any[]>(`/api/cases/${caseId}/multisource-checks`);
        setMultisourceChecks(res || []);
      }
    } catch (e) {
      console.error("Error fetching multisource checks:", e);
    } finally {
      setIsLoadingMultisource(false);
    }
  };

  const [isRefreshingFallback, setIsRefreshingFallback] = useState(false);

  const handleBuscarNuevamente = async () => {
    if (!caseData?.radicado) return;
    setIsRefreshingFallback(true);
    toast({
      title: "Búsqueda con fallback iniciada",
      description: "Consultando Rama Judicial principal y fuentes alternativas..."
    });
    try {
      const res = await buscarNuevamente(caseData.radicado, caseData.company_id);
      if (res && res.status === "error") {
        toast({
          title: "Error al buscar",
          description: res.message || "Ocurrió un error en el motor de búsqueda",
          variant: "destructive"
        });
      } else {
        toast({
          title: "Búsqueda finalizada",
          description: res.message || "Se completó la verificación con fuentes oficiales."
        });
        // Reload case details
        if (id) {
          getCaseById(Number(id)).then(setCaseData).catch(console.error);
        } else if (radicado) {
          getCaseByRadicado(radicado).then(res => {
            if (res && res.length > 0) setCaseData(res[0]);
          }).catch(console.error);
        }
        // Refresh sources history
        fetchMultisourceChecks(caseData.id);
      }
    } catch (e: any) {
      toast({
        title: "Error",
        description: e.message || "Error al realizar la búsqueda con fallbacks",
        variant: "destructive"
      });
    } finally {
      setIsRefreshingFallback(false);
    }
  };

  const handleTriggerMultisourceCheck = async () => {
    if (!caseData?.id) return;
    setIsCheckingMultisource(true);
    try {
      await apiFetch(`/api/cases/${caseData.id}/multisource-check`, {
        method: 'POST'
      });
      toast({
        title: "Búsqueda encolada",
        description: "Se ha iniciado la consulta en otras fuentes. Los resultados se actualizarán en segundo plano."
      });
      
      // Auto-refresh the log list after 5 seconds to show progress
      setTimeout(() => {
        if (caseData?.id) {
          fetchMultisourceChecks(caseData.id);
        }
      }, 5000);
    } catch (e: any) {
      toast({
        title: "Error al iniciar búsqueda",
        description: e.message || "No se pudo iniciar la consulta multifuente.",
        variant: "destructive"
      });
    } finally {
      setIsCheckingMultisource(false);
    }
  };

  const getSourceStatus = (sourceName: string) => {
    // Find the most recent check log for this source
    const check = multisourceChecks.find((l: any) => l.source === sourceName);
    if (!check) return { status: 'no_consultado', label: 'No consultado', color: 'bg-slate-100 text-slate-700 border-slate-200' };
    
    const st = check.status;
    if (st === 'skipped') return { status: 'no_consultado', label: 'No consultado', color: 'bg-slate-100 text-slate-700 border-slate-200', details: check };
    if (st === 'success') {
      const hasRecords = check.records_found > 0;
      return { 
        status: 'success', 
        label: hasRecords ? 'Encontrado' : 'Sin resultado', 
        color: hasRecords ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-blue-50 text-blue-700 border-blue-200',
        details: check
      };
    }
    if (st === 'error') return { status: 'error', label: 'Error', color: 'bg-rose-50 text-rose-700 border-rose-200', details: check };
    if (st === 'unsupported') return { status: 'unsupported', label: 'Requiere validación manual', color: 'bg-amber-50 text-amber-700 border-amber-200', details: check };
    return { status: 'pending', label: 'Consultando', color: 'bg-yellow-50 text-yellow-700 border-yellow-200', details: check };
  };

  const handleUpdateLawyer = async (newLawyer: string) => {
    if (!caseData?.id) return;
    try {
      const res = await updateCaseLawyer(caseData.id, newLawyer);
      setCaseData({ ...caseData, abogado: res.abogado, user_id: res.user_id } as any);
      toast({ title: 'Abogado actualizado', description: `Asignado a: ${res.abogado}` });
    } catch (e) {
      toast({ title: 'Error', description: 'No se pudo actualizar el abogado', variant: 'destructive' });
    }
  };

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      if (searchText) {
        const search = searchText.toLowerCase();
        const title = (event.title || '').toLowerCase();
        const detail = (event.detail || '').toLowerCase();
        if (!title.includes(search) && !detail.includes(search)) return false;
      }
      if (dateFrom && event.event_date < dateFrom) return false;
      if (dateTo && event.event_date > dateTo) return false;
      return true;
    });
  }, [events, searchText, dateFrom, dateTo]);

  const actuacionesConDocumentos = useMemo(
    () => events.filter(e => e.con_documentos).length,
    [events]
  );

  const handleDownloadExcel = () => {
    if (id || caseData?.id) {
      downloadEventsByIdExcel(Number(id || caseData?.id));
    } else if (radicado || caseData?.radicado) {
      const r = radicado || caseData?.radicado;
      if (r) downloadEventsExcel(decodeURIComponent(r));
    } else {
      return;
    }
    toast({ title: 'Descargando...', description: 'El archivo Excel se descargará en unos segundos' });
  };

  const handleToggleDocumentos = async (event: any) => {
    const idReg: number = event.id_reg_actuacion;
    const r = radicado || caseData?.radicado;
    if (!idReg || !r) return;

    // Si ya está expandido → colapsar
    if (expandedDocs[idReg]) {
      setExpandedDocs(prev => {
        const copy = { ...prev };
        delete copy[idReg];
        return copy;
      });
      return;
    }

    setLoadingDocs(prev => ({ ...prev, [idReg]: true }));

    try {
      const decoded = caseData?.radicado || (radicado ? decodeURIComponent(radicado) : '');
      const result = await getDocumentosActuacion(decoded, idReg);

      setExpandedDocs(prev => ({
        ...prev,
        [idReg]: {
          items: result.items || [],
          rawResponse: result,
        },
      }));
    } catch (e: any) {
      console.error('Error cargando documentos:', e);
      const errorMessage = e?.payload?.detail || e?.message || 'Error desconocido';
      setExpandedDocs(prev => ({
        ...prev,
        [idReg]: { items: [], rawResponse: null, error: errorMessage },
      }));
      toast({
        title: 'Rama Judicial no responde',
        description: errorMessage,
        variant: 'destructive',
      });
    } finally {
      setLoadingDocs(prev => ({ ...prev, [idReg]: false }));
    }
  };

  const handleRefresh = async () => {
    const r = radicado || caseData?.radicado;
    if (!r) return;
    setIsLoading(true);
    setExpandedDocs({});
    const decoded = decodeURIComponent(r);
    try {
      // Si tenemos ID, usamos ID para ser precisos
      if (id || caseData?.id) {
        const result = await getCaseById(Number(id || caseData?.id));
        setCaseData(result);
        
        const [eventsResult, pubsResult, tasksResult] = await Promise.all([
          getCaseEventsById(result.id),
          getCasePublicationsById(result.id),
          getCaseTasks(result.id)
        ]);
        
        setEvents(eventsResult.items || []);
        setEventsWarning(eventsResult.warning || null);
        setPublications(pubsResult.items || []);
        setTasks(tasksResult || []);
        if (pubsResult && (pubsResult as any).sync_pub_status !== undefined) {
          setCaseData((prev: any) => prev ? {
            ...prev,
            sync_pub_status: (pubsResult as any).sync_pub_status,
            sync_pub_progress: (pubsResult as any).sync_pub_progress
          } : null);
        }
      } else {
        // Fallback a radicado (solo si no hay ID, ej. búsqueda inicial)
        const results = await getCaseByRadicado(decoded);
        if (results.length === 1) {
          setCaseData(results[0]);
            const [eventsResult, pubsResult, tasksResult] = await Promise.all([
              getCaseEventsById(results[0].id),
              getCasePublicationsById(results[0].id),
              getCaseTasks(results[0].id)
            ]);
            setEvents(eventsResult.items || []);
            setEventsWarning(eventsResult.warning || null);
            setPublications(pubsResult.items || []);
            setTasks(tasksResult || []);
            if (pubsResult && (pubsResult as any).sync_pub_status !== undefined) {
              setCaseData((prev: any) => prev ? {
                ...prev,
                sync_pub_status: (pubsResult as any).sync_pub_status,
                sync_pub_progress: (pubsResult as any).sync_pub_progress
              } : null);
            }
        } else if (results.length > 1) {
          setMultipleCases(results);
        } else {
          throw new Error("No se encontró el caso");
        }
      }
      
      const currentCaseId = id || caseData?.id;
      if (currentCaseId) {
        fetchMultisourceChecks(Number(currentCaseId));
      }
      
      toast({ title: 'Actualizado', description: 'Información del caso actualizada' });
    } catch (e: any) {
      toast({ title: 'Error', description: e?.message || 'Error al actualizar', variant: 'destructive' });
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return '—';
    try {
      const d = dateString.includes('T') ? dateString : `${dateString}T12:00:00`;
      return new Date(d).toLocaleDateString('es-CO', { year: 'numeric', month: 'long', day: 'numeric' });
    } catch { return dateString; }
  };

  const formatShortDate = (dateString: string) => {
    if (!dateString) return '—';
    try {
      const d = dateString.includes('T') ? dateString : `${dateString}T12:00:00`;
      return new Date(d).toLocaleDateString('es-CO', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch { return dateString; }
  };

  const handleCreateTask = () => {
    if (!caseData) return;
    
    let assigneeId: number | undefined = undefined;
    if (caseData.abogado && systemUsers.length > 0) {
      const match = systemUsers.find(u => 
        u.nombre?.toLowerCase().includes(caseData.abogado!.toLowerCase()) || 
        caseData.abogado!.toLowerCase().includes(u.nombre?.toLowerCase() || '')
      );
      if (match) assigneeId = match.id;
    }

    // Por defecto, inicializar la lista de destino en Ninguna (sin sincronizar)
    setSelectedListId('none');
    if (workspaces.length > 0) {
      const currentWsId = selectedWorkspaceId ?? workspaces[0].id;
      setSelectedWorkspaceId(currentWsId);
    }

    setNewTaskTitle(`Gestión para Radicado: ${caseData.radicado}`);
    setNewTaskAssigneeId(assigneeId);
    setNewTaskGestiones([{ title: '', due_date: '', priority: 'normal', assignee_id: assigneeId }]);
    setShowCreateTaskForm(true);
  };

  const handleCreateTaskWithGestiones = async () => {
    if (!caseData) return;
    
    const validGestiones = newTaskGestiones.filter(g => g.title.trim() !== '');
    if (validGestiones.length === 0) {
      toast({ title: 'Agrega al menos una gestión', description: 'Escribe el nombre de la actividad técnica.', variant: 'destructive' });
      return;
    }

    // Resolver ID de lista final
    let listIdToUse: number | undefined = undefined;

    if (selectedListId === 'new') {
      if (!newListName.trim()) {
        toast({ title: 'Error', description: 'Por favor escribe el nombre de la nueva lista.', variant: 'destructive' });
        return;
      }
      let wsId = selectedWorkspaceId || (workspaces.length > 0 ? workspaces[0].id : undefined);
      if (!wsId) {
        try {
          const newWs = await createWorkspace({ name: "Espacio Interno EMDECOB" });
          wsId = newWs.id;
          const freshWorkspaces = await getWorkspaces();
          setWorkspaces(freshWorkspaces);
        } catch (err: any) {
          toast({ title: 'Error al crear espacio de trabajo', description: err.message || 'Error desconocido', variant: 'destructive' });
          return;
        }
      }
      try {
        const newList = await createList({ name: newListName.trim(), workspace_id: wsId });
        listIdToUse = newList.id;
        // Actualizar localmente la lista de workspaces
        const freshWorkspaces = await getWorkspaces();
        setWorkspaces(freshWorkspaces);
      } catch (err: any) {
        toast({ title: 'Error al crear lista en ClickUp', description: err.message || 'Error desconocido', variant: 'destructive' });
        return;
      }
    } else if (selectedListId === 'none') {
      listIdToUse = undefined;
    } else if (selectedListId) {
      listIdToUse = typeof selectedListId === 'string' ? parseInt(selectedListId) : selectedListId;
    }

    // Intentar auto-seleccionar lista si no hay una seleccionada y no se eligió 'none'
    if (!listIdToUse && selectedListId !== 'none' && workspaces.length > 0) {
      let defaultListId: number | undefined = undefined;
      let defaultWsId = selectedWorkspaceId ?? workspaces[0].id;
      
      for (const ws of workspaces) {
        const direct = ws.lists || [];
        const fromFolders = (ws.folders || []).flatMap(f => f.lists || []);
        const wsLists = [...direct, ...fromFolders];
        if (wsLists.length > 0) {
          defaultListId = wsLists[0].id;
          defaultWsId = ws.id;
          break;
        }
      }
      
      listIdToUse = defaultListId;
      if (listIdToUse) {
        setSelectedListId(listIdToUse);
        setSelectedWorkspaceId(defaultWsId);
      }
    }

    // Si no hay lista de destino asignada, el backend se encargará de buscar o crear 
    // automáticamente una lista y un espacio por defecto ("Espacio Interno EMDECOB").

    try {
      // 1. Crear tarea padre
      const parentTask = await createTask({
        title: newTaskTitle || `Gestión para Radicado: ${caseData.radicado}`,
        description: newTaskDescription || `Gestión para Radicado: ${caseData.radicado}`,
        status: 'to do',
        priority: 'normal',
        case_id: caseData.id,
        assignee_id: newTaskAssigneeId,
        list_id: listIdToUse
      });

      // 2. Crear cada gestión como subtarea
      for (const gestion of validGestiones) {
        await createTask({
          title: gestion.title,
          parent_id: parentTask.id,
          due_date: gestion.due_date ? new Date(gestion.due_date).toISOString() : undefined,
          priority: gestion.priority,
          assignee_id: gestion.assignee_id,
          case_id: caseData.id,
          list_id: parentTask.list_id,
          status: 'to do'
        } as any);
      }

      // 3. Refrescar lista de tareas
      const refreshedTasks = await getCaseTasks(caseData.id);
      setTasks(refreshedTasks);

      // 4. Limpiar formulario
      setShowCreateTaskForm(false);
      setNewTaskTitle('');
      setNewTaskDescription('');
      setNewListName('');
      setNewTaskGestiones([{ title: '', due_date: '', priority: 'normal', assignee_id: undefined }]);

      toast({ title: '✅ Tarea creada', description: `Se creó la tarea con ${validGestiones.length} gestión(es) técnica(s).` });
    } catch (error: any) {
      console.error('Error creating task with gestiones:', error);
      toast({ title: 'Error al crear tarea', description: String(error.message || 'Error desconocido'), variant: 'destructive' });
    }
  };

  const addGestionRow = () => {
    setNewTaskGestiones(prev => [...prev, { title: '', due_date: '', priority: 'normal', assignee_id: newTaskAssigneeId }]);
  };

  const removeGestionRow = (index: number) => {
    setNewTaskGestiones(prev => prev.filter((_, i) => i !== index));
  };

  const updateGestionRow = (index: number, field: string, value: any) => {
    setNewTaskGestiones(prev => prev.map((g, i) => i === index ? { ...g, [field]: value } : g));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error && !caseData) {
    return (
      <div className="space-y-6">
        <div className="flex items-start gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold">Error</h1>
        </div>
        <Card className="border-red-500/50 bg-red-500/5">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <AlertCircle className="h-8 w-8 text-red-500" />
              <div>
                <h3 className="font-semibold">No se pudo cargar el caso</h3>
                <p className="text-sm text-muted-foreground mt-1">{error}</p>
              </div>
            </div>
            <div className="mt-4">
              <Button variant="outline" onClick={() => navigate(-1)}>Volver</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (multipleCases) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold">Múltiples procesos encontrados</h1>
        </div>
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="pt-6">
            <p className="mb-6">El radicado <strong>{radicado}</strong> tiene varios procesos registrados. Por favor selecciona el que deseas ver:</p>
            <div className="grid gap-4">
              {multipleCases.map(c => (
                <Card key={c.id} className="cursor-pointer hover:bg-muted/50 transition-colors border-primary/20" onClick={() => navigate(`/casos/id/${c.id}`)}>
                  <CardContent className="p-4 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-primary">{c.juzgado || 'Juzgado no especificado'}</p>
                      <p className="text-sm text-muted-foreground">ID Proceso: {c.id_proceso || 'N/A'}</p>
                      <p className="text-sm text-muted-foreground">{c.demandante} vs {c.demandado}</p>
                    </div>
                    <ArrowRight className="h-5 w-5 text-muted-foreground" />
                  </CardContent>
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!caseData) return null;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold tracking-tight">Detalle del Proceso</h1>
              {caseData.encontrado_en_fuente_alternativa && (
                <span className={`text-[10px] uppercase font-extrabold px-2 py-0.5 rounded-full border flex items-center gap-1 ${
                  caseData.requiere_revision 
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-600' 
                    : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600'
                }`}>
                  <AlertCircle className="h-3 w-3" />
                  Alternativo
                </span>
              )}
            </div>
            <p className="font-mono text-primary text-sm mt-1">{caseData.radicado}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {caseData.encontrado_en_fuente_alternativa && (
            <Button 
              onClick={handleBuscarNuevamente} 
              disabled={isRefreshingFallback} 
              variant="outline" 
              size="sm" 
              className="bg-primary/5 border-primary/20 text-primary hover:bg-primary/10 transition-colors"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshingFallback ? 'animate-spin' : ''}`} />
              Buscar nuevamente
            </Button>
          )}
          <Button onClick={handleRefresh} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Actualizar
          </Button>
          {events.length > 0 && (
            <Button onClick={handleDownloadExcel} variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Exportar Excel
            </Button>
          )}
        </div>
      </div>

      {/* Alerta de Fuente Alternativa / Requiere Revisión */}
      {caseData.encontrado_en_fuente_alternativa && (
        <div className={`p-4 rounded-xl border flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 ${
          caseData.requiere_revision 
            ? 'bg-amber-500/10 border-amber-500/30 text-amber-800' 
            : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-800'
        }`}>
          <div className="flex items-start gap-3">
            <AlertCircle className={`h-5 w-5 mt-0.5 flex-shrink-0 ${caseData.requiere_revision ? 'text-amber-600' : 'text-emerald-600'}`} />
            <div>
              <p className="font-bold text-sm">
                Encontrado en fuente alternativa: {caseData.fuente_encontrado || 'Publicaciones Procesales'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {caseData.requiere_revision 
                  ? 'Este caso requiere revisión. Los datos provienen de una fuente externa y podrían ser parciales (Confianza: ' + (caseData.confianza_busqueda || 'N/A') + '%).'
                  : 'Los datos coinciden plenamente con el radicado buscado (Confianza: ' + (caseData.confianza_busqueda || 'N/A') + '%).'
                }
              </p>
            </div>
          </div>
          {caseData.url_fuente && (
            <Button 
              size="sm" 
              onClick={() => window.open(caseData.url_fuente, "_blank")} 
              className={`font-semibold shrink-0 gap-1.5 ${
                caseData.requiere_revision 
                  ? 'bg-amber-600 hover:bg-amber-500 text-white' 
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white'
              }`}
            >
              <ExternalLink className="h-4 w-4" />
              Abrir fuente oficial
            </Button>
          )}
        </div>
      )}

      {/* Información General */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            Información General
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {[
              { icon: Hash,      label: 'RADICADO',          value: caseData.radicado,                    mono: true },
              { icon: UserIcon,  label: 'DEMANDANTE',        value: caseData.demandante || '—' },
              { icon: Users,     label: 'DEMANDADO',         value: caseData.demandado  || '—' },
              { icon: Building2, label: 'JUZGADO',           value: caseData.juzgado    || '—' },
              { icon: Calendar,  label: 'FECHA RADICACIÓN',  value: formatDate(caseData.fecha_radicacion) },
              { icon: Clock,     label: 'ÚLTIMA ACTUACIÓN',  value: formatDate(caseData.ultima_actuacion) },
            ].map(({ icon: Icon, label, value, mono }) => (
              <div key={label} className="space-y-1 p-3 rounded-lg bg-muted/30">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Icon className="h-3 w-3" />
                  {label}
                </div>
                <p className={`text-sm font-medium break-all ${mono ? 'font-mono' : ''}`}>{value}</p>
              </div>
            ))}
            
            {/* ABOGADO SELECTOR */}
            <div className="space-y-1 p-3 rounded-lg bg-primary/5 border border-primary/10">
              <div className="flex items-center gap-2 text-xs text-primary font-semibold">
                <UserCheck className="h-3 w-3" />
                ABOGADO RESPONSABLE
              </div>
              <select 
                className="w-full bg-transparent text-sm font-bold border-none focus:ring-0 cursor-pointer text-primary"
                value={caseData.abogado || ''}
                onChange={(e) => handleUpdateLawyer(e.target.value)}
              >
                <option value="">Sin asignar</option>
                {(() => {
                  const uniqueLawyers = Array.from(new Set([
                    caseData.abogado,
                    ...tasks.map(t => t.assignee_name),
                    ...systemUsers.map(u => u.nombre || u.username)
                  ].filter(Boolean) as string[]));
                  return uniqueLawyers.map(name => (
                    <option key={name} value={name}>{name}</option>
                  ));
                })()}
              </select>
            </div>

            {/* ID PROCESO (MANUAL OVERRIDE) - SENIOR FEATURE */}
            <div className="space-y-1 p-3 rounded-lg bg-orange-500/5 border border-orange-500/10">
              <div className="flex items-center gap-2 text-xs text-orange-600 font-semibold">
                <ChevronRight className="h-3 w-3" />
                ID PROCESO (RAMA)
              </div>
              <div className="flex items-center gap-2">
                <input 
                  type="text"
                  placeholder="Sin ID"
                  className="w-full bg-transparent text-sm font-mono font-bold border-none focus:ring-0 p-0 text-orange-700"
                  defaultValue={caseData.id_proceso || ''}
                  onBlur={(e) => {
                    if (e.target.value !== caseData.id_proceso) {
                      updateCaseIdProceso(caseData.id, e.target.value)
                        .then(() => toast.success("ID Judicial actualizado"))
                        .catch(() => toast.error("Error al actualizar ID"));
                    }
                  }}
                />
                <Edit3 className="h-3 w-3 text-orange-400" />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Estadísticas */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-teal-500/10 border-teal-500/30">
          <CardContent className="pt-4 pb-4">
            <div className="text-2xl font-bold text-teal-500">{events.length}</div>
            <div className="text-xs text-muted-foreground">Total Actuaciones</div>
          </CardContent>
        </Card>
        <Card className="bg-blue-500/10 border-blue-500/30">
          <CardContent className="pt-4 pb-4">
            <div className="text-2xl font-bold text-blue-500">{actuacionesConDocumentos}</div>
            <div className="text-xs text-muted-foreground">Con Documentos</div>
          </CardContent>
        </Card>
        <Card className="bg-green-500/10 border-green-500/30">
          <CardContent className="pt-4 pb-4">
            <div className="text-2xl font-bold text-green-500 text-base">{formatShortDate(caseData.fecha_radicacion)}</div>
            <div className="text-xs text-muted-foreground">Inicio Proceso</div>
          </CardContent>
        </Card>
        <Card className="bg-orange-500/10 border-orange-500/30">
          <CardContent className="pt-4 pb-4">
            <div className="text-2xl font-bold text-orange-500 text-base">{formatShortDate(caseData.ultima_actuacion)}</div>
            <div className="text-xs text-muted-foreground">Última Actividad</div>
          </CardContent>
        </Card>
      </div>

      {/* Filtros */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Filter className="h-5 w-5 text-primary" />
            Filtrar Actuaciones
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <Input
                placeholder="Buscar en actuaciones..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
              />
            </div>
            <div className="w-[150px]">
              <label className="text-xs text-muted-foreground mb-1 block">Desde</label>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div className="w-[150px]">
              <label className="text-xs text-muted-foreground mb-1 block">Hasta</label>
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
            <Button variant="outline" onClick={() => { setSearchText(''); setDateFrom(''); setDateTo(''); }}>
              Limpiar
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Contenido con Tabs */}
      <Tabs defaultValue="actuaciones" className="w-full">
        <TabsList className="grid w-full max-w-[1000px] grid-cols-5 mb-4">
          <TabsTrigger value="actuaciones" className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Actuaciones
          </TabsTrigger>
          <TabsTrigger value="publicaciones" className="flex items-center gap-2">
            <FileDown className="h-4 w-4" />
            Publicaciones
          </TabsTrigger>
          <TabsTrigger value="tareas" className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            Tareas de Gestión
          </TabsTrigger>
          <TabsTrigger value="multifuente" className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            Fuentes Consultadas
          </TabsTrigger>
          <TabsTrigger value="retirar" className="flex items-center gap-2 data-[state=active]:text-amber-600 data-[state=active]:border-amber-500">
            <ArrowLeft className="h-4 w-4" />
            {caseData?.is_active === false ? 'Radicado Retirado' : 'Retirar Radicado'}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="actuaciones">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  Historial de Actuaciones
                </CardTitle>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-muted-foreground bg-muted px-2 py-1 rounded">
                    {filteredEvents.length} registros
                  </span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {eventsWarning && (
                <div className="mb-4 flex items-center gap-2 text-sm text-amber-600 p-3 bg-amber-500/10 rounded-lg border border-amber-500/30">
                  <AlertCircle className="h-5 w-5 flex-shrink-0" />
                  <p>{eventsWarning}</p>
                </div>
              )}
              {isLoadingEvents ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : filteredEvents.length === 0 ? (
                <div className="text-center py-12">
                  <Calendar className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">No hay actuaciones locales</p>
                </div>
              ) : (
                <div className="overflow-auto max-h-[600px] border rounded-lg">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/50">
                        <TableHead className="w-[110px] sticky top-0 bg-muted z-10">Fecha</TableHead>
                        <TableHead className="w-[200px] sticky top-0 bg-muted z-10">Actuación</TableHead>
                        <TableHead className="sticky top-0 bg-muted z-10">Anotación</TableHead>
                        <TableHead className="w-[60px] sticky top-0 bg-muted z-10 text-center">Docs</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredEvents.map((event, i) => {
                        const idReg: number = event.id_reg_actuacion;
                        const isExpanded  = idReg ? !!expandedDocs[idReg] : false;
                        const isLoadingDoc = idReg ? loadingDocs[idReg]   : false;
                        const docsState: DocsState | undefined = idReg ? expandedDocs[idReg] : undefined;
                        const docs = docsState?.items || [];
                        const hasDocuments = event.con_documentos;

                        return (
                          <Fragment key={i}>
                            <TableRow className={isExpanded ? 'bg-primary/5' : ''}>

                              <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                                {formatShortDate(event.event_date)}
                              </TableCell>

                              <TableCell className="font-medium text-sm">{event.title || '—'}</TableCell>

                              <TableCell className="text-sm text-muted-foreground">
                                <p className="line-clamp-2">{event.detail || '—'}</p>
                              </TableCell>

                              <TableCell className="text-center">
                                {hasDocuments && idReg ? (
                                  <button
                                    onClick={() => handleToggleDocumentos(event)}
                                    disabled={isLoadingDoc}
                                    title="Ver documentos"
                                    className="inline-flex items-center justify-center w-7 h-7 rounded bg-blue-500/10 text-blue-500 hover:bg-blue-500/25 transition-colors disabled:opacity-50"
                                  >
                                    {isLoadingDoc ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : isExpanded ? (
                                      <ChevronDown className="h-3 w-3" />
                                    ) : (
                                      <Paperclip className="h-3 w-3" />
                                    )}
                                  </button>
                                ) : (
                                  <span className="text-muted-foreground text-xs">—</span>
                                )}
                              </TableCell>
                            </TableRow>

                            {isExpanded && docsState && (
                              <TableRow className="bg-primary/5 hover:bg-primary/5">
                                <TableCell colSpan={4} className="py-3">
                                  <div className="pl-6">

                                    <div className="text-xs font-medium text-muted-foreground mb-3 flex items-center gap-2">
                                      <Paperclip className="h-3 w-3" />
                                      DOCUMENTOS ADJUNTOS
                                    </div>

                                    {docsState.error && (
                                      <div className="flex items-center gap-2 text-sm text-red-500 p-3 bg-red-500/10 rounded-lg border border-red-500/30">
                                        <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                        Error al consultar: {docsState.error}
                                      </div>
                                    )}

                                    {docs.length === 0 && !docsState.error && (
                                      <div className="flex items-center gap-2 text-sm text-muted-foreground p-3 bg-muted/30 rounded-lg border border-border">
                                        <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                        No se encontraron documentos disponibles para esta actuación.
                                      </div>
                                    )}

                                    {docs.length > 0 && (
                                      <div className="space-y-2">
                                        {docs.map((doc: any, j: number) => {
                                          const docId =
                                            doc.idRegDocumento       ??
                                            doc.idRegistroDocumento  ??
                                            doc.IdRegDocumento       ??
                                            doc.IdRegistroDocumento  ??
                                            doc.idDocumento          ??
                                            doc.id                   ??
                                            null;

                                          const docName =
                                            doc.nombre          ||
                                            doc.Nombre          ||
                                            doc.nombreDocumento ||
                                            doc.NombreDocumento ||
                                            doc.nombreArchivo   ||
                                            doc.NombreArchivo   ||
                                            `Documento ${j + 1}`;

                                          const docDate =
                                            doc.fechaCarga   ||
                                            doc.fechaCargue  ||
                                            doc.FechaCargue  ||
                                            doc.fechaRegistro ||
                                            doc.FechaRegistro ||
                                            doc.fecha        ||
                                            '';

                                          const authToken = localStorage.getItem("token") || localStorage.getItem("access_token");
                                          const downloadUrl = doc.url 
                                            ? doc.url 
                                            : (docId ? `${cleanBaseUrl}/documentos/${docId}/descargar${authToken ? `?token=${encodeURIComponent(authToken)}` : ''}` : null);

                                          return (
                                            <div
                                              key={j}
                                              className="flex items-center justify-between gap-4 p-3 rounded-lg bg-background border border-border shadow-sm"
                                            >
                                              <div className="flex items-center gap-3 min-w-0">
                                                <FileDown className="h-5 w-5 text-red-500 flex-shrink-0" />
                                                <div className="min-w-0">
                                                  <p className="text-sm font-semibold truncate">{docName}</p>
                                                  {docDate && (
                                                    <p className="text-xs text-muted-foreground mt-0.5">
                                                      {formatShortDate(docDate)}
                                                    </p>
                                                  )}
                                                </div>
                                              </div>

                                              {downloadUrl ? (
                                                <a
                                                  href={downloadUrl}
                                                  target="_blank"
                                                  rel="noopener noreferrer"
                                                  className="inline-flex items-center gap-2 whitespace-nowrap rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 flex-shrink-0"
                                                  onClick={() => toast({ title: "Abriendo documento", description: "El documento oficial se abrirá en una nueva pestaña" })}
                                                >
                                                  <FileDown className="h-4 w-4" />
                                                  Ver / Descargar PDF
                                                </a>
                                              ) : (
                                                <Button disabled size="sm" variant="outline">
                                                  No disponible
                                                </Button>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    )}

                                  </div>
                                </TableCell>
                              </TableRow>
                            )}
                          </Fragment>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="publicaciones">
          <Card>
            <CardContent className="pt-6">
              <PublicacionesPanel 
                radicado={caseData?.radicado || decodeURIComponent(radicado || '')} 
                caseId={caseData?.id}
                publications={publications}
                isLoading={isLoadingPubs}
                onRefresh={(newPubs) => setPublications(newPubs)}
                initialSyncStatus={caseData?.sync_pub_status}
                initialSyncProgress={caseData?.sync_pub_progress}
                isSuperAdmin={isSuperAdmin}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tareas">
          <Card className="border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-primary" />
                  Tareas Vinculadas
                </CardTitle>
                <CardDescription>Seguimiento de gestión para este radicado</CardDescription>
              </div>
              {!user?.sync_with_clickup && (
                <Button size="sm" onClick={handleCreateTask} className="bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all">
                  <ListPlus className="h-4 w-4 mr-2" />
                  Lanzar Tarea
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {/* Formulario inline de creación de tarea + gestiones */}
              {showCreateTaskForm && (
                <div className="mb-6 p-6 bg-card border-2 border-primary/30 rounded-2xl space-y-5 shadow-xl animate-in slide-in-from-top-2 duration-300">
                  <div className="flex items-center gap-3 pb-3 border-b border-border/50">
                    <Zap className="h-5 w-5 text-primary" />
                    <h3 className="text-sm font-bold uppercase tracking-widest text-primary">Nueva Tarea de Gestión</h3>
                  </div>

                  {/* Título y responsable general */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Título de la tarea</label>
                      <Input 
                        value={newTaskTitle} 
                        onChange={(e) => setNewTaskTitle(e.target.value)} 
                        placeholder="Gestión para Radicado..." 
                        className="h-10 bg-background border-border/60 rounded-xl text-sm font-semibold" 
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Responsable General</label>
                      <Select value={newTaskAssigneeId?.toString() || ''} onValueChange={(v) => setNewTaskAssigneeId(v ? parseInt(v) : undefined)}>
                        <SelectTrigger className="h-10 bg-background border-border/60 rounded-xl text-sm font-semibold">
                          <SelectValue placeholder="Asignar abogado..." />
                        </SelectTrigger>
                        <SelectContent>
                          {systemUsers.map(u => <SelectItem key={u.id} value={u.id.toString()}>{u.nombre || u.username}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Descripción de la tarea / proceso */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Descripción del proceso / tarea</label>
                    <Textarea 
                      value={newTaskDescription} 
                      onChange={(e) => setNewTaskDescription(e.target.value)} 
                      placeholder="Escribe detalles adicionales sobre este proceso o las gestiones a realizar..." 
                      className="min-h-[80px] bg-background border-border/60 rounded-xl text-sm font-semibold p-3" 
                    />
                  </div>

                  {/* Espacio y Lista de destino */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {workspaces.length === 0 && (
                      <div className="md:col-span-2 p-3 bg-sky-500/5 border border-sky-500/15 rounded-xl text-[10px] text-sky-600 dark:text-sky-400 font-medium">
                        💡 No tienes espacios de trabajo creados. Al seleccionar "➕ Crear nueva lista..." se creará un espacio interno automáticamente.
                      </div>
                    )}
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Espacio de Trabajo (ClickUp)</label>
                      <Select 
                        value={selectedWorkspaceId?.toString() || ''} 
                        onValueChange={(v) => {
                          const wsId = v ? parseInt(v) : undefined;
                          setSelectedWorkspaceId(wsId);
                          if (wsId) {
                            const ws = workspaces.find(w => w.id === wsId);
                            if (ws) {
                              const wsLists = getWorkspaceLists(ws);
                              if (wsLists.length > 0) {
                                setSelectedListId(wsLists[0].id);
                              }
                            }
                          }
                        }}
                      >
                        <SelectTrigger className="h-10 bg-background border-border/60 rounded-xl text-sm font-semibold">
                          <SelectValue placeholder="Seleccionar Espacio..." />
                        </SelectTrigger>
                        <SelectContent>
                          {workspaces.map(ws => (
                            <SelectItem key={ws.id} value={ws.id.toString()}>{ws.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Lista de Destino</label>
                      <Select 
                        value={selectedListId?.toString() || ''} 
                        onValueChange={(v) => {
                          const listId = v ? (['none', 'new'].includes(v) ? v : parseInt(v)) : undefined;
                          setSelectedListId(listId);
                          if (typeof listId === 'number') {
                            const lists = getAllWorkspaceListsSorted();
                            const matched = lists.find(l => l.id === listId);
                            if (matched) {
                              setSelectedWorkspaceId(matched.wsId);
                            }
                          }
                        }}
                      >
                        <SelectTrigger className="h-10 bg-background border-border/60 rounded-xl text-sm font-semibold">
                          <SelectValue placeholder="Seleccionar Lista..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">❌ Ninguna (Solo local / Sin sincronizar)</SelectItem>
                          {(() => {
                            const lists = getAllWorkspaceListsSorted();
                            return lists.map(l => (
                              <SelectItem key={l.id} value={l.id.toString()}>
                                {l.isCurrentWs ? l.name : `[${l.wsName}] ${l.name}`}
                              </SelectItem>
                            ));
                          })()}
                          <SelectItem value="new">➕ Crear nueva lista...</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {selectedListId === 'new' && (
                      <div className="space-y-1.5 md:col-span-2 animate-in slide-in-from-top-2 duration-200">
                        <label className="text-[10px] font-bold text-primary uppercase tracking-widest">Nombre de la nueva Lista ClickUp</label>
                        <Input 
                          value={newListName}
                          onChange={(e) => setNewListName(e.target.value)}
                          placeholder="Ej. Sincronización Proceso 11001..."
                          className="h-10 bg-background border-primary/50 rounded-xl text-sm font-semibold px-4"
                        />
                      </div>
                    )}
                  </div>

                  {/* Gestiones técnicas */}
                  <div className="space-y-3 pt-2">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-bold text-primary uppercase tracking-widest flex items-center gap-2">
                        <Flag className="h-3.5 w-3.5" /> Gestiones Técnicas
                      </label>
                      <Button type="button" variant="ghost" size="sm" onClick={addGestionRow} className="h-7 px-3 text-[10px] font-bold uppercase text-primary hover:bg-primary/10 rounded-lg">
                        <Plus className="h-3.5 w-3.5 mr-1" /> Agregar otra
                      </Button>
                    </div>

                    {newTaskGestiones.map((gestion, idx) => (
                      <div key={idx} className="grid grid-cols-[1fr_140px_120px_180px_36px] gap-3 items-end p-3 bg-muted/30 rounded-xl border border-border/40">
                        <div className="space-y-1">
                          <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider">Actividad Técnica</label>
                          <Input 
                            value={gestion.title} 
                            onChange={(e) => updateGestionRow(idx, 'title', e.target.value)} 
                            placeholder="Nombre de la gestión..." 
                            className="h-9 bg-background border-border/50 rounded-lg text-sm" 
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider">Término</label>
                          <Input 
                            type="date" 
                            value={gestion.due_date} 
                            onChange={(e) => updateGestionRow(idx, 'due_date', e.target.value)} 
                            className="h-9 bg-background border-border/50 rounded-lg text-sm" 
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider">Prioridad</label>
                          <Select value={gestion.priority} onValueChange={(v) => updateGestionRow(idx, 'priority', v)}>
                            <SelectTrigger className="h-9 bg-background border-border/50 rounded-lg text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="low">Baja</SelectItem>
                              <SelectItem value="normal">Normal</SelectItem>
                              <SelectItem value="high">Alta</SelectItem>
                              <SelectItem value="urgent">Urgente</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider">Abogado</label>
                          <Select value={gestion.assignee_id?.toString() || ''} onValueChange={(v) => updateGestionRow(idx, 'assignee_id', v ? parseInt(v) : undefined)}>
                            <SelectTrigger className="h-9 bg-background border-border/50 rounded-lg text-sm">
                              <SelectValue placeholder="Asignar..." />
                            </SelectTrigger>
                            <SelectContent>
                              {systemUsers.map(u => <SelectItem key={u.id} value={u.id.toString()}>{u.nombre || u.username}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          {newTaskGestiones.length > 1 && (
                            <Button type="button" variant="ghost" size="icon" onClick={() => removeGestionRow(idx)} className="h-9 w-9 text-muted-foreground hover:text-red-500 rounded-lg">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Botones de acción */}
                  <div className="flex items-center justify-end gap-3 pt-2">
                    <Button variant="ghost" onClick={() => setShowCreateTaskForm(false)} className="h-10 px-5 rounded-xl text-sm font-semibold text-muted-foreground hover:text-foreground">
                      Descartar
                    </Button>
                    <Button onClick={handleCreateTaskWithGestiones} className="h-10 px-8 rounded-xl bg-primary text-primary-foreground font-bold text-sm shadow-lg shadow-primary/20 hover:bg-primary/90 transition-all">
                      <CheckCircle2 className="h-4 w-4 mr-2" />
                      Crear Tarea y Gestiones
                    </Button>
                  </div>
                </div>
              )}

              {isLoadingTasks ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : tasks.length === 0 && !showCreateTaskForm ? (
                <div className="text-center py-12 border-2 border-dashed rounded-xl bg-muted/10">
                  <CheckCircle2 className="h-12 w-12 mx-auto text-muted-foreground opacity-20 mb-4" />
                  <p className="text-muted-foreground font-medium">No hay tareas de gestión vinculadas.</p>
                  <Button variant="outline" className="mt-4 rounded-full" onClick={handleCreateTask}>
                    <Plus className="h-4 w-4 mr-2" />
                    Crear primera tarea
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {(() => {
                    const parents = tasks.filter(t => !t.parent_id);
                    const subs = tasks.reduce((acc, t) => {
                      if (t.parent_id) {
                        if (!acc[t.parent_id]) acc[t.parent_id] = [];
                        acc[t.parent_id].push(t);
                      }
                      return acc;
                    }, {} as Record<number, TaskType[]>);

                    return parents.map(task => (
                      <div key={task.id} className="space-y-2">
                        <TaskItem task={task} onSelect={setSelectedTask} />
                        {subs[task.id] && (
                          <div className="ml-10 space-y-2 border-l-2 border-dashed border-primary/20 pl-4 py-1">
                            {subs[task.id].map(sub => (
                              <TaskItem key={sub.id} task={sub} onSelect={setSelectedTask} isSubtask />
                            ))}
                          </div>
                        )}
                      </div>
                    ));
                  })()}
                </div>
              )}
            </CardContent>
          </Card>
          
          <TaskDrawer 
            task={selectedTask} 
            open={!!selectedTask} 
            onOpenChange={(open) => !open && setSelectedTask(null)}
            onTaskUpdate={(updated) => {
              setTasks(prev => prev.map(t => t.id === updated.id ? updated : t));
              setSelectedTask(updated); // refrescar drawer data en vivo
            }}
            onTaskDelete={(taskId) => {
              setTasks(prev => prev.filter(t => t.id !== taskId && t.parent_id !== taskId));
              setSelectedTask(null);
            }}
            clickupToken={clickupToken || undefined}
            allAssignees={Array.from(new Set([...tasks.map(t => t.assignee_name), ...systemUsers.map(u => u.nombre || u.username)].filter(Boolean))) as string[]}
            allStatuses={Array.from(new Set(tasks.map(t => t.status).filter(Boolean))) as string[]}
          />
        </TabsContent>

        <TabsContent value="multifuente">
          <Card className="border-primary/20 shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-3 flex-wrap gap-4">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Database className="h-5 w-5 text-primary animate-pulse" />
                  Fuentes Consultadas
                </CardTitle>
                <CardDescription>
                  Búsqueda y diagnóstico de radicados en portales judiciales alternos (Fase 1)
                </CardDescription>
              </div>
              <Button
                onClick={handleTriggerMultisourceCheck}
                disabled={isCheckingMultisource || isLoadingMultisource}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow-lg shadow-emerald-500/20 transition-all duration-200"
              >
                {isCheckingMultisource ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Consultando Fuentes...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Buscar en otras fuentes
                  </>
                )}
              </Button>
            </CardHeader>
            <CardContent className="space-y-6">
              
              {/* Resumen explicativo Fase 1 */}
              <div className="bg-primary/5 border border-primary/10 rounded-xl p-4 flex gap-3 text-sm text-primary/80">
                <AlertCircle className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-sm">Módulo de Diagnóstico Multifuente (Fase 1)</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Esta fase valida la existencia del radicado en portales externos en modo consulta segura. 
                    No modifica, reemplaza ni elimina actuaciones, publicaciones o datos del caso actual.
                  </p>
                </div>
              </div>

              {/* Grid de Fuentes */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  {
                    key: 'PUBLICACIONES_PROCESALES',
                    name: 'Publicaciones Procesales',
                    desc: 'Estados electrónicos, traslados y edictos oficiales de despachos judiciales en Colombia.',
                    url: 'https://publicacionesprocesales.ramajudicial.gov.co/'
                  },
                  {
                    key: 'SIUGJ',
                    name: 'SIUGJ (Rama Judicial)',
                    desc: 'Sistema de Información Unificado de Gestión Judicial para juzgados electrónicos incorporados.',
                    url: 'https://siugj.ramajudicial.gov.co/'
                  },
                  {
                    key: 'TYBA',
                    name: 'TYBA / Justicia XXI Web',
                    desc: 'Consulta nacional de procesos unificados e historial de actuaciones de la Rama Judicial.',
                    url: 'https://procesojudicial.ramajudicial.gov.co/Justicia21/'
                  },
                  {
                    key: 'SAMAI',
                    name: 'SAMAI (Consejo de Estado)',
                    desc: 'Portal de consulta de procesos y jurisprudencia del Consejo de Estado y tribunales administrativos.',
                    url: 'https://samai.consejodeestado.gov.co/'
                  }
                ].map((src) => {
                  const badge = getSourceStatus(src.key);
                  const lastCheck = badge.details?.checked_at ? new Date(badge.details.checked_at).toLocaleString('es-CO') : null;
                  
                  return (
                    <div 
                      key={src.key}
                      className="group relative flex flex-col justify-between p-4 rounded-xl border border-border bg-card hover:bg-muted/10 hover:border-primary/20 transition-all duration-200 shadow-sm animate-in fade-in-50 duration-200"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <h4 className="font-bold text-sm text-foreground group-hover:text-primary transition-colors">
                            {src.name}
                          </h4>
                          <span className={`text-[10px] uppercase font-extrabold px-2 py-0.5 rounded-full border ${badge.color}`}>
                            {badge.label}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2 mb-4">
                          {src.desc}
                        </p>
                      </div>
                      
                      <div className="space-y-2 pt-2 border-t border-border/50 text-[11px]">
                        <div className="flex justify-between items-center text-muted-foreground">
                          <span>Portal oficial:</span>
                          <a 
                            href={src.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-primary hover:underline flex items-center gap-1 font-semibold"
                          >
                            Visitar Sitio
                            <ChevronRight className="h-3 w-3" />
                          </a>
                        </div>
                        {lastCheck && (
                          <div className="flex justify-between text-muted-foreground">
                            <span>Último chequeo:</span>
                            <span className="font-mono text-[10px] text-foreground">{lastCheck}</span>
                          </div>
                        )}
                        {badge.details && badge.details.records_found !== undefined && badge.details.status === 'success' && (
                          <div className="flex justify-between text-muted-foreground">
                            <span>Registros hallados:</span>
                            <span className="font-semibold text-emerald-600">{badge.details.records_found}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Detalle Técnico de Consultas para SuperAdmin / logs generales */}
              <div className="space-y-4 pt-4 border-t border-border">
                <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Historial de Verificaciones
                </h3>

                {isLoadingMultisource ? (
                  <div className="flex justify-center py-6">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  </div>
                ) : multisourceChecks.length === 0 ? (
                  <div className="text-center py-8 bg-muted/20 border border-dashed rounded-xl">
                    <Database className="h-8 w-8 mx-auto text-muted-foreground opacity-30 mb-2" />
                    <p className="text-xs text-muted-foreground">No se han registrado búsquedas multifuente para este caso.</p>
                  </div>
                ) : (
                  <div className="overflow-auto max-h-[300px] border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-muted/50">
                          <TableHead className="w-[180px]">Fuente</TableHead>
                          <TableHead className="w-[100px]">Estado</TableHead>
                          <TableHead className="w-[160px]">Fecha</TableHead>
                          {isSuperAdmin && (
                            <>
                              <TableHead className="w-[80px]">Duración</TableHead>
                              <TableHead className="w-[80px]">Registros</TableHead>
                              <TableHead>URL / Mensaje</TableHead>
                            </>
                          )}
                          {!isSuperAdmin && <TableHead>Resultado / Nota</TableHead>}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {multisourceChecks.map((log: any, i: number) => {
                          const logBadge = getSourceStatus(log.source);
                          const formattedDate = log.checked_at 
                            ? new Date(log.checked_at).toLocaleString('es-CO') 
                            : '—';
                          
                          return (
                            <TableRow key={log.id || i} className="hover:bg-muted/20">
                              <TableCell className="font-semibold text-xs text-foreground">
                                {log.source === 'PUBLICACIONES_PROCESALES' ? 'Publicaciones Procesales' : log.source}
                              </TableCell>
                              <TableCell>
                                <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded-full border ${logBadge.color}`}>
                                  {logBadge.label}
                                </span>
                              </TableCell>
                              <TableCell className="text-xs text-muted-foreground font-mono">
                                {formattedDate}
                              </TableCell>
                              
                              {/* SUPERADMIN DETAILED COLUMNS */}
                              {isSuperAdmin && (
                                <>
                                  <TableCell className="text-xs font-mono">
                                    {log.duration_ms !== undefined ? `${log.duration_ms}ms` : '—'}
                                  </TableCell>
                                  <TableCell className="text-xs text-center font-bold">
                                    {log.records_found !== undefined ? log.records_found : '—'}
                                  </TableCell>
                                  <TableCell className="text-xs">
                                    <div className="max-w-[400px] space-y-1">
                                      {log.url && (
                                        <p className="truncate text-[10px] text-primary/70 font-mono" title={log.url}>
                                          <strong>URL:</strong> {log.url}
                                        </p>
                                      )}
                                      {log.error_message && (
                                        <p className="text-red-500 font-mono text-[10px] bg-red-500/5 p-1 rounded border border-red-500/10 whitespace-pre-wrap">
                                          <strong>Error:</strong> {log.error_message}
                                        </p>
                                      )}
                                      {log.raw_summary && (
                                        <details className="mt-1">
                                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground text-[10px] select-none font-bold">
                                            Ver Raw Summary (JSON)
                                          </summary>
                                          <pre className="text-[9px] font-mono bg-muted p-2 rounded mt-1 overflow-x-auto max-h-[150px] border border-border">
                                            {typeof log.raw_summary === 'string' 
                                              ? JSON.stringify(JSON.parse(log.raw_summary), null, 2) 
                                              : JSON.stringify(log.raw_summary, null, 2)}
                                          </pre>
                                        </details>
                                      )}
                                      {!log.error_message && !log.raw_summary && (
                                        <span className="text-muted-foreground text-[11px]">Diagnóstico OK (Dry-run)</span>
                                      )}
                                    </div>
                                  </TableCell>
                                </>
                              )}

                              {/* REGULAR CLIENT COLUMNS */}
                              {!isSuperAdmin && (
                                <TableCell className="text-xs text-muted-foreground">
                                  {log.status === 'unsupported' && (
                                    <span className="text-amber-600 font-medium">
                                      Esta fuente requiere ingreso manual con captcha o autenticación externa.
                                    </span>
                                  )}
                                  {log.status === 'error' && (
                                    <span className="text-rose-500">
                                      El portal del despacho judicial presentó una falla temporal. Por favor intente más tarde.
                                    </span>
                                  )}
                                  {log.status === 'success' && (
                                    <span>
                                      {log.records_found > 0 
                                        ? `Se hallaron ${log.records_found} registros en esta fuente.` 
                                        : 'No se encontraron registros activos para este radicado.'}
                                    </span>
                                  )}
                                  {log.status === 'skipped' && (
                                    <span className="text-muted-foreground">
                                      No ejecutado. El servicio de consulta multifuente automático está deshabilitado.
                                    </span>
                                  )}
                                  {log.status === 'pending' && (
                                    <span className="text-yellow-600 animate-pulse font-medium">
                                      Procesando consulta...
                                    </span>
                                  )}
                                </TableCell>
                              )}
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* === PESTAÑA: RETIRAR / REACTIVAR RADICADO === */}
        <TabsContent value="retirar">
          <Card className="border-amber-500/30 shadow-md">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <ArrowLeft className="h-5 w-5 text-amber-500" />
                {caseData?.is_active === false ? 'Radicado Retirado de Gestión' : 'Retirar Radicado de Gestión'}
              </CardTitle>
              <CardDescription>
                {caseData?.is_active === false
                  ? 'Este radicado está actualmente retirado de la gestión activa. Puedes reactivarlo en cualquier momento.'
                  : 'Al retirar un radicado, este dejará de aparecer en la lista principal de casos activos. El historial de actuaciones, publicaciones, tareas y fuentes consultadas se conserva íntegro en esta pestaña.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">

              {/* Banner de estado */}
              {caseData?.is_active === false ? (
                <div className="flex items-start gap-4 p-5 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                  <AlertCircle className="h-6 w-6 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-bold text-amber-700 dark:text-amber-400">Este radicado está retirado de gestión activa</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      No aparece en la lista principal de casos. Todo el historial se conserva y puedes consultarlo desde esta misma pestaña.
                      Puedes reactivarlo en cualquier momento sin perder ningún dato.
                    </p>
                    <Button
                      className="mt-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow-lg shadow-emerald-500/20"
                      disabled={isRetiring}
                      onClick={async () => {
                        if (!caseData?.id) return;
                        setIsRetiring(true);
                        try {
                          await updateCaseActiveStatus(caseData.id, true);
                          setCaseData(prev => prev ? { ...prev, is_active: true } : prev);
                          toast({ title: 'Radicado reactivado', description: 'El radicado vuelve a aparecer en la gestión activa.' });
                        } catch (e: any) {
                          toast({ title: 'Error al reactivar', description: e?.message || 'Ocurrió un error', variant: 'destructive' });
                        } finally {
                          setIsRetiring(false);
                        }
                      }}
                    >
                      {isRetiring ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
                      Reactivar Radicado
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-5">
                  {/* Aviso informativo */}
                  <div className="flex items-start gap-4 p-5 bg-amber-500/5 border border-amber-500/20 rounded-xl">
                    <AlertCircle className="h-6 w-6 text-amber-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-amber-700 dark:text-amber-400">Antes de continuar</p>
                      <ul className="mt-2 space-y-1 text-sm text-muted-foreground list-disc list-inside">
                        <li>El radicado <span className="font-mono font-bold text-foreground">{caseData?.radicado}</span> dejará de aparecer en la lista principal de casos activos.</li>
                        <li>Toda la información (actuaciones, publicaciones, tareas y fuentes) se conserva sin cambios.</li>
                        <li>Podrás reactivarlo en cualquier momento desde esta misma pestaña.</li>
                        <li>El historial <strong>no puede eliminarse</strong> a través de esta opción.</li>
                      </ul>
                    </div>
                  </div>

                  {/* Campo de motivo (opcional) */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Motivo del retiro (opcional)</label>
                    <Input
                      id="retiro-motivo"
                      placeholder="Ej: Proceso terminado, Caso archivado, Error de radicación..."
                      value={retiroMotivo}
                      onChange={e => setRetiroMotivo(e.target.value)}
                      className="rounded-xl"
                    />
                  </div>

                  {/* Botón de retiro */}
                  <div className="flex justify-end pt-2">
                    <Button
                      variant="outline"
                      className="border-amber-500/50 text-amber-600 hover:bg-amber-500/10 hover:border-amber-500 font-bold rounded-xl px-8"
                      disabled={isRetiring}
                      onClick={async () => {
                        if (!caseData?.id) return;
                        setIsRetiring(true);
                        try {
                          await updateCaseActiveStatus(caseData.id, false, retiroMotivo || undefined);
                          setCaseData(prev => prev ? { ...prev, is_active: false } : prev);
                          toast({ title: 'Radicado retirado', description: 'Ya no aparece en la lista de gestión activa. El historial se conserva en esta pestaña.' });
                          setRetiroMotivo('');
                        } catch (e: any) {
                          toast({ title: 'Error al retirar', description: e?.message || 'Ocurrió un error', variant: 'destructive' });
                        } finally {
                          setIsRetiring(false);
                        }
                      }}
                    >
                      {isRetiring ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <ArrowLeft className="h-4 w-4 mr-2" />}
                      Confirmar Retiro de Gestión
                    </Button>
                  </div>
                </div>
              )}

            </CardContent>
          </Card>
        </TabsContent>

      </Tabs>

      {/* Línea de tiempo */}
      {filteredEvents.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="h-5 w-5 text-primary" />
              Últimas Actuaciones
            </CardTitle>
            <CardDescription>Las 5 actuaciones más recientes</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {filteredEvents.slice(0, 5).map((event, i) => (
                <div
                  key={i}
                  className="flex gap-4 p-3 rounded-lg bg-muted/30 border border-border/50"
                >
                  <div className="flex-shrink-0 w-2 h-2 mt-2 rounded-full bg-primary" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        {formatDate(event.event_date)}
                      </div>
                      {event.con_documentos && (
                        <span className="inline-flex items-center gap-1 text-xs text-blue-500">
                          <Paperclip className="h-3 w-3" />
                          Docs
                        </span>
                      )}
                    </div>
                    <h4 className="font-medium text-sm">{event.title || 'Sin título'}</h4>
                    {event.detail && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{event.detail}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

    </div>
  );
}

function TaskItem({ task, onSelect, isSubtask }: { task: TaskType; onSelect: (t: TaskType) => void; isSubtask?: boolean }) {
  const { toast } = useToast();
  
  return (
    <div 
      onClick={() => onSelect(task)}
      className={`group relative flex items-center justify-between transition-all duration-200 cursor-pointer border rounded-xl overflow-hidden shadow-sm hover:shadow-md ${
        isSubtask 
          ? 'p-2 bg-background/50 hover:bg-background border-dashed ml-2' 
          : 'p-4 bg-card hover:bg-muted/30 border-border/60'
      }`}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${
        task.status === 'complete' ? 'bg-green-500' : 
        task.priority === 'urgent' ? 'bg-red-500' : 
        'bg-primary'
      }`} />

      <div className="flex items-center gap-4 min-w-0">
        <div className={`flex-shrink-0 ${isSubtask ? 'h-6 w-6' : 'h-8 w-8'} flex items-center justify-center rounded-full bg-muted/50 text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary transition-colors`}>
          <CheckCircle2 className={`${isSubtask ? 'h-3 w-3' : 'h-4 w-4'}`} />
        </div>
        <div className="flex flex-col min-w-0">
          <h4 className={`font-semibold ${isSubtask ? 'text-xs' : 'text-sm'} truncate max-w-[300px]`}>
            {task.title || 'Sin título'}
          </h4>
          <div className="flex items-center gap-3 mt-0.5">
            <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded-md ${
              task.status === 'complete' ? 'bg-green-500/10 text-green-600' : 'bg-primary/10 text-primary'
            }`}>
              {task.status}
            </span>
            {task.due_date && (
              <span className="flex items-center gap-1 text-[10px] text-muted-foreground font-medium">
                <Calendar className="h-3 w-3" />
                {new Date(task.due_date).toLocaleDateString('es-CO', {day: 'numeric', month: 'short'})}
              </span>
            )}
            {task.assignee_name && (
              <span className="flex items-center gap-1 text-[10px] text-muted-foreground font-medium">
                <UserIcon className="h-3 w-3" />
                {task.assignee_name}
              </span>
            )}
            <span className="flex items-center gap-1 text-[10px] text-muted-foreground font-medium">
              <Clock className="h-3 w-3" />
              {task.priority || 'Normal'}
            </span>
            {task.tags && task.tags.length > 0 && (
              <div className="flex gap-1 ml-1">
                {task.tags.map(tag => (
                  <div 
                    key={tag.id} 
                    className="h-1 w-3 rounded-full" 
                    style={{ backgroundColor: tag.color || '#3b82f6' }}
                    title={tag.name}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 pr-2">
        <ChevronRight className="h-4 w-4 text-muted-foreground/40 group-hover:text-primary transition-colors" />
      </div>
    </div>
  );
}



