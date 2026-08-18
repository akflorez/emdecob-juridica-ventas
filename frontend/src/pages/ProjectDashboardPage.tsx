import { useState, useEffect, useMemo } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { 
  LayoutDashboard, FolderPlus, ListPlus, Plus, RefreshCw, Search, 
  Filter, MoreVertical, ChevronRight, MessageSquare, 
  Calendar as CalendarIcon, User as UserIcon, CheckCircle2, Clock, Check,
  LayoutGrid, CalendarDays, List as ListIcon, Zap, PlayCircle, Lock,
  ChevronDown, Calendar, PieChart as PieIcon, BarChart as BarIcon, 
  TrendingUp, Users, Activity, Flag, Settings, Layers, Users2, Database,
  PanelLeftClose, PanelLeftOpen, AlertTriangle, CalendarRange, ArrowLeft,
  ChevronLeft, Trash2, Edit3, Tag
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { 
  getWorkspaces, getTasks, importClickUp, updateTask, getUsers,
  createWorkspace, createFolder, createList, addWorkspaceMember, createTask,
  deleteWorkspace, deleteFolder, deleteList, updateWorkspace, updateFolder, updateList, createTag, getTags, updateTag, deleteTag, createQuickUser, updateQuickUser,
  getNotificationConfig, updateNotificationConfig,
  type Workspace, type Task as TaskType, type User, type NotificationConfigResponse, type Tag
} from "@/services/api";

import { TaskDrawer } from "@/components/TaskDrawer";
import { ManageTags } from "@/components/ManageTags";
import { Calendar as BigCalendar, momentLocalizer, Views } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { format, subDays, startOfMonth, endOfMonth, isToday, isYesterday, isWithinInterval, startOfDay, endOfDay, addDays, startOfYear, endOfYear, differenceInDays } from 'date-fns';
import { es } from 'date-fns/locale';
import { 
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip as ChartTooltip, 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend 
} from 'recharts';
import { motion, AnimatePresence } from "framer-motion";

// Español para el calendario
moment.locale('es');
const localizer = momentLocalizer(moment);

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1'];

export default function ProjectDashboardPage() {
  const { user } = useAuth();
  const [isSyncing, setIsSyncing] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [tasks, setTasks] = useState<TaskType[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("board");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // Drill-down dashboard
  const [detailView, setDetailView] = useState<string | null>(null);
  
  // Creation Modals
  const [creationModal, setCreationModal] = useState<{ open: boolean, mode: string, title: string }>({ open: false, mode: '', title: '' });
  const [newItemName, setNewItemName] = useState('');
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([]);
  const [configData, setConfigData] = useState<any>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Calendario state
  const [calendarDate, setCalendarDate] = useState(new Date());
  const [calendarView, setCalendarView] = useState<any>(Views.MONTH);
  
  // Filtros de navegación
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [selectedListId, setSelectedListId] = useState<number | null>(null);
  
  const [expandedWorkspaces, setExpandedWorkspaces] = useState<Set<number>>(new Set());
  const [expandedFolders, setExpandedFolders] = useState<Set<number>>(new Set());
  
  const [selectedTask, setSelectedTask] = useState<TaskType | null>(null);
  
  // Filtros de búsqueda/fecha
  const [searchTerm, setSearchTerm] = useState("");
  const [dateFilterType, setDateFilterType] = useState<string>("all");
  const [dateRange, setDateRange] = useState({ start: "", end: "" });
  const [responsibleFilter, setResponsibleFilter] = useState<string>("all");
  const [newDueDate, setNewDueDate] = useState("");
  const [clickupToken, setClickupToken] = useState<string>(localStorage.getItem('clickup_token') || '');
  const [editingWorkspaceId, setEditingWorkspaceId] = useState<number | null>(null);
  const [editWorkspaceName, setEditWorkspaceName] = useState("");
  const [editingFolderId, setEditingFolderId] = useState<number | null>(null);
  const [editFolderName, setEditFolderName] = useState("");
  const [editingListId, setEditingListId] = useState<number | null>(null);
  const [editListName, setEditListName] = useState("");
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [editUserName, setEditUserName] = useState("");


  useEffect(() => {
    console.log("🚀 Judicial Dashboard Expert Engine v2.3 Loaded");
    fetchInitialData();
    getUsers().then(setUsers).catch(console.error);
  }, []);

  const fetchInitialData = async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const [wsData, taskData] = await Promise.all([
        getWorkspaces(),
        getTasks({})
      ]);
      const uniqueWS = Array.from(new Map(wsData.map(ws => [ws.id, ws])).values());
      setWorkspaces(uniqueWS);
      setTasks(Array.isArray(taskData) ? taskData : []);
    } catch (error) {
      toast.error("Error al cargar proyectos");
    } finally {
      if (!silent) setIsLoading(false);
    }
  };

  const fetchTasks = async () => {
    try {
      const taskData = await getTasks({});
      setTasks(Array.isArray(taskData) ? taskData : []);
    } catch (error) {
      toast.error("Error al cargar tareas");
      setTasks([]);
    }
  };

  const handleSync = async () => {
    const token = prompt("Ingresa tu ClickUp API Token:", clickupToken);
    if (!token) return;
    setClickupToken(token);
    localStorage.setItem('clickup_token', token);
    setIsSyncing(true);
    try {
      const res = await importClickUp(token);
      toast.success("Sincronización iniciada", { description: res.message });
      setTimeout(fetchInitialData, 5000);
    } catch (error: any) {
      toast.error("Error en sincronización", { description: error.message });
    } finally {
      setIsSyncing(false);
    }
  };

  const handleDateFilterChange = (val: string) => {
    setDateFilterType(val);
    const today = new Date();
    let start = "";
    let end = "";

    switch(val) {
      case 'today': start = end = format(today, 'yyyy-MM-dd'); break;
      case 'yesterday': start = end = format(subDays(today, 1), 'yyyy-MM-dd'); break;
      case '7d': start = format(subDays(today, 7), 'yyyy-MM-dd'); end = format(today, 'yyyy-MM-dd'); break;
      case '30d': start = format(subDays(today, 30), 'yyyy-MM-dd'); end = format(today, 'yyyy-MM-dd'); break;
      case 'month': start = format(startOfMonth(today), 'yyyy-MM-dd'); end = format(endOfMonth(today), 'yyyy-MM-dd'); break;
      case 'year': start = format(startOfYear(today), 'yyyy-MM-dd'); end = format(endOfYear(today), 'yyyy-MM-dd'); break;
      case 'last_year': start = format(startOfYear(subDays(startOfYear(today), 1)), 'yyyy-MM-dd'); end = format(endOfYear(subDays(startOfYear(today), 1)), 'yyyy-MM-dd'); break;
      case 'all': start = ""; end = ""; break;
    }
    setDateRange({ start, end });
  };

  const baseFilteredTasks = useMemo(() => {
    return (tasks || []).filter(t => {
      if (selectedListId && t.list_id !== selectedListId) return false;
      
      if (selectedFolderId && !selectedListId) {
        const folder = workspaces.flatMap(ws => ws.folders).find(f => f.id === selectedFolderId);
        const listIds = folder?.lists.map(l => l.id) || [];
        if (!listIds.includes(t.list_id)) return false;
      }

      if (selectedWorkspaceId && !selectedFolderId && !selectedListId) {
        const ws = workspaces.find(w => w.id === selectedWorkspaceId);
        const listIds = [
          ...(ws?.lists?.map(l => l.id) || []),
          ...(ws?.folders?.flatMap(f => f.lists.map(l => l.id)) || [])
        ];
        if (!listIds.includes(t.list_id)) return false;
      }

      if (searchTerm) {
        const search = searchTerm.toLowerCase();
        if (!t.title.toLowerCase().includes(search) && !t.description?.toLowerCase().includes(search)) return false;
      }
      
      if (responsibleFilter !== "all") {
        const matchesName = t.assignee_name?.includes(responsibleFilter);
        const matchesList = t.assignees?.some(a => (a.nombre || a.username) === responsibleFilter);
        if (!matchesName && !matchesList) return false;
      }

      return true;
    });
  }, [tasks, selectedListId, selectedFolderId, selectedWorkspaceId, workspaces, searchTerm, responsibleFilter]);

  const filteredTasks = useMemo(() => {
    return baseFilteredTasks.filter(t => {
      if (dateFilterType !== "all" && dateFilterType !== "histórico" && t.due_date) {
        const d = new Date(t.due_date);
        if (dateRange.start && d < startOfDay(new Date(dateRange.start))) return false;
        if (dateRange.end && d > endOfDay(new Date(dateRange.end))) return false;
      } else if (dateFilterType !== "all" && dateFilterType !== "histórico" && !t.due_date) {
        return false;
      }
      return true;
    });
  }, [baseFilteredTasks, dateRange, dateFilterType]);

  const dynamicBoardColumns = useMemo(() => {
    const allStatuses = Array.from(new Set(tasks.map(t => (t.status || 'ABIERTO').toUpperCase())));
    
    allStatuses.sort((a, b) => {
      const aLower = (a || '').toLowerCase();
      const bLower = (b || '').toLowerCase();
      if (aLower.includes('abierto') || aLower.includes('to do') || aLower.includes('open')) return -1;
      if (aLower.includes('completado') || aLower.includes('complete') || aLower.includes('closed')) return 1;
      return 0;
    });

    return allStatuses.map((s, idx) => {
      const sLower = (s || '').toLowerCase();
      let dotColor = COLORS[idx % COLORS.length];
      if (sLower.includes('abierto') || sLower.includes('todo')) dotColor = '#94a3b8';
      if (sLower.includes('proceso') || sLower.includes('curso')) dotColor = '#3b82f6';
      if (sLower.includes('presentar')) dotColor = '#8b5cf6';
      if (sLower.includes('retiro')) dotColor = '#ef4444';
      if (sLower.includes('completado') || sLower.includes('finalizado')) dotColor = '#10b981';

      return {
        id: s,
        label: (s || 'SIN ESTADO').toUpperCase(),
        dot: dotColor
      };
    });
  }, [tasks]);

  const parentTasks = useMemo(() => {
    return filteredTasks.filter(t => !t.parent_id);
  }, [filteredTasks]);

  const tasksByColumn = useMemo(() => {
    const grouped: Record<string, { parentTasks: TaskType[], count: number }> = {};
    
    dynamicBoardColumns.forEach(col => {
      grouped[col.id] = { parentTasks: [], count: 0 };
    });
    
    (filteredTasks || []).forEach(t => {
      const status = (t.status || 'ABIERTO').toUpperCase();
      if (!grouped[status]) {
        grouped[status] = { parentTasks: [], count: 0 };
      }
      grouped[status].count++;
      if (!t.parent_id) {
        grouped[status].parentTasks.push(t);
      }
    });
    
    return grouped;
  }, [filteredTasks, dynamicBoardColumns]);

  const dynamicTagColumns = useMemo(() => {
    const allTags = new Map<number, Tag>();
    tasks.forEach(t => {
      t.tags?.forEach(tag => allTags.set(tag.id, tag));
    });
    const columns = Array.from(allTags.values()).map(tag => ({
      id: tag.id.toString(),
      label: tag.name,
      dot: tag.color || '#3b82f6'
    }));
    columns.push({ id: 'untagged', label: 'SIN ETIQUETA', dot: '#94a3b8' });
    return columns;
  }, [tasks]);

  const tasksByTag = useMemo(() => {
    const grouped: Record<string, { parentTasks: TaskType[], count: number }> = {};
    dynamicTagColumns.forEach(col => grouped[col.id] = { parentTasks: [], count: 0 });
    
    (filteredTasks || []).forEach(t => {
      const hasTags = t.tags && t.tags.length > 0;
      if (!hasTags) {
        if (grouped['untagged']) {
          grouped['untagged'].count++;
          if (!t.parent_id) grouped['untagged'].parentTasks.push(t);
        }
      } else {
        t.tags?.forEach(tag => {
          const tid = tag.id.toString();
          if (grouped[tid]) {
            grouped[tid].count++;
            if (!t.parent_id) grouped[tid].parentTasks.push(t);
          }
        });
      }
    });
    return grouped;
  }, [filteredTasks, dynamicTagColumns]);

  const statsByAssignee = useMemo(() => {
    const map: Record<string, number> = {};
    filteredTasks.forEach(t => {
      if (t.assignees && t.assignees.length > 0) {
        t.assignees.forEach(a => {
          const name = a.nombre || a.username;
          map[name] = (map[name] || 0) + 1;
        });
      } else {
        const name = t.assignee_name || "Sin Asignar";
        map[name] = (map[name] || 0) + 1;
      }
    });
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [filteredTasks]);

  const statsByStatus = useMemo(() => {
    return dynamicBoardColumns.map(col => ({
      name: col.label,
      value: tasksByColumn[col.id]?.count || 0,
      color: col.dot
    }));
  }, [tasksByColumn, dynamicBoardColumns]);

  const calendarEvents = useMemo(() => {
    return baseFilteredTasks
      .filter(t => t.due_date && !isNaN(new Date(t.due_date).getTime()))
      .map(t => ({
        id: t.id,
        title: (t.title || 'Sin Título') + ((t.status || '').toLowerCase().includes('completado') ? ' ✅' : ''),
        start: new Date(t.due_date!),
        end: new Date(t.due_date!),
        resource: t,
      }));
  }, [baseFilteredTasks]);

  const dashboardMetrics = useMemo(() => {
    const now = new Date();
    return {
      sinAsignar: filteredTasks.filter(t => (!t.assignee_id && !t.assignee_name) || t.assignee_name === "Sin Asignar").length,
      enCurso: filteredTasks.filter(t => (t.status || '').toLowerCase().includes('proceso') || (t.status || '').toLowerCase().includes('curso')).length,
      completadas: filteredTasks.filter(t => (t.status || '').toLowerCase().includes('completado') || (t.status || '').toLowerCase().includes('closed')).length,
      vencidas: filteredTasks.filter(t => t.due_date && new Date(t.due_date) < now && !t.status.toLowerCase().includes('completado')).length,
      porVencer: filteredTasks.filter(t => t.due_date && isWithinInterval(new Date(t.due_date), { start: now, end: addDays(now, 7) }) && !t.status.toLowerCase().includes('completado')).length
    };
  }, [filteredTasks]);

  const detailTasks = useMemo(() => {
    const now = new Date();
    if (detailView === 'vencidas') return filteredTasks.filter(t => t.due_date && new Date(t.due_date) < now && !t.status.toLowerCase().includes('completado'));
    if (detailView === 'porVencer') return filteredTasks.filter(t => t.due_date && isWithinInterval(new Date(t.due_date), { start: now, end: addDays(now, 7) }) && !t.status.toLowerCase().includes('completado'));
    if (detailView === 'enCurso') return filteredTasks.filter(t => (t.status || '').toLowerCase().includes('proceso') || (t.status || '').toLowerCase().includes('curso'));
    if (detailView === 'sinAsignar') return filteredTasks.filter(t => (!t.assignee_id && !t.assignee_name) || t.assignee_name === "Sin Asignar");
    return [];
  }, [filteredTasks, detailView]);

  const handleActionClick = (mode: string, title: string) => {
    setCreationModal({ open: true, mode, title });
    setNewItemName('');
    setSelectedUserId(null);
    setSelectedUserIds([]);
  };

  const handleCreateConfirm = async () => {
    const isNameRequired = creationModal.mode !== 'equipo' && creationModal.mode !== 'pref';
    if ((isNameRequired && !newItemName.trim()) || isSubmitting) return;
    setIsSubmitting(true);
    try {
      if (creationModal.mode === 'espacio') {
        const ws = await createWorkspace({ name: newItemName });
        if (ws && ws.id) {
          const newWS = {
            id: ws.id,
            name: ws.name,
            visibility: ws.visibility || 'TEAM_COLLABORATION',
            folders: [],
            lists: []
          };
          setWorkspaces(prev => {
            const unique = prev.filter(item => item.id !== ws.id);
            return [...unique, newWS];
          });
          const expanded = new Set(expandedWorkspaces);
          expanded.add(ws.id);
          setExpandedWorkspaces(expanded);
          setSelectedWorkspaceId(ws.id);
          setSelectedFolderId(null);
          setSelectedListId(null);
        }
      } else if (creationModal.mode === 'equipo' && selectedWorkspaceId) {
        const uids = selectedUserIds.length > 0 ? selectedUserIds : (selectedUserId ? [selectedUserId] : []);
        if (uids.length === 0) {
          toast.error("Seleccione al menos un miembro del equipo");
          setIsSubmitting(false);
          return;
        }
        for (const uid of uids) {
          await addWorkspaceMember(selectedWorkspaceId, uid);
        }
      } else if (creationModal.mode === 'pref' && configData) {
        await updateNotificationConfig(configData);
      } else if (creationModal.mode === 'etiqueta' || creationModal.mode === 'estado') {
        if (!newItemName.trim()) {
           toast.error(`El nombre d${creationModal.mode === 'estado' ? 'el estado' : 'e la etiqueta'} es requerido`);
           setIsSubmitting(false);
           return;
        }
        await createTag(newItemName.trim());
      } else if (creationModal.mode === 'carpeta' && selectedWorkspaceId) {
        const f = await createFolder({ name: newItemName, workspace_id: selectedWorkspaceId });
        if (f && f.id) {
          const newFolder = { id: f.id, name: f.name, lists: [] };
          setWorkspaces(prev => prev.map(ws => {
            if (ws.id === selectedWorkspaceId) {
              const folders = ws.folders || [];
              const uniqueFolders = folders.filter(item => item.id !== f.id);
              return {
                ...ws,
                folders: [...uniqueFolders, newFolder]
              };
            }
            return ws;
          }));
          const wsExpanded = new Set(expandedWorkspaces);
          wsExpanded.add(selectedWorkspaceId);
          setExpandedWorkspaces(wsExpanded);

          const fExpanded = new Set(expandedFolders);
          fExpanded.add(f.id);
          setExpandedFolders(fExpanded);

          setSelectedFolderId(f.id);
          setSelectedListId(null);
        }
      } else if (creationModal.mode === 'lista' && (selectedFolderId || selectedWorkspaceId)) {
        const l = await createList({ name: newItemName, workspace_id: selectedWorkspaceId!, folder_id: selectedFolderId || undefined });
        if (l && l.id) {
          const newList = { id: l.id, name: l.name };
          setWorkspaces(prev => prev.map(ws => {
            if (ws.id === selectedWorkspaceId) {
              if (selectedFolderId) {
                return {
                  ...ws,
                  folders: (ws.folders || []).map(folder => {
                    if (folder.id === selectedFolderId) {
                      const lists = folder.lists || [];
                      const uniqueLists = lists.filter(item => item.id !== l.id);
                      return {
                        ...folder,
                        lists: [...uniqueLists, newList]
                      };
                    }
                    return folder;
                  })
                };
              } else {
                const lists = ws.lists || [];
                const uniqueLists = lists.filter(item => item.id !== l.id);
                return {
                  ...ws,
                  lists: [...uniqueLists, newList]
                };
              }
            }
            return ws;
          }));
          const wsExpanded = new Set(expandedWorkspaces);
          wsExpanded.add(selectedWorkspaceId!);
          setExpandedWorkspaces(wsExpanded);

          if (selectedFolderId) {
            const fExpanded = new Set(expandedFolders);
            fExpanded.add(selectedFolderId);
            setExpandedFolders(fExpanded);
          }

          setSelectedListId(l.id);
        }
      } else if (creationModal.mode === 'tarea' || !creationModal.mode) {
        let targetListId = selectedListId;
        if (!targetListId && selectedWorkspaceId) {
           const ws = workspaces.find(w => w.id === selectedWorkspaceId);
           if (ws) {
               for (const f of ws.folders || []) {
                   if (f.lists && f.lists.length > 0) {
                       targetListId = f.lists[0].id;
                       break;
                   }
               }
               if (!targetListId && ws.lists && ws.lists.length > 0) {
                   targetListId = ws.lists[0].id;
               }
           }
        }
        await createTask({ 
          title: newItemName, 
          list_id: targetListId || undefined,
          due_date: newDueDate || undefined,
          status: 'ABIERTO'
        });
      }
      
      const successName = creationModal.mode === 'equipo' 
        ? 'Miembros agregados' 
        : creationModal.mode === 'pref'
        ? 'Preferencias guardadas'
        : creationModal.mode === 'estado'
        ? 'Estado creado'
        : creationModal.mode === 'etiqueta'
        ? 'Etiqueta creada'
        : `${creationModal.mode.charAt(0).toUpperCase() + creationModal.mode.slice(1)} "${newItemName}" cread${creationModal.mode === 'carpeta' || creationModal.mode === 'lista' || creationModal.mode === 'tarea' ? 'a' : 'o'}`;
      toast.success(`${creationModal.title} ${successName} procesado con éxito`);
      setCreationModal({ open: false, mode: '', title: '' });
      setNewItemName('');
      setNewDueDate('');
      setSelectedUserId(null);
      setSelectedUserIds([]);
      await fetchInitialData(true);
    } catch (error: any) {
      toast.error("Error al crear el elemento", { description: error.message });
    } finally {
      setIsSubmitting(false);
    }
  };


  return (
    <div className="flex flex-col h-full bg-background text-foreground overflow-hidden relative font-sans transition-colors duration-500">
      <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[120px] pointer-events-none" />
      
      {/* Header */}
      <motion.div 
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="flex items-center justify-between py-4 px-6 border-b border-border/40 bg-background/80 backdrop-blur-xl z-20"
      >
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => setSidebarCollapsed(!sidebarCollapsed)} className="rounded-lg hover:bg-accent">
            {sidebarCollapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
          </Button>
          <div className="p-2.5 bg-gradient-to-br from-primary to-blue-600 rounded-xl shadow-xl shadow-primary/20">
            <LayoutDashboard className="h-5 w-5 text-white" />
          </div>
          <div onClick={() => { setSelectedWorkspaceId(null); setSelectedFolderId(null); setSelectedListId(null); setDetailView(null); }} className="cursor-pointer hidden sm:block">
            <h1 className="text-xl font-black tracking-tight flex items-center gap-2 uppercase">
              {user?.company_name || "EMDECOB JURÍDICO"} <Badge variant="secondary" className="bg-primary/20 text-primary border-primary/20 text-[10px]">EXPERT</Badge>
            </h1>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Master Workflow Engine</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="rounded-lg h-9 bg-accent/50 border-border/40 font-bold text-xs">
                  <Layers className="mr-2 h-3.5 w-3.5" /> Operaciones
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56 bg-background border-border shadow-2xl rounded-xl">
                <DropdownMenuLabel className="text-[10px] uppercase font-black text-muted-foreground tracking-widest">Gestión Operativa</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="cursor-pointer" onClick={() => handleActionClick('espacio', 'Nuevo Espacio')}><Plus className="mr-2 h-4 w-4" /> Nuevo Espacio</DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer" onClick={() => handleActionClick('carpeta', 'Nueva Carpeta')}><FolderPlus className="mr-2 h-4 w-4" /> Nueva Carpeta</DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer" onClick={() => handleActionClick('lista', 'Nueva Lista')}><ListPlus className="mr-2 h-4 w-4" /> Nueva Lista</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="cursor-pointer" onClick={() => handleActionClick('estado', 'Crear Estado')}><Activity className="mr-2 h-4 w-4" /> Estados</DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer" onClick={() => handleActionClick('etiqueta', 'Crear Etiqueta de Clasificación')}><Tag className="mr-2 h-4 w-4" /> Etiquetas</DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer" onClick={() => handleActionClick('equipo', 'Gestionar Equipo')}><Users2 className="mr-2 h-4 w-4" /> Equipos</DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer" onClick={() => handleActionClick('pref', 'Configuración')}><Settings className="mr-2 h-4 w-4" /> Preferencias</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {user?.sync_with_clickup && (
              <Button variant="ghost" onClick={handleSync} disabled={isSyncing} className="rounded-lg h-9 bg-accent/50 hover:bg-accent border border-border/40 text-xs px-4 font-bold">
                <RefreshCw className={`mr-2 h-3.5 w-3.5 ${isSyncing ? "animate-spin" : ""}`} /> Sincronizar
              </Button>
            )}
            
            <Button onClick={() => setSelectedTask({ title: '', status: 'ABIERTO', priority: 'normal', list_id: selectedListId } as any)} className="rounded-lg h-9 bg-primary hover:bg-primary/90 text-primary-foreground font-black text-[11px] px-6 shadow-lg shadow-primary/20 uppercase tracking-wider">
              <Plus className="mr-2 h-4 w-4" /> Nueva Tarea
            </Button>
        </div>
      </motion.div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <AnimatePresence>
          {!sidebarCollapsed && (
            <motion.div 
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 280, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              className="flex flex-col border-r border-border/40 bg-background/50 backdrop-blur-sm overflow-hidden"
            >
               <div className="p-4">
                 <div className="relative group">
                   <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                   <Input placeholder="Buscar..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="pl-9 h-9 bg-accent/30 border-border/40 rounded-lg text-xs" />
                 </div>
               </div>
               <div className="flex-1 overflow-y-auto px-2 space-y-1 custom-scrollbar">
                  {workspaces.map(ws => (
                    <div key={ws.id}>
                       <div className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all group ${selectedWorkspaceId === ws.id && !selectedFolderId ? "bg-primary/10 text-primary" : "hover:bg-accent/50"}`} onClick={() => {
                         const n = new Set(expandedWorkspaces);
                         if (n.has(ws.id)) n.delete(ws.id); else n.add(ws.id);
                         setExpandedWorkspaces(n);
                         setSelectedWorkspaceId(ws.id);
                         setSelectedFolderId(null);
                         setSelectedListId(null);
                         setDetailView(null);
                       }}>
                         <motion.div animate={{ rotate: expandedWorkspaces.has(ws.id) ? 0 : -90 }}>
                            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                         </motion.div>
                         {editingWorkspaceId === ws.id ? (
                           <Input 
                             value={editWorkspaceName}
                             onChange={(e) => setEditWorkspaceName(e.target.value)}
                             onClick={(e) => e.stopPropagation()}
                             onKeyDown={async (e) => {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    try {
                                        await updateWorkspace(ws.id, { name: editWorkspaceName });
                                        setEditingWorkspaceId(null);
                                        toast.success("Espacio actualizado");
                                        fetchInitialData(true);
                                    } catch (err: any) {
                                        toast.error("Error al actualizar", { description: err.message });
                                    }
                                } else if (e.key === 'Escape') {
                                    setEditingWorkspaceId(null);
                                }
                             }}
                             autoFocus
                             className="h-6 text-[10px] font-black uppercase flex-1 min-w-0"
                           />
                         ) : (
                           <span className="text-[10px] font-black uppercase text-muted-foreground tracking-widest flex-1 truncate">{ws.name}</span>
                         )}
                         <div className="flex items-center gap-1 transition-opacity">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingWorkspaceId(ws.id);
                                setEditWorkspaceName(ws.name);
                              }}
                              className="p-1 hover:bg-primary/20 text-muted-foreground hover:text-primary rounded transition-all duration-200"
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={async (e) => {
                                e.stopPropagation();
                                if (window.confirm(`¿Estás seguro de que deseas eliminar el espacio "${ws.name}"? Se eliminarán todas sus carpetas, listas y tareas de forma permanente.`)) {
                                  try {
                                    await deleteWorkspace(ws.id);
                                    toast.success(`Espacio "${ws.name}" eliminado con éxito`);
                                    if (selectedWorkspaceId === ws.id) {
                                      setSelectedWorkspaceId(null);
                                      setSelectedFolderId(null);
                                      setSelectedListId(null);
                                    }
                                    fetchInitialData();
                                  } catch (err: any) {
                                    toast.error("Error al eliminar espacio", { description: err.message });
                                  }
                                }
                              }}
                              className="p-1 hover:bg-destructive/20 text-muted-foreground hover:text-destructive rounded transition-all duration-200"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                         </div>
                       </div>
                       
                       <AnimatePresence>
                         {expandedWorkspaces.has(ws.id) && (
                           <motion.div 
                             initial={{ height: 0, opacity: 0 }}
                             animate={{ height: "auto", opacity: 1 }}
                             exit={{ height: 0, opacity: 0 }}
                             className="overflow-hidden"
                           >
                             {ws.folders.map(f => (
                               <div key={f.id} className="ml-3">
                                  <div className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all group ${selectedFolderId === f.id && !selectedListId ? "bg-primary/10 text-primary" : "hover:bg-accent/50"}`} onClick={() => {
                                    const n = new Set(expandedFolders);
                                    if (n.has(f.id)) n.delete(f.id); else n.add(f.id);
                                    setExpandedFolders(n);
                                    setSelectedFolderId(f.id);
                                    setSelectedListId(null);
                                    setDetailView(null);
                                  }}>
                                    <motion.div animate={{ rotate: expandedFolders.has(f.id) ? 0 : -90 }}>
                                      <ChevronDown className="h-3 w-3 text-muted-foreground" />
                                    </motion.div>
                                    {editingFolderId === f.id ? (
                                      <Input 
                                        value={editFolderName}
                                        onChange={(e) => setEditFolderName(e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                        onKeyDown={async (e) => {
                                            if (e.key === 'Enter') {
                                                e.preventDefault();
                                                try {
                                                    await updateFolder(f.id, { name: editFolderName });
                                                    setEditingFolderId(null);
                                                    toast.success("Carpeta actualizada");
                                                    fetchInitialData(true);
                                                } catch (err: any) {
                                                    toast.error("Error al actualizar", { description: err.message });
                                                }
                                            } else if (e.key === 'Escape') {
                                                setEditingFolderId(null);
                                            }
                                        }}
                                        autoFocus
                                        className="h-6 text-[11px] font-bold flex-1 min-w-0"
                                      />
                                    ) : (
                                      <span className="text-[11px] font-bold text-foreground/70 flex-1 truncate">{f.name}</span>
                                    )}
                                    {!user?.sync_with_clickup && (
                                       <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                         <button
                                           onClick={(e) => {
                                             e.stopPropagation();
                                             setEditingFolderId(f.id);
                                             setEditFolderName(f.name);
                                           }}
                                           className="p-1 hover:bg-primary/20 text-muted-foreground hover:text-primary rounded transition-all duration-200"
                                         >
                                           <Edit3 className="h-3.5 w-3.5" />
                                         </button>
                                         <button
                                           onClick={async (e) => {
                                             e.stopPropagation();
                                             if (window.confirm(`¿Estás seguro de que deseas eliminar la carpeta "${f.name}"? Se eliminarán todas sus listas y tareas de forma permanente.`)) {
                                               try {
                                                 await deleteFolder(f.id);
                                                 toast.success(`Carpeta "${f.name}" eliminada con éxito`);
                                                 if (selectedFolderId === f.id) {
                                                   setSelectedFolderId(null);
                                                   setSelectedListId(null);
                                                 }
                                                 fetchInitialData();
                                               } catch (err: any) {
                                                 toast.error("Error al eliminar carpeta", { description: err.message });
                                               }
                                             }
                                           }}
                                           className="p-1 hover:bg-destructive/20 text-muted-foreground hover:text-destructive rounded transition-all duration-200"
                                         >
                                           <Trash2 className="h-3.5 w-3.5" />
                                         </button>
                                       </div>
                                     )}
                                  </div>
                                  <AnimatePresence>
                                    {expandedFolders.has(f.id) && (
                                      <motion.div 
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: "auto", opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        className="overflow-hidden"
                                      >
                                        {f.lists.map(list => (
                                          <motion.div 
                                            key={list.id} 
                                            whileHover={{ x: 5 }}
                                            onClick={(e) => { e.stopPropagation(); setSelectedListId(list.id); setDetailView(null); }}
                                            className={`ml-5 p-2 rounded-lg cursor-pointer text-[11px] transition-all flex items-center justify-between group ${selectedListId === list.id ? "bg-primary text-primary-foreground font-bold" : "text-muted-foreground hover:text-foreground"}`}
                                          >
                                             {editingListId === list.id ? (
                                               <Input 
                                                 value={editListName}
                                                 onChange={(e) => setEditListName(e.target.value)}
                                                 onClick={(e) => e.stopPropagation()}
                                                 onKeyDown={async (e) => {
                                                     if (e.key === 'Enter') {
                                                         e.preventDefault();
                                                         try {
                                                             await updateList(list.id, { name: editListName });
                                                             setEditingListId(null);
                                                             toast.success("Lista actualizada");
                                                             fetchInitialData(true);
                                                         } catch (err: any) {
                                                             toast.error("Error al actualizar", { description: err.message });
                                                         }
                                                     } else if (e.key === 'Escape') {
                                                         setEditingListId(null);
                                                     }
                                                 }}
                                                 autoFocus
                                                 className="h-6 text-[11px] font-bold flex-1 min-w-0 text-foreground"
                                               />
                                             ) : (
                                               <span className="flex-1 truncate">{list.name}</span>
                                             )}
                                             <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {selectedListId === list.id && <Zap className="h-3 w-3 animate-pulse group-hover:hidden" />}
                                                {!user?.sync_with_clickup && (
                                                  <>
                                                    <button
                                                      onClick={(e) => {
                                                        e.stopPropagation();
                                                        setEditingListId(list.id);
                                                        setEditListName(list.name);
                                                      }}
                                                      className="p-1 hover:bg-primary/20 text-muted-foreground hover:text-primary rounded transition-all duration-200"
                                                    >
                                                      <Edit3 className="h-3 w-3" />
                                                    </button>
                                                    <button
                                                      onClick={async (e) => {
                                                        e.stopPropagation();
                                                        if (window.confirm(`¿Estás seguro de que deseas eliminar la lista "${list.name}"? Se eliminarán todas sus tareas de forma permanente.`)) {
                                                          try {
                                                            await deleteList(list.id);
                                                            toast.success(`Lista "${list.name}" eliminada con éxito`);
                                                            if (selectedListId === list.id) {
                                                              setSelectedListId(null);
                                                            }
                                                            fetchInitialData();
                                                          } catch (err: any) {
                                                            toast.error("Error al eliminar lista", { description: err.message });
                                                          }
                                                        }
                                                      }}
                                                      className="p-1 hover:bg-destructive/20 text-muted-foreground group-hover:text-destructive rounded transition-all duration-200"
                                                    >
                                                      <Trash2 className="h-3 w-3" />
                                                    </button>
                                                  </>
                                                )}
                                              </div>
                                          </motion.div>
                                        ))}
                                      </motion.div>
                                    )}
                                  </AnimatePresence>
                               </div>
                             ))}
                           </motion.div>
                         )}
                       </AnimatePresence>
                    </div>
                  ))}
               </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
           <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
              <div className="h-16 flex items-center justify-between px-6 border-b border-border/40 bg-background/50">
                 <TabsList className="bg-accent/50 p-1 rounded-xl h-10 border border-border/40">
                   <TabsTrigger value="board" className="rounded-lg text-[10px] font-black uppercase tracking-widest px-6">Tablero</TabsTrigger>
                   <TabsTrigger value="list" className="rounded-lg text-[10px] font-black uppercase tracking-widest px-6">Lista</TabsTrigger>
                   <TabsTrigger value="calendar" className="rounded-lg text-[10px] font-black uppercase tracking-widest px-6">Agenda</TabsTrigger>
                   <TabsTrigger value="stats" className="rounded-lg text-[10px] font-black uppercase tracking-widest px-6">Dashboard</TabsTrigger>
                   <TabsTrigger value="tags_board" className="rounded-lg text-[10px] font-black uppercase tracking-widest px-6 text-primary">Etiquetas</TabsTrigger>
                 </TabsList>

                 <div className="flex items-center gap-3">
                    <Select value={dateFilterType} onValueChange={handleDateFilterChange}>
                      <SelectTrigger className="w-[140px] h-9 bg-accent/30 border-border/40 rounded-xl text-[10px] font-black uppercase text-primary">
                        <CalendarRange className="h-3.5 w-3.5 mr-2" />
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="today">Hoy</SelectItem>
                        <SelectItem value="yesterday">Ayer</SelectItem>
                        <SelectItem value="7d">Últimos 7 Días</SelectItem>
                        <SelectItem value="30d">Últimos 30 Días</SelectItem>
                        <SelectItem value="month">Este Mes</SelectItem>
                        <SelectItem value="year">Este Año</SelectItem>
                        <SelectItem value="last_year">Año Pasado</SelectItem>
                        <SelectItem value="all">Histórico</SelectItem>
                      </SelectContent>
                    </Select>

                    <Select value={responsibleFilter} onValueChange={setResponsibleFilter}>
                       <SelectTrigger className="w-[160px] h-9 bg-accent/30 border-border/40 rounded-xl text-[10px] font-black uppercase text-muted-foreground">
                         <Users className="h-3.5 w-3.5 mr-2" />
                         <SelectValue placeholder="Abogado" />
                       </SelectTrigger>
                       <SelectContent>
                         <SelectItem value="all">Todos</SelectItem>
                         {Array.from(new Set(tasks.map(t => t.assignee_name).filter(Boolean))).map(name => (
                           <SelectItem key={name!} value={name!}>{name}</SelectItem>
                         ))}
                       </SelectContent>
                    </Select>
                 </div>
              </div>

              <div className="flex-1 overflow-hidden relative">
                    {activeTab === "board" && (
                      <div className="h-full p-6 flex gap-6 overflow-x-auto custom-scrollbar">
                         {dynamicBoardColumns.map((col, colIdx) => (
                           <div key={col.id} className="min-w-[320px] flex flex-col bg-accent/5 border border-border/40 rounded-3xl p-4 shadow-xl">
                             <div className="flex items-center justify-between mb-6 px-2">
                                <div className="flex items-center gap-2">
                                   <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: col.dot }} />
                                   <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-muted-foreground">{col.label}</h3>
                                </div>
                                <Badge variant="outline" className="text-[10px]">{tasksByColumn[col.id]?.count || 0}</Badge>
                             </div>
                             <div className="flex-1 overflow-y-auto space-y-4 px-1 custom-scrollbar">
                                {(tasksByColumn[col.id]?.parentTasks || []).map(task => (
                                  <Card key={task.id} className="bg-card/80 border-border/40 hover:border-primary/40 transition-all cursor-pointer shadow-lg overflow-hidden" onClick={() => setSelectedTask(task)}>
                                    <div className="p-4">
                                       <div className="flex justify-between items-start mb-3">
                                          <Badge variant="secondary" className="text-[9px] uppercase tracking-wider">{task.priority || 'Normal'}</Badge>
                                       </div>
                                       <h4 className="text-[13px] font-bold leading-snug line-clamp-2 mb-4">{task.title}</h4>
                                       <div className="flex items-center justify-between border-t border-border/40 pt-3">
                                          <div className="flex items-center">
                                             <div className="flex -space-x-2 overflow-hidden mr-2">
                                                {task.assignees?.map((a, i) => (
                                                  <div key={i} className="h-5 w-5 rounded-full ring-2 ring-card bg-primary/20 flex items-center justify-center text-[8px] font-black text-primary">{(a.nombre || a.username)[0]}</div>
                                                ))}
                                             </div>
                                             <span className="text-[9px] font-bold text-muted-foreground truncate max-w-[80px]">{task.assignee_name}</span>
                                          </div>
                                          {task.due_date && <span className={`text-[9px] font-black flex items-center gap-1 ${new Date(task.due_date) < new Date() && !task.status.toLowerCase().includes('completado') ? 'text-red-500' : 'text-muted-foreground'}`}><Clock className="h-3 w-3"/> {format(new Date(task.due_date), 'd MMM')}</span>}
                                       </div>
                                    </div>
                                  </Card>
                                ))}
                             </div>
                           </div>
                         ))}
                      </div>
                    )}
                    {activeTab === "tags_board" && (
                      <div className="h-full p-6 flex gap-6 overflow-x-auto custom-scrollbar">
                         {dynamicTagColumns.map((col, colIdx) => (
                           <div key={col.id} className="min-w-[320px] flex flex-col bg-accent/5 border border-border/40 rounded-3xl p-4 shadow-xl">
                             <div className="flex items-center justify-between mb-6 px-2">
                                <div className="flex items-center gap-2">
                                   <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: col.dot }} />
                                   <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-muted-foreground">{col.label}</h3>
                                </div>
                                <Badge variant="outline" className="text-[10px]">{tasksByTag[col.id]?.count || 0}</Badge>
                             </div>
                             <div className="flex-1 overflow-y-auto space-y-4 px-1 custom-scrollbar">
                                {(tasksByTag[col.id]?.parentTasks || []).map(task => (
                                  <Card key={task.id} className="bg-card/80 border-border/40 hover:border-primary/40 transition-all cursor-pointer shadow-lg overflow-hidden" onClick={() => setSelectedTask(task)}>
                                    <div className="p-4">
                                       <div className="flex justify-between items-start mb-3">
                                          <Badge variant="secondary" className="text-[9px] uppercase tracking-wider">{task.priority || 'Normal'}</Badge>
                                       </div>
                                       <h4 className="text-[13px] font-bold leading-snug line-clamp-2 mb-4">{task.title}</h4>
                                       <div className="flex items-center justify-between border-t border-border/40 pt-3">
                                          <div className="flex items-center">
                                             <div className="flex -space-x-2 overflow-hidden mr-2">
                                                {task.assignees?.map((a, i) => (
                                                  <div key={i} className="h-5 w-5 rounded-full ring-2 ring-card bg-primary/20 flex items-center justify-center text-[8px] font-black text-primary">{(a.nombre || a.username)[0]}</div>
                                                ))}
                                             </div>
                                             {task.assignees && task.assignees.length > 0 && <span className="text-[9px] font-black text-muted-foreground">{task.assignees[0].nombre || task.assignees[0].username}</span>}
                                          </div>
                                          <div className="flex items-center text-[9px] font-black text-muted-foreground">
                                             <Clock className="h-3 w-3 mr-1" />
                                             {task.due_date ? moment(task.due_date).format('D MMM') : 'Sin fecha'}
                                          </div>
                                       </div>
                                    </div>
                                  </Card>
                                ))}
                             </div>
                           </div>
                         ))}
                      </div>
                    )}

                    {activeTab === "list" && (
                      <div className="h-full p-6 overflow-y-auto space-y-2 custom-scrollbar">
                         {parentTasks.map(t => (
                           <div key={t.id} className="group flex items-center justify-between p-4 bg-accent/5 border border-border/40 rounded-2xl hover:bg-accent/10 transition-all cursor-pointer" onClick={() => setSelectedTask(t)}>
                              <div className="flex items-center gap-4">
                                 <div className="h-3 w-3 rounded-full border-2 border-muted-foreground/30" />
                                 <div>
                                    <div className="text-[13px] font-bold group-hover:text-primary transition-colors">{t.title}</div>
                                    <div className="text-[10px] text-muted-foreground flex items-center gap-3 mt-1">
                                       <span>{t.assignee_name || 'Sin asignar'}</span>
                                       {t.due_date && <span>{format(new Date(t.due_date), 'd MMM')}</span>}
                                    </div>
                                 </div>
                              </div>
                              <Badge variant="outline" className="text-[9px] font-black">{t.status}</Badge>
                           </div>
                         ))}
                      </div>
                    )}

                    {activeTab === "calendar" && (
                      <div className="h-full p-6 overflow-y-auto custom-scrollbar">
                         <div className="h-[650px] bg-card rounded-3xl border border-border/40 p-6 overflow-hidden shadow-2xl">
                            <BigCalendar
                              localizer={localizer}
                              events={calendarEvents}
                              selectable
                              onSelectSlot={(slotInfo: any) => {
                                setNewDueDate(format(slotInfo.start, 'yyyy-MM-dd'));
                                setCreationModal({ open: true, mode: 'tarea', title: 'Nueva Tarea' });
                              }}
                              startAccessor="start"
                              endAccessor="end"
                              date={calendarDate}
                              view={calendarView}
                              onNavigate={setCalendarDate}
                              onView={setCalendarView}
                              style={{ height: '100%' }}
                              onSelectEvent={(e: any) => setSelectedTask(e.resource)}
                              views={[Views.MONTH, Views.WEEK, Views.DAY, Views.AGENDA]}
                              messages={{ today: "Hoy", previous: "Anterior", next: "Siguiente", month: "Mes", week: "Semana", day: "Día", agenda: "Agenda" }}
                              culture="es"
                            />
                         </div>
                      </div>
                    )}

                    {activeTab === "stats" && (
                      <div className="h-full p-8 overflow-y-auto space-y-8 custom-scrollbar bg-accent/5">
                         {detailView ? (
                           <div className="space-y-6">
                              <Button variant="ghost" size="sm" onClick={() => setDetailView(null)} className="font-bold text-xs">
                                <ArrowLeft className="mr-2 h-4 w-4" /> Volver al Dashboard
                              </Button>
                              <Card className="bg-card border-border/40 shadow-2xl rounded-3xl overflow-hidden">
                                 <CardHeader className="bg-primary/5 border-b border-border/40">
                                    <CardTitle className="text-[11px] font-black uppercase tracking-[0.2em] text-primary">
                                       Detalle: {detailView === 'vencidas' ? 'Tareas Vencidas' : detailView === 'porVencer' ? 'Próximas a Vencer' : 'Tareas en Curso'}
                                    </CardTitle>
                                 </CardHeader>
                                 <Table>
                                    <TableHeader>
                                       <TableRow className="border-border/40 bg-accent/30">
                                          <TableHead className="text-[10px] uppercase font-black tracking-widest">Tarea</TableHead>
                                          <TableHead className="text-[10px] uppercase font-black tracking-widest">Responsable</TableHead>
                                          <TableHead className="text-[10px] uppercase font-black tracking-widest">Estado</TableHead>
                                          <TableHead className="text-[10px] uppercase font-black tracking-widest text-right">Vencimiento</TableHead>
                                          <TableHead className="text-[10px] uppercase font-black tracking-widest text-right">Días Retraso</TableHead>
                                       </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                       {detailTasks.map(t => {
                                          const delay = t.due_date ? differenceInDays(new Date(), new Date(t.due_date)) : 0;
                                          return (
                                             <TableRow key={t.id} className="border-border/40 hover:bg-primary/5 cursor-pointer" onClick={() => setSelectedTask(t)}>
                                                <TableCell className="font-bold text-[11px]">{t.title}</TableCell>
                                                <TableCell className="text-[11px] text-muted-foreground">{t.assignee_name || 'Sin Asignar'}</TableCell>
                                                <TableCell><Badge variant="outline" className="text-[9px] uppercase">{t.status}</Badge></TableCell>
                                                <TableCell className="text-right text-[11px]">{t.due_date ? format(new Date(t.due_date), 'dd/MM/yyyy') : '-'}</TableCell>
                                                <TableCell className="text-right font-black text-red-500 text-xs">{delay > 0 ? `+${delay}` : '-'}</TableCell>
                                             </TableRow>
                                          );
                                       })}
                                    </TableBody>
                                 </Table>
                              </Card>
                           </div>
                         ) : (
                           <>
                             <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                                {[
                                  { id: 'sinAsignar', label: 'Sin Asignar', count: dashboardMetrics.sinAsignar, icon: Users, color: 'text-slate-400', bg: 'bg-slate-400/10' },
                                  { id: 'enCurso', label: 'En Curso', count: dashboardMetrics.enCurso, icon: Activity, color: 'text-blue-500', bg: 'bg-blue-500/10' },
                                  { id: 'vencidas', label: 'Vencidas', count: dashboardMetrics.vencidas, icon: AlertTriangle, color: 'text-red-500', bg: 'bg-red-500/10' },
                                  { id: 'porVencer', label: 'Por Vencer (7d)', count: dashboardMetrics.porVencer, icon: Clock, color: 'text-orange-500', bg: 'bg-orange-500/10' },
                                  { id: 'completadas', label: 'Completadas', count: dashboardMetrics.completadas, icon: CheckCircle2, color: 'text-green-500', bg: 'bg-green-500/10' }
                                ].map((card, i) => (
                                  <Card key={i} className="bg-card border-border/40 shadow-xl overflow-hidden relative group cursor-pointer hover:border-primary/60 hover:shadow-primary/10 transition-all duration-300" onClick={() => setDetailView(card.id)}>
                                     <div className={`absolute top-0 right-0 w-24 h-24 ${card.bg} rounded-full -mr-12 -mt-12 blur-3xl group-hover:scale-150 transition-transform duration-500`} />
                                     <CardContent className="p-6">
                                        <div className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground mb-4">{card.label}</div>
                                        <div className="flex items-center justify-between">
                                           <div className={`text-4xl font-black ${card.color}`}>{card.count}</div>
                                           <card.icon className={`h-8 w-8 ${card.color} opacity-20`} />
                                        </div>
                                     </CardContent>
                                  </Card>
                                ))}
                             </div>

                             <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                <Card className="bg-card border-border/40 shadow-xl overflow-hidden flex flex-col">
                                   <CardHeader className="border-b border-border/40">
                                      <CardTitle className="text-[11px] font-black uppercase tracking-[0.2em] text-muted-foreground">Carga por Abogado</CardTitle>
                                   </CardHeader>
                                   <CardContent className="p-4 flex-1 h-[450px] min-h-[450px]">
                                      <ResponsiveContainer width="100%" height="100%">
                                         <PieChart>
                                            <Pie data={statsByAssignee} cx="50%" cy="45%" innerRadius={70} outerRadius={100} paddingAngle={2} dataKey="value" stroke="none">
                                               {statsByAssignee.map((entry, index) => (
                                                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                               ))}
                                            </Pie>
                                            <ChartTooltip contentStyle={{ background: 'var(--background)', border: '1px solid var(--border)', borderRadius: '12px', fontSize: '10px' }} />
                                            <Legend verticalAlign="bottom" align="center" wrapperStyle={{ paddingTop: '20px', fontSize: '9px', fontWeight: 'bold' }} layout="horizontal" iconType="circle" />
                                         </PieChart>
                                      </ResponsiveContainer>
                                   </CardContent>
                                </Card>

                                <Card className="bg-card border-border/40 shadow-xl overflow-hidden flex flex-col">
                                   <CardHeader className="border-b border-border/40">
                                      <CardTitle className="text-[11px] font-black uppercase tracking-[0.2em] text-muted-foreground">Distribución de Estados</CardTitle>
                                   </CardHeader>
                                   <CardContent className="p-4 flex-1 h-[450px] min-h-[450px]">
                                      <ResponsiveContainer width="100%" height="100%">
                                         <BarChart data={statsByStatus} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.1)" vertical={false} />
                                            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 8, fontWeight: 'bold' }} angle={-45} textAnchor="end" interval={0} />
                                            <YAxis axisLine={false} tickLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                                            <ChartTooltip cursor={{ fill: 'rgba(128,128,128,0.05)' }} contentStyle={{ background: 'var(--background)', border: '1px solid var(--border)', borderRadius: '12px' }} />
                                            <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={35}>
                                               {statsByStatus.map((entry, index) => (
                                                  <Cell key={`cell-${index}`} fill={entry.color} />
                                               ))}
                                            </Bar>
                                         </BarChart>
                                      </ResponsiveContainer>
                                   </CardContent>
                                </Card>
                             </div>
                           </>
                         )}
                      </div>
                    )}
              </div>
           </Tabs>
        </div>
      </div>

      <TaskDrawer 
        task={selectedTask} 
        open={!!selectedTask} 
        onOpenChange={(open) => !open && setSelectedTask(null)}
        onTaskUpdate={(t) => {
          setTasks(prev => {
            const exists = prev.some(pt => pt.id === t.id);
            if (exists) return prev.map(pt => pt.id === t.id ? t : pt);
            return [t, ...prev];
          });
        }}
        clickupToken={clickupToken}
        allAssignees={Array.from(new Set(tasks.map(t => t.assignee_name).filter(Boolean))) as string[]}
        allStatuses={dynamicBoardColumns.map(c => c.id)}
      />

      {/* Creation Modal */}
      <Dialog open={creationModal.open} onOpenChange={(o) => !o && setCreationModal({ ...creationModal, open: false })}>
        <DialogContent className="bg-card border-border/40 rounded-3xl shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-black uppercase tracking-tight flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" /> {creationModal.title}
            </DialogTitle>
          </DialogHeader>
          <div className="py-6 space-y-4">
             {(creationModal.mode === 'estado' || creationModal.mode === 'etiqueta') ? (
               <ManageTags mode={creationModal.mode} />
             ) : creationModal.mode !== 'pref' && creationModal.mode !== 'equipo' ? (
               <div className="space-y-2">
                 <label className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Nombre</label>
                 <Input 
                   placeholder={`Ej: ${creationModal.mode === 'espacio' ? 'Departamento Legal' : creationModal.mode === 'carpeta' ? 'Procesos 2026' : 'Lista de Tareas'}`}
                   value={newItemName}
                   onChange={(e) => setNewItemName(e.target.value)}
                   className="bg-accent/30 border-border/40 rounded-xl h-12 text-sm font-bold"
                 />
               </div>
             ) : null}

             {creationModal.mode === 'equipo' && (
                <div className="space-y-3">
                  <label className="text-[10px] font-black uppercase text-muted-foreground tracking-[0.2em] mb-1 block">Seleccionar Miembros del Equipo</label>
                  <div className="flex gap-2 mb-2">
                    <Input 
                      placeholder="Nombre del Abogado..." 
                      className="h-8 text-xs flex-1 bg-accent/20"
                      value={newItemName}
                      onChange={(e) => setNewItemName(e.target.value)}
                    />
                    <Button 
                      type="button"
                      size="sm" 
                      variant="secondary" 
                      className="h-8 text-[10px] font-bold"
                      disabled={!newItemName.trim() || isSubmitting}
                      onClick={async () => {
                        try {
                          setIsSubmitting(true);
                          const u = await createQuickUser(newItemName.trim());
                          toast.success("Abogado creado y seleccionado");
                          setNewItemName('');
                          // Re-fetch users and auto-select
                          const updatedUsers = await getUsers();
                          if (Array.isArray(updatedUsers)) setUsers(updatedUsers);
                          setSelectedUserIds(prev => [...prev, u.id]);
                        } catch(e) {
                          toast.error("Error al crear usuario");
                        } finally {
                          setIsSubmitting(false);
                        }
                      }}
                    >
                      <Plus className="h-3 w-3 mr-1" /> Crear
                    </Button>
                  </div>
                  <div className="max-h-[220px] overflow-y-auto pr-2 space-y-2 divide-y divide-border/20 border border-border/40 rounded-2xl bg-accent/10 p-3">
                    {users.map(u => {
                      const isSelected = selectedUserIds.includes(u.id);
                      const initials = (u.nombre || u.username || 'U').substring(0, 2).toUpperCase();
                      const isEditing = editingUserId === u.id;
                      return (
                        <div 
                          key={u.id} 
                          className={cn(
                            "flex items-center justify-between p-2.5 rounded-xl transition-all hover:bg-accent/40 group",
                            isSelected ? "bg-primary/10 border-primary/20" : "border-transparent"
                          )}
                        >
                          {isEditing ? (
                            <div className="flex-1 flex items-center gap-2 mr-2">
                              <Input 
                                value={editUserName} 
                                onChange={(e) => setEditUserName(e.target.value)} 
                                className="h-8 text-xs bg-background"
                                autoFocus
                                onKeyDown={async (e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    if (!editUserName.trim()) return;
                                    try {
                                      await updateQuickUser(u.id, editUserName.trim());
                                      setUsers(prev => prev.map(user => user.id === u.id ? { ...user, nombre: editUserName.trim() } : user));
                                      setEditingUserId(null);
                                      toast.success("Abogado actualizado");
                                    } catch (err) {
                                      toast.error("Error al actualizar");
                                    }
                                  } else if (e.key === 'Escape') {
                                    setEditingUserId(null);
                                  }
                                }}
                              />
                              <Button size="icon" variant="ghost" className="h-8 w-8 text-emerald-600 hover:text-emerald-700" onClick={async () => {
                                if (!editUserName.trim()) return;
                                try {
                                  await updateQuickUser(u.id, editUserName.trim());
                                  setUsers(prev => prev.map(user => user.id === u.id ? { ...user, nombre: editUserName.trim() } : user));
                                  setEditingUserId(null);
                                  toast.success("Abogado actualizado");
                                } catch (err) {
                                  toast.error("Error al actualizar");
                                }
                              }}>
                                <Check className="h-4 w-4" />
                              </Button>
                              <Button size="icon" variant="ghost" className="h-8 w-8 text-zinc-400 hover:text-zinc-600" onClick={() => setEditingUserId(null)}>
                                <X className="h-4 w-4" />
                              </Button>
                            </div>
                          ) : (
                            <>
                              <div className="flex items-center gap-3 flex-1 cursor-pointer" onClick={() => setSelectedUserIds(prev => prev.includes(u.id) ? prev.filter(id => id !== u.id) : [...prev, u.id])}>
                                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary/30 to-primary/10 border border-primary/20 flex items-center justify-center text-[11px] font-black text-primary shadow-sm">
                                  {initials}
                                </div>
                                <div className="flex flex-col">
                                  <span className="text-xs font-bold text-foreground">{u.nombre || u.username}</span>
                                  <span className="text-[9px] text-muted-foreground font-semibold uppercase tracking-wider">{u.role || 'ABOGADO'}</span>
                                </div>
                              </div>
                              <div className="flex items-center gap-1">
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setEditingUserId(u.id);
                                    setEditUserName(u.nombre || u.username || '');
                                  }}
                                  className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-primary/20 text-muted-foreground hover:text-primary rounded transition-all mr-1"
                                >
                                  <Edit3 className="h-3.5 w-3.5" />
                                </button>
                                <div 
                                  className={cn(
                                    "h-5 w-5 rounded-md border flex items-center justify-center transition-all cursor-pointer",
                                    isSelected ? "bg-primary border-primary text-primary-foreground scale-110 shadow-lg shadow-primary/20" : "border-muted-foreground/30 hover:border-primary/50"
                                  )}
                                  onClick={() => setSelectedUserIds(prev => prev.includes(u.id) ? prev.filter(id => id !== u.id) : [...prev, u.id])}
                                >
                                  {isSelected && <Check className="h-3 w-3 stroke-[3]" />}
                                </div>
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {selectedUserIds.length > 0 && (
                    <p className="text-[9px] text-primary font-bold uppercase tracking-wider text-right animate-pulse">
                      {selectedUserIds.length} {selectedUserIds.length === 1 ? 'usuario seleccionado' : 'usuarios seleccionados'}
                    </p>
                  )}
                </div>
              )}

             {creationModal.mode === 'pref' && (
               <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Nombre del Sistema</label>
                    <Input placeholder="EMDECOB JURÍDICO" className="bg-accent/30 border-border/40 rounded-xl h-12 text-sm font-bold" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">SMTP Host</label>
                      <Input placeholder="smtp.gmail.com" className="bg-accent/30 border-border/40 rounded-xl h-10 text-xs" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">SMTP Port</label>
                      <Input type="number" placeholder="587" className="bg-accent/30 border-border/40 rounded-xl h-10 text-xs" />
                    </div>
                  </div>
                  <p className="text-[9px] text-muted-foreground bg-primary/5 p-3 rounded-lg border border-primary/10 italic">Nota: Estas configuraciones afectan a las notificaciones globales y al branding del panel.</p>
               </div>
             )}

             {(creationModal.mode === 'tarea' || !creationModal.mode) && (
               <div className="space-y-2">
                 <label className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Fecha de Vencimiento</label>
                 <Input 
                   type="date"
                   value={newDueDate}
                   onChange={(e) => setNewDueDate(e.target.value)}
                   className="bg-accent/30 border-border/40 rounded-xl h-12 text-sm font-bold"
                 />
               </div>
             )}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreationModal({ ...creationModal, open: false })} className="rounded-xl font-bold">
              {creationModal.mode === 'estado' || creationModal.mode === 'etiqueta' ? 'Cerrar' : 'Cancelar'}
            </Button>
            {creationModal.mode !== 'estado' && creationModal.mode !== 'etiqueta' && (
              <Button 
                onClick={handleCreateConfirm} 
                disabled={
                  isSubmitting || 
                  (creationModal.mode !== 'equipo' && creationModal.mode !== 'pref' && !newItemName.trim()) ||
                  (creationModal.mode === 'equipo' && selectedUserIds.length === 0)
                } 
                className="bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl font-black uppercase tracking-widest px-8"
              >
                {isSubmitting ? "Creando..." : "Crear Ahora"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
