import { useState, useEffect, useMemo } from "react";
import { 
  CheckCircle2, Clock, Calendar as CalendarIcon, User as UserIcon, 
  Flag, AlertCircle, ChevronDown, ChevronRight, Activity, 
  Search, Filter, ListChecks, Hash, UserCheck, RefreshCw,
  FolderOpen, FolderClosed, CornerDownRight
} from "lucide-react";
import { getTasks, type Task, importClickUp } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { format, isToday, isBefore, parseISO, startOfToday } from "date-fns";
import { es } from "date-fns/locale";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { TaskDrawer } from "./TaskDrawer";
import { cn } from "@/lib/utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function MyTasksView() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("assigned");

  useEffect(() => {
    loadTasks();
  }, [user?.id]);

  const loadTasks = async () => {
    if (!user?.id) return;
    setIsLoading(true);
    try {
      const res = await getTasks({ assignee_id: user.id });
      setTasks(res || []);
    } catch (error) {
      toast({ title: "Error al cargar tareas", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSyncClickup = async () => {
    const token = localStorage.getItem("clickup_token");
    if (!token) {
      toast({ title: "Token de ClickUp no encontrado", description: "Configúralo en tu perfil.", variant: "destructive" });
      return;
    }

    setIsSyncing(true);
    try {
      toast({ title: "Sincronización iniciada", description: "Importando abogados y gestiones desde ClickUp..." });
      await importClickUp(token);
      // Esperar un momento y recargar
      setTimeout(loadTasks, 3000);
      toast({ title: "Sincronización completada", description: "Tu equipo y tareas están actualizados." });
    } catch (error) {
      toast({ title: "Fallo en la sincronización", variant: "destructive" });
    } finally {
      setIsSyncing(false);
    }
  };

  const getFilteredTasks = (mode: string) => {
    let filtered = tasks;
    if (mode === "assigned") {
      filtered = filtered.filter(t => t.assignee_id === user?.id);
    } else if (mode === "created") {
      filtered = filtered.filter(t => t.creator_id === user?.id);
    } else if (mode === "today") {
      const today = startOfToday();
      filtered = filtered.filter(t => {
        if (t.assignee_id !== user?.id) return false;
        if (!t.due_date) return false;
        const d = parseISO(t.due_date.toString());
        return isToday(d) || isBefore(d, today);
      });
    }
    return filtered.filter(t => 
      t.title.toLowerCase().includes(search.toLowerCase()) ||
      t.clickup_id?.toLowerCase().includes(search.toLowerCase())
    );
  };

  const overdueCount = useMemo(() => {
    const today = startOfToday();
    return tasks.filter(t => {
      if (t.assignee_id !== user?.id) return false;
      if (!t.due_date) return false;
      const d = parseISO(t.due_date.toString());
      return isToday(d) || isBefore(d, today);
    }).length;
  }, [tasks, user?.id]);

  const handleTaskClick = (task: Task) => {
    setSelectedTask(task);
    setIsDrawerOpen(true);
  };

  return (
    <div className="flex flex-col h-full bg-background animate-in fade-in duration-700">
      <div className="p-10 border-b border-border/50 bg-card/20">
        <div className="max-w-[1600px] mx-auto space-y-8">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
               <h1 className="text-4xl font-black tracking-tighter text-foreground flex items-center gap-5">
                  <div className="h-12 w-12 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-2xl">
                    <UserCheck className="h-7 w-7 text-primary" />
                  </div>
                  Experiencia de Usuario: Mis Tareas
               </h1>
               <p className="text-[12px] text-muted-foreground font-black uppercase tracking-[0.4em] opacity-80">
                  Panel central de litigio y gestión de términos legales
               </p>
            </div>
          </div>

          <Tabs defaultValue="assigned" className="w-full" onValueChange={setActiveTab}>
             <div className="flex items-center justify-between border-b border-border/50 pb-1">
                <TabsList className="bg-transparent border-none p-0 h-auto gap-10">
                   <TabsTrigger value="assigned" className="bg-transparent border-none text-muted-foreground data-[state=active]:text-primary data-[state=active]:shadow-none p-0 pb-4 rounded-none border-b-2 border-transparent data-[state=active]:border-primary transition-all text-[14px] font-black uppercase tracking-widest shadow-none hover:text-foreground">
                      Asignadas a mí
                   </TabsTrigger>
                   <TabsTrigger value="created" className="bg-transparent border-none text-muted-foreground data-[state=active]:text-primary data-[state=active]:shadow-none p-0 pb-4 rounded-none border-b-2 border-transparent data-[state=active]:border-primary transition-all text-[14px] font-black uppercase tracking-widest shadow-none hover:text-foreground">
                      Asignadas por mí
                   </TabsTrigger>
                   <TabsTrigger value="today" className="bg-transparent border-none text-muted-foreground data-[state=active]:text-red-500 data-[state=active]:shadow-none p-0 pb-4 rounded-none border-b-2 border-transparent data-[state=active]:border-red-500 transition-all text-[14px] font-black uppercase tracking-widest flex items-center gap-3 shadow-none hover:text-foreground">
                      Hoy y vencido
                      {overdueCount > 0 && <Badge className="bg-red-500/10 text-red-500 border-none text-[10px] h-5 px-2">{overdueCount}</Badge>}
                   </TabsTrigger>
                </TabsList>

                <div className="flex items-center gap-6 pb-4">
                   <div className="relative group w-80">
                      <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                      <Input 
                        placeholder="Filtrar gestiones..." 
                        className="pl-12 h-10 bg-card/40 border-border/50 rounded-xl focus:ring-primary/20 focus:border-primary/40 transition-all text-[13px] font-medium text-foreground"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                   </div>
                   <Button variant="outline" className="h-10 w-10 rounded-xl border-border/50 bg-card/40 text-muted-foreground">
                      <Filter className="h-4 w-4" />
                   </Button>
                </div>
             </div>

             <div className="mt-8">
                <TabsContent value="assigned" className="m-0 focus-visible:outline-none outline-none">
                   <TaskList tasks={getFilteredTasks("assigned")} isLoading={isLoading} onTaskClick={handleTaskClick} />
                </TabsContent>
                <TabsContent value="created" className="m-0 focus-visible:outline-none outline-none">
                   <TaskList tasks={getFilteredTasks("created")} isLoading={isLoading} onTaskClick={handleTaskClick} />
                </TabsContent>
                <TabsContent value="today" className="m-0 focus-visible:outline-none outline-none">
                   <TaskList tasks={getFilteredTasks("today")} isLoading={isLoading} onTaskClick={handleTaskClick} isUrgent />
                </TabsContent>
             </div>
          </Tabs>
        </div>
      </div>

      <TaskDrawer 
        task={selectedTask}
        open={isDrawerOpen}
        onOpenChange={setIsDrawerOpen}
        onTaskUpdate={(updated) => {
          setTasks(prev => prev.map(t => t.id === updated.id ? updated : t));
          setSelectedTask(updated);
        }}
        clickupToken={localStorage.getItem("clickup_token") || undefined}
      />
    </div>
  );
}

interface TaskListProps {
  tasks: Task[];
  isLoading: boolean;
  onTaskClick: (task: Task) => void;
  isUrgent?: boolean;
}

function TaskList({ tasks, isLoading, onTaskClick, isUrgent }: TaskListProps) {
  const [expandedCases, setExpandedCases] = useState<Record<string, boolean>>({});
  const [expandedParents, setExpandedParents] = useState<Record<number, boolean>>({});

  // Grouping logic:
  const grouped = useMemo(() => {
    // 1. Filter parent and sub tasks
    const parentTasks = tasks.filter(t => !t.parent_id);
    const subTasks = tasks.filter(t => t.parent_id);

    // Map parent tasks by ID for quick lookup of nested subtasks
    const subtasksMap: Record<number, Task[]> = {};
    subTasks.forEach(sub => {
      if (sub.parent_id) {
        if (!subtasksMap[sub.parent_id]) subtasksMap[sub.parent_id] = [];
        subtasksMap[sub.parent_id].push(sub);
      }
    });

    // 2. Group these parent tasks by Case
    const casesMap: Record<string, { id: string; radicado: string; demandante?: string; demandado?: string; items: Array<{ task: Task; subtasks: Task[] }> }> = {};
    const generalTasks: Array<{ task: Task; subtasks: Task[] }> = [];

    parentTasks.forEach(pt => {
      const key = pt.case_id ? String(pt.case_id) : "general";
      const item = { task: pt, subtasks: subtasksMap[pt.id] || [] };
      
      if (key === "general") {
        generalTasks.push(item);
      } else {
        if (!casesMap[key]) {
          casesMap[key] = {
            id: key,
            radicado: pt.case_radicado || `Caso #${pt.case_id}`,
            demandante: pt.case_demandante,
            demandado: pt.case_demandado,
            items: []
          };
        }
        casesMap[key].items.push(item);
      }
    });

    // Add orphaned subtasks whose parents are not in the list
    const parentIds = new Set(parentTasks.map(p => p.id));
    subTasks.forEach(sub => {
      if (sub.parent_id && !parentIds.has(sub.parent_id)) {
        const key = sub.case_id ? String(sub.case_id) : "general";
        const item = { task: sub, subtasks: [] };
        if (key === "general") {
          generalTasks.push(item);
        } else {
          if (!casesMap[key]) {
            casesMap[key] = {
              id: key,
              radicado: sub.case_radicado || `Caso #${sub.case_id}`,
              demandante: sub.case_demandante,
              demandado: sub.case_demandado,
              items: []
            };
          }
          casesMap[key].items.push(item);
        }
      }
    });

    return { cases: Object.values(casesMap), general: generalTasks };
  }, [tasks]);

  if (isLoading) {
    return (
      <div className="py-40 text-center space-y-6 opacity-40">
         <Activity className="h-16 w-16 mx-auto animate-spin text-primary" />
         <p className="text-[11px] font-black uppercase tracking-[0.5em] text-muted-foreground">Analizando carga de trabajo...</p>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="py-40 text-center space-y-10 bg-card/5 rounded-[4rem] border border-dashed border-border/50 mx-10">
         <CheckCircle2 className="h-24 w-24 mx-auto text-muted-foreground opacity-20" />
         <div className="space-y-3">
            <p className="text-2xl font-black text-muted-foreground tracking-tight">Todo al día, abogado</p>
            <p className="text-[10px] text-muted-foreground/50 font-black uppercase tracking-widest">No hay gestiones pendientes en este panel</p>
         </div>
      </div>
    );
  }

  const toggleCase = (caseId: string) => {
    setExpandedCases(prev => ({ ...prev, [caseId]: prev[caseId] === false }));
  };

  const toggleParent = (parentId: number) => {
    setExpandedParents(prev => ({ ...prev, [parentId]: prev[parentId] === false }));
  };

  const renderTaskRow = (task: Task, subtasksCount: number, isSubtask = false) => {
    const isParentExpanded = expandedParents[task.id] !== false; // default expanded
    return (
      <div className="group/row">
        <div 
           className={cn(
             "grid grid-cols-[1fr_180px_120px_180px] gap-10 px-12 py-4 hover:bg-muted/30 transition-all cursor-pointer border-l-2 border-transparent hover:border-primary",
             isSubtask ? "bg-muted/5 pl-20" : "bg-card/10"
           )}
           onClick={(e) => {
             // If click is on expand/collapse chevron, don't trigger task detail drawer
             const target = e.target as HTMLElement;
             if (target.closest('.chevron-toggle')) return;
             onTaskClick(task);
           }}
        >
           <div className="flex items-center gap-4">
              {!isSubtask && subtasksCount > 0 ? (
                <button 
                  onClick={() => toggleParent(task.id)}
                  className="chevron-toggle p-1 hover:bg-muted rounded transition-colors text-muted-foreground hover:text-foreground"
                >
                  {isParentExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>
              ) : !isSubtask ? (
                <div className="w-6" /> // spacer to align titles
              ) : (
                <CornerDownRight className="h-4 w-4 text-muted-foreground/40 mr-1" />
              )}
              
              <div className={cn(
                "h-8 w-8 rounded-lg bg-background border border-border/50 flex items-center justify-center text-primary shadow shadow-inner",
                isSubtask && "h-6 w-6 text-muted-foreground/60"
              )}>
                 <Hash className={cn("h-4 w-4", isSubtask && "h-3 w-3")} />
              </div>
              <div className="flex flex-col gap-0.5">
                 <span className="text-[14.5px] font-bold text-foreground group-hover/row:text-primary transition-colors tracking-tight leading-tight">{task.title}</span>
                 <span className="text-[9px] text-muted-foreground font-semibold tracking-widest uppercase opacity-60">REF: {task.clickup_id || task.id}</span>
              </div>
           </div>
           <div className="flex items-center justify-center">
              <Badge className={cn(
                "px-3 py-0.5 rounded text-[8px] font-black uppercase tracking-widest border-none shadow",
                task.status?.toLowerCase().includes('done') ? "bg-[#2da44e] text-white" : "bg-primary/20 text-primary"
              )}>
                 {task.status || 'ABIERTO'}
              </Badge>
           </div>
           <div className="flex items-center justify-center">
              <Flag className={cn(
                "h-4 w-4 drop-shadow transition-transform group-hover/row:scale-125",
                task.priority?.toLowerCase() === 'high' ? "text-red-500" : "text-muted-foreground/20"
              )} />
           </div>
           <div className="flex items-center justify-end">
              <div className={cn(
                "flex items-center gap-2 text-[11px] font-bold uppercase tracking-tighter px-4 py-1.5 rounded-lg border transition-all",
                task.due_date && isBefore(parseISO(task.due_date.toString()), startOfToday()) 
                 ? "bg-red-500/10 text-red-500 border-red-500/20 shadow-red-500/20 animate-pulse" 
                 : "bg-muted text-muted-foreground border-border/50"
              )}>
                 <Clock className="h-3.5 w-3.5" />
                 {task.due_date ? format(parseISO(task.due_date.toString()), "d MMM, yyyy", { locale: es }) : 'SIN TÉRMINO'}
              </div>
           </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header columns */}
      <div className="grid grid-cols-[1fr_180px_120px_180px] gap-10 px-12 py-3 text-[9px] font-black uppercase text-muted-foreground tracking-[0.4em]">
         <div>Descripción de la Gestión</div>
         <div className="text-center">Estado Judicial</div>
         <div className="text-center">Prioridad</div>
         <div className="text-right">Término Legal</div>
      </div>

      {/* Render Case Groups */}
      {grouped.cases.map(c => {
        const isCaseExpanded = expandedCases[c.id] !== false; // default expanded
        return (
          <div key={c.id} className="bg-card/10 rounded-[2rem] border border-border/50 overflow-hidden shadow-2xl transition-all">
            {/* Case Header (Folder UI) */}
            <div 
              onClick={() => toggleCase(c.id)}
              className="flex items-center justify-between px-8 py-4 bg-muted/20 hover:bg-muted/30 transition-colors cursor-pointer border-b border-border/50"
            >
              <div className="flex items-center gap-4">
                {isCaseExpanded ? (
                  <FolderOpen className="h-5 w-5 text-primary" />
                ) : (
                  <FolderClosed className="h-5 w-5 text-primary" />
                )}
                <div className="flex flex-col">
                  <span className="text-sm font-bold text-foreground tracking-tight">Radicado: {c.radicado}</span>
                  {(c.demandante || c.demandado) && (
                    <span className="text-[10px] text-muted-foreground font-semibold">
                      {c.demandante && `Dte: ${c.demandante}`} {c.demandado && `| Ddo: ${c.demandado}`}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <Badge variant="secondary" className="text-[10px] font-bold">
                  {c.items.length} {c.items.length === 1 ? 'gestión' : 'gestiones'}
                </Badge>
                {isCaseExpanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
              </div>
            </div>

            {/* Case Tasks Content */}
            {isCaseExpanded && (
              <div className="divide-y divide-border/50">
                {c.items.map(({ task, subtasks }) => {
                  const isParentExpanded = expandedParents[task.id] !== false;
                  return (
                    <div key={task.id} className="divide-y divide-border/30">
                      {renderTaskRow(task, subtasks.length, false)}
                      {subtasks.length > 0 && isParentExpanded && (
                        <div className="divide-y divide-border/20 bg-muted/5">
                          {subtasks.map(sub => renderTaskRow(sub, 0, true))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      {/* Render General/Sin Radicado Tasks */}
      {grouped.general.length > 0 && (
        <div className="bg-card/10 rounded-[2rem] border border-border/50 overflow-hidden shadow-2xl transition-all">
          {/* General Header */}
          <div 
            onClick={() => toggleCase("general")}
            className="flex items-center justify-between px-8 py-4 bg-muted/20 hover:bg-muted/30 transition-colors cursor-pointer border-b border-border/50"
          >
            <div className="flex items-center gap-4">
              {expandedCases["general"] !== false ? (
                <FolderOpen className="h-5 w-5 text-muted-foreground" />
              ) : (
                <FolderClosed className="h-5 w-5 text-muted-foreground" />
              )}
              <div className="flex flex-col">
                <span className="text-sm font-bold text-foreground tracking-tight">Gestiones Generales</span>
                <span className="text-[10px] text-muted-foreground font-semibold">Tareas administrativas o sin radicado asociado</span>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="secondary" className="text-[10px] font-bold">
                {grouped.general.length} {grouped.general.length === 1 ? 'gestión' : 'gestiones'}
              </Badge>
              {expandedCases["general"] !== false ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </div>
          </div>

          {/* General Tasks Content */}
          {expandedCases["general"] !== false && (
            <div className="divide-y divide-border/50">
              {grouped.general.map(({ task, subtasks }) => {
                const isParentExpanded = expandedParents[task.id] !== false;
                return (
                  <div key={task.id} className="divide-y divide-border/30">
                    {renderTaskRow(task, subtasks.length, false)}
                    {subtasks.length > 0 && isParentExpanded && (
                      <div className="divide-y divide-border/20 bg-muted/5">
                        {subtasks.map(sub => renderTaskRow(sub, 0, true))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
