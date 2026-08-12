import { useState, useEffect, useMemo } from "react";
import { 
  X, Calendar as CalendarIcon, User as UserIcon, CheckCircle2, 
  Clock, Tag, Paperclip, MessageSquare, Plus, ChevronRight, 
  Send, Trash2, ListChecks, Zap, Flag, AlertCircle, Edit3,
  UserCheck, Search, Activity, CornerDownRight, Smile, MoreHorizontal,
  ChevronDown, CalendarDays, Layout, Check, Trash, RefreshCw,
  Play, Settings, Hash, Paperclip as AttachmentIcon, MessageCircle,
  ChevronUp
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { 
  updateTask, addComment, deleteComment, updateComment,
  addChecklistItem, updateChecklistItem, deleteChecklistItem,
  getUsers, getTags, getStatuses, getTaskDetail, createTask, deleteTask, createTag,
  type Task as TaskType, type User, type Tag as TagType
} from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { format, isValid, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface TaskDrawerProps {
  task: TaskType | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTaskUpdate: (updatedTask: TaskType) => void;
  onTaskDelete?: (taskId: number) => void;
  clickupToken?: string;
  allAssignees?: string[];
  allStatuses?: string[];
}

export function TaskDrawer({ task, open, onOpenChange, onTaskUpdate, onTaskDelete, clickupToken, allStatuses: propStatuses = [] }: TaskDrawerProps) {
  const { toast } = useToast();
  const [editedTitle, setEditedTitle] = useState('');
  const [editedDesc, setEditedDesc] = useState('');
  const [editedDueDate, setEditedDueDate] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [fullTask, setFullTask] = useState<TaskType | null>(null);
  const [newComment, setNewComment] = useState('');
  const [newChecklist, setNewChecklist] = useState("");
  const [allTags, setAllTags] = useState<TagType[]>([]);
  const [allSystemStatuses, setAllSystemStatuses] = useState<string[]>([]);
  
  // Collapsible states
  const [isSubtasksOpen, setIsSubtasksOpen] = useState(true);
  const [isChecklistOpen, setIsChecklistOpen] = useState(true);

  // Subtask edit states
  const [editingSubtaskId, setEditingSubtaskId] = useState<number | null>(null);
  const [editSubtaskTitle, setEditSubtaskTitle] = useState("");

  // Subtask form states
  const [showSubtaskForm, setShowSubtaskForm] = useState(false);
  const [newSubtaskTitle, setNewSubtaskTitle] = useState("");
  const [newSubtaskDate, setNewSubtaskDate] = useState("");
  const [newSubtaskAssigneeId, setNewSubtaskAssigneeId] = useState<number | undefined>(undefined);
  const [newSubtaskPriority, setNewSubtaskPriority] = useState<string>("normal");

  const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
  const [editingCommentText, setEditingCommentText] = useState("");
  const [isNote, setIsNote] = useState(true);

  const displayTask = fullTask || task;

  const COMMON_EMOJIS = ["👍", "❤️", "🔥", "✅", "🚀", "⏳", "⚠️", "⚖️", "📝", "👏"];

  useEffect(() => {
    if (task && open) {
      setFullTask(null); // limpiar datos anteriores para evitar mostrar datos de otra tarea
      setEditedTitle(task.title || '');
      setEditedDesc(task.description || '');
      setEditedDueDate(task.due_date ? format(parseISO(task.due_date.toString()), 'yyyy-MM-dd') : '');
      if (task.id) refreshTask();
      
      getUsers().then(res => {
        if (Array.isArray(res)) setUsers(res);
      }).catch(console.error);

      getTags().then(res => {
        if (Array.isArray(res) && res.length > 0) setAllTags(res);
        else if (task.tags) setAllTags(task.tags);
      }).catch(() => {
        if (task.tags) setAllTags(task.tags);
      });

      getStatuses().then(res => setAllSystemStatuses(Array.isArray(res) ? res : [])).catch(console.error);
    }
  }, [task?.id, open]);

  const refreshTask = async () => {
    if (!task || !task.id) return;
    setIsLoading(true);
    try {
      const detail = await getTaskDetail(task.id, clickupToken);
      if (detail) {
        setFullTask(detail);
        onTaskUpdate(detail);
      }
    } catch (error: any) {
      console.error("Error refreshing task", error);
      const errorDetail = error.payload?.detail || error.message || "No se pudo sincronizar con ClickUp.";
      toast({ 
        title: "Error al refrescar", 
        description: typeof errorDetail === 'object' ? JSON.stringify(errorDetail) : String(errorDetail), 
        variant: "destructive" 
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteTask = async () => {
    if (!displayTask || !displayTask.id) return;
    if (!confirm('¿Estás seguro de eliminar esta tarea? Se eliminarán también todas sus gestiones, comentarios y checklist.')) return;
    try {
      await deleteTask(displayTask.id);
      toast({ title: 'Tarea eliminada', description: 'La tarea y sus gestiones han sido eliminadas.' });
      if (onTaskDelete) onTaskDelete(displayTask.id);
      onOpenChange(false);
    } catch (error: any) {
      toast({ title: 'Error al eliminar', description: String(error.message || 'Error desconocido'), variant: 'destructive' });
    }
  };

  const handleSave = async (updates: Partial<TaskType>) => {
    if (!displayTask) return;
    try {
      // Solo enviamos los campos que el backend espera para evitar errores de validación o 500
      const allowedFields = ['title', 'description', 'status', 'priority', 'due_date', 'assignee_id', 'case_id', 'assignee_ids'];
      const cleanedUpdates: any = {};
      
      allowedFields.forEach(field => {
        if (field in updates) {
          (cleanedUpdates as any)[field] = (updates as any)[field];
        }
      });

      // Manejo especial de tags si vienen en el objeto updates
      if ('tags' in updates) {
        cleanedUpdates.tags = (updates.tags as any[]).map(t => typeof t === 'string' ? t : t.name);
      }

      if (cleanedUpdates.due_date && typeof cleanedUpdates.due_date === 'string' && cleanedUpdates.due_date.trim() !== '') {
        cleanedUpdates.due_date = new Date(cleanedUpdates.due_date).toISOString();
      } else if (cleanedUpdates.due_date === '') {
        cleanedUpdates.due_date = null;
      }

      if (!displayTask.id) {
        // Es una tarea nueva, usar createTask
        const created = await createTask({
          ...displayTask,
          ...cleanedUpdates,
          title: editedTitle || "Nueva Tarea"
        });
        onTaskUpdate(created);
        setFullTask(created);
        toast({ title: "Tarea creada", description: "La tarea se ha guardado correctamente." });
      } else {
        // Es una tarea existente, usar updateTask
        const updated = await updateTask(displayTask.id, cleanedUpdates);
        onTaskUpdate(updated);
        setFullTask(updated);
      }
    } catch (error: any) {
      console.error("Error in handleSave", error);
      const detail = error.payload?.detail || error.message || "Error desconocido";
      toast({ 
        title: "Error de sincronización", 
        description: String(detail), 
        variant: "destructive" 
      });
    }
  };

  const toggleAssignee = (userId: number) => {
    if (!displayTask) return;
    const currentIds = (displayTask.assignees || []).map(a => a.id);
    let newIds = currentIds.includes(userId) ? currentIds.filter(id => id !== userId) : [...currentIds, userId];
    handleSave({ assignee_ids: newIds } as any);
  };

  const toggleTag = (tagName: string) => {
    if (!displayTask) return;
    const currentTags = (displayTask.tags || []).map(t => t.name);
    let newTags = currentTags.includes(tagName) ? currentTags.filter(t => t !== tagName) : [...currentTags, tagName];
    handleSave({ tags: newTags } as any);
  };

  const toggleSubtaskStatus = async (st: any, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!displayTask) return;
    const isCompleted = ['completado', 'completo', 'finalizado', 'terminado', 'closed', 'done'].includes(st.status?.toLowerCase() || '');
    const newStatus = isCompleted ? 'to do' : 'completado';
    try {
      await updateTask(st.id, { status: newStatus });
      await refreshTask();
      if (onTaskUpdate) onTaskUpdate({ ...displayTask });
    } catch (error) {
      console.error("Error toggling subtask status:", error);
    }
  };

  const toggleSubtaskTag = async (st: any, tagName: string) => {
    if (!displayTask) return;
    const currentTags = (st.tags || []).map((t: any) => typeof t === 'string' ? t : t.name);
    let newTags = currentTags.includes(tagName) ? currentTags.filter((t: any) => t !== tagName) : [...currentTags, tagName];
    try {
      await updateTask(st.id, { tags: newTags });
      await refreshTask();
      if (onTaskUpdate) onTaskUpdate({ ...displayTask });
    } catch (error) {
      console.error("Error toggling subtask tag:", error);
    }
  };

  const handleAddComment = async () => {
    if (!displayTask || !newComment.trim()) return;
    try {
      await addComment(displayTask.id, newComment, clickupToken);
      setNewComment('');
      refreshTask();
    } catch (error) {
      toast({ title: "Error al publicar registro" });
    }
  };

  const handleUpdateComment = async (id: number) => {
    if (!editingCommentText.trim()) return;
    try {
      await updateComment(id, editingCommentText);
      setEditingCommentId(null);
      refreshTask();
    } catch (error) {
      toast({ title: "Error al editar" });
    }
  };

  const handleDeleteComment = async (id: number) => {
    if (!confirm("¿Eliminar registro de actividad?")) return;
    try {
      await deleteComment(id);
      refreshTask();
    } catch (error) {
      toast({ title: "Error al eliminar" });
    }
  };

  const handleCreateSubtask = async () => {
    if (!displayTask || !newSubtaskTitle.trim()) return;
    try {
      const isoDate = newSubtaskDate ? new Date(newSubtaskDate).toISOString() : undefined;
      await createTask({
        title: newSubtaskTitle,
        parent_id: displayTask.id,
        due_date: isoDate as any,
        list_id: displayTask.list_id,
        case_id: displayTask.case_id,
        assignee_id: newSubtaskAssigneeId,
        priority: newSubtaskPriority,
        status: 'to do'
      });
      setNewSubtaskTitle("");
      setNewSubtaskDate("");
      setNewSubtaskAssigneeId(undefined);
      setNewSubtaskPriority("normal");
      setShowSubtaskForm(false);
      await refreshTask();
      toast({ title: "Gestión creada correctamente" });
    } catch (error) {
      toast({ title: "Error al crear gestión", variant: "destructive" });
    }
  };

  const handleAddChecklist = async () => {
    if (!displayTask || !newChecklist.trim()) return;
    try {
      await addChecklistItem(displayTask.id, newChecklist);
      setNewChecklist("");
      refreshTask();
    } catch (error) {
      toast({ title: "Error" });
    }
  };

  const addEmoji = (emoji: string) => {
    setNewComment(prev => prev + emoji);
  };

  if (!displayTask) return null;

  const statusOptions = Array.from(new Set([
    'ABIERTO', 'TO DO', 'IN PROGRESS', 'PENDIENTE', 'ALMP', '468', 'REMATE', 'AVALUO', 'COMPLETO', 'CLOSED',
    ...(allSystemStatuses || []),
    ...(propStatuses || [])
  ])).filter(Boolean);

  const currentStatus = (displayTask.status || 'ABIERTO').toUpperCase();
  
  const totalSub = displayTask.subtasks?.length || 0;
  const doneSub = displayTask.subtasks?.filter(s => ['completado', 'completo', 'finalizado', 'terminado', 'closed', 'done'].includes(s.status?.toLowerCase() || '')).length || 0;
  const progressSub = totalSub > 0 ? (doneSub / totalSub) * 100 : 0;

  const totalCheck = displayTask.checklists?.length || 0;
  const doneCheck = displayTask.checklists?.filter(c => c.is_completed).length || 0;
  const progressCheck = totalCheck > 0 ? (doneCheck / totalCheck) * 100 : 0;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[95vw] p-0 bg-background border-none text-foreground flex flex-col shadow-2xl font-sans outline-none">
        <SheetHeader className="sr-only"><SheetTitle>Consola Judicial Multi-Modo</SheetTitle></SheetHeader>
        
        <div className="flex flex-1 overflow-hidden h-full">
          {/* MAIN PANEL (70%) */}
          <div className="flex-[2] flex flex-col overflow-hidden bg-background">
             <ScrollArea className="flex-1 px-8 pt-8 pb-20">
                <div className="space-y-8 max-w-[1500px] mx-auto">
                   
                   {/* Top Header Compact */}
                   <div className="flex items-center justify-between text-[10px] font-black text-muted-foreground uppercase tracking-[0.3em]">
                      <div className="flex items-center gap-4">
                         <div className="flex items-center gap-2 px-3 py-1 bg-muted/30 rounded-full border border-border/50 shadow-inner">
                            <Badge className="h-3.5 w-3.5 p-0 bg-[#2da44e] flex items-center justify-center rounded-sm"><Check className="h-2.5 w-2.5 text-white" /></Badge>
                            <span>Expediente Jurídico</span>
                         </div>
                         <span className="text-primary font-black tracking-[0.4em]">{displayTask.clickup_id || displayTask.id}</span>
                      </div>
                      <div className="flex items-center gap-4">
                         <Button variant="ghost" size="sm" onClick={refreshTask} disabled={isLoading} className="text-muted-foreground hover:text-foreground gap-2 font-black text-[9px] tracking-widest transition-all">
                            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} /> REFRESCAR
                         </Button>
                         {displayTask.id && (
                           <Button variant="ghost" size="sm" onClick={handleDeleteTask} className="text-muted-foreground hover:text-red-500 gap-2 font-black text-[9px] tracking-widest transition-all">
                              <Trash2 className="h-3.5 w-3.5" /> ELIMINAR
                           </Button>
                         )}
                         <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)} className="h-8 w-8 text-muted-foreground hover:text-foreground">
                           <X className="h-6 w-6" />
                         </Button>
                      </div>
                   </div>

                   {/* Title */}
                   <input 
                     className="w-full bg-transparent text-2xl font-black tracking-tight border-none focus:ring-0 p-0 text-foreground placeholder:text-muted-foreground/20 transition-all"
                     value={editedTitle}
                     onChange={(e) => setEditedTitle(e.target.value)}
                     onBlur={() => handleSave({ title: editedTitle })}
                   />

                   {/* Metadata Bar */}
                   <div className="grid grid-cols-4 gap-6 py-6 border-y border-border/50 bg-card/20 px-6 rounded-[2rem] shadow-inner">
                      {/* Estado */}
                      <div className="flex flex-col gap-2">
                         <span className="text-[9px] text-muted-foreground font-black uppercase tracking-[0.2em] flex items-center gap-2">Estado Actual</span>
                         <Select value={statusOptions.includes(currentStatus) ? currentStatus : undefined} onValueChange={(v) => handleSave({ status: v })}>
                            <SelectTrigger className="h-10 w-full bg-[#2da44e] hover:bg-[#34bc5a] text-white text-[11px] font-black uppercase rounded-xl border-none px-4 transition-all">
                               <SelectValue placeholder={currentStatus} />
                            </SelectTrigger>
                            <SelectContent className="bg-popover border-border text-popover-foreground shadow-2xl rounded-xl">
                               {statusOptions.map(s => (
                                 <SelectItem key={s} value={s} className="uppercase text-[10px] font-black py-2.5 tracking-widest">{s}</SelectItem>
                               ))}
                            </SelectContent>
                         </Select>
                      </div>

                      {/* Responsable */}
                      <div className="flex flex-col gap-2">
                         <span className="text-[9px] text-muted-foreground font-black uppercase tracking-[0.2em] flex items-center gap-2">Responsable</span>
                         <Popover>
                            <PopoverTrigger asChild>
                               <Button variant="outline" className="h-10 w-full bg-card/40 border-border/50 rounded-xl flex items-center justify-start gap-3 px-3 hover:bg-card/60 transition-all group">
                                  <div className="flex -space-x-2">
                                     {displayTask.assignees?.length ? (
                                        displayTask.assignees.map(a => (
                                          <div key={a.id} className="h-7 w-7 rounded-full bg-primary text-primary-foreground border-2 border-background flex items-center justify-center text-[10px] font-black shadow-lg">{a.nombre?.[0] || a.username[0]}</div>
                                        ))
                                     ) : (
                                        <div className="h-7 w-7 rounded-full border border-dashed border-muted-foreground/30 bg-muted/10 flex items-center justify-center text-muted-foreground"><UserIcon className="h-3.5 w-3.5" /></div>
                                     )}
                                  </div>
                                  <span className="text-[12px] font-black text-muted-foreground truncate group-hover:text-primary transition-colors tracking-tight">
                                     {displayTask.assignees?.length ? displayTask.assignees.map(a => a.nombre || a.username).join(', ') : (displayTask.assignee_name || 'Sin Asignar')}
                                  </span>
                               </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-80 p-3 bg-popover border-border text-popover-foreground rounded-2xl shadow-2xl">
                               <ScrollArea className="h-[300px]">
                                  <div className="p-2 border-b border-border/50 mb-2 text-[9px] font-black uppercase text-muted-foreground tracking-widest text-center">Equipo de Litigio</div>
                                  <div className="space-y-0.5">
                                    {users.map(u => (
                                      <div key={u.id} className="flex items-center justify-between p-3 hover:bg-muted/50 rounded-xl cursor-pointer transition-all border border-transparent hover:border-border/30" onClick={() => toggleAssignee(u.id)}>
                                         <span className="text-[13px] font-bold text-foreground">{u.nombre || u.username}</span>
                                         <Checkbox checked={displayTask.assignees?.some(a => a.id === u.id)} className="h-5 w-5 data-[state=checked]:bg-primary" />
                                      </div>
                                    ))}
                                  </div>
                               </ScrollArea>
                            </PopoverContent>
                         </Popover>
                      </div>

                      {/* Término */}
                      <div className="flex flex-col gap-2">
                         <span className="text-[9px] text-muted-foreground font-black uppercase tracking-[0.2em] flex items-center gap-2">Término Legal</span>
                         <div className="h-10 bg-card/40 border border-border/50 rounded-xl flex items-center gap-3 px-4 hover:border-primary/40 transition-all">
                            <input 
                              type="date" 
                              className="bg-transparent border-none focus:ring-0 text-[12px] font-black uppercase text-foreground p-0 w-full cursor-pointer"
                              value={editedDueDate}
                              onChange={(e) => {
                                setEditedDueDate(e.target.value);
                                handleSave({ due_date: e.target.value } as any);
                              }}
                            />
                         </div>
                      </div>

                      {/* Clasificación */}
                      <div className="flex flex-col gap-2">
                         <span className="text-[9px] text-muted-foreground font-black uppercase tracking-[0.2em] flex items-center gap-2">Clasificación</span>
                         <Popover>
                            <PopoverTrigger asChild>
                               <Button variant="outline" className="h-10 w-full bg-card/40 border-border/50 rounded-xl flex flex-wrap gap-1.5 px-3 hover:bg-card/60 transition-all justify-start overflow-hidden shadow-inner">
                                  {displayTask.tags?.length ? (
                                    displayTask.tags.map(t => (
                                      <Badge key={t.id} style={{ backgroundColor: t.color || '#3b82f6', color: '#fff' }} className="h-5 text-[8px] font-black px-2 rounded-md border-none shadow-lg">
                                         {t.name}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-[10px] text-muted-foreground/40 font-black tracking-widest uppercase">+ TAGS</span>
                                  )}
                               </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-80 p-3 bg-popover border-border text-popover-foreground rounded-2xl shadow-2xl">
                               <ScrollArea className="h-[250px]">
                                  <div className="grid grid-cols-1 gap-1.5">
                                <div className="p-2 mb-2">
                                  <Input 
                                    placeholder="Nueva etiqueta..." 
                                    className="h-9 bg-accent/30 border-border/40 rounded-lg text-xs"
                                    onKeyDown={async (e: any) => {
                                      if (e.key === 'Enter') {
                                        const val = e.target.value;
                                        if (val.trim()) {
                                          try {
                                              await createTag(val.trim());
                                              const updatedTags = await getTags();
                                              setAllTags(updatedTags);
                                          } catch (err) {
                                              console.error("Error creating tag", err);
                                          }
                                          toggleTag(val.trim());
                                          e.target.value = '';
                                        }
                                      }
                                    }}
                                  />
                                </div>
                                {allTags.map(t => (
                                      <div key={t.id} className="flex items-center justify-between p-2.5 hover:bg-muted/50 rounded-xl cursor-pointer transition-all border border-transparent hover:border-border/30" onClick={() => toggleTag(t.name)}>
                                         <div className="flex items-center gap-3">
                                            <div className="h-3.5 w-3.5 rounded-full shadow-lg" style={{ backgroundColor: t.color || '#3b82f6' }} />
                                            <span className="text-[13px] font-bold text-foreground">{t.name}</span>
                                         </div>
                                         {displayTask.tags?.some(gt => gt.name === t.name) && <CheckCircle2 className="h-5 w-5 text-[#2da44e]" />}
                                      </div>
                                    ))}
                                  </div>
                               </ScrollArea>
                            </PopoverContent>
                         </Popover>
                      </div>
                   </div>

                   {/* Description */}
                   <div className="space-y-4">
                      <div className="flex items-center gap-3 text-muted-foreground italic text-[11px] font-black tracking-widest uppercase">
                         <Activity className="h-4 w-4 text-primary opacity-50" /> Síntesis Procesal
                      </div>
                      <div className="bg-card/10 rounded-[2rem] p-8 border border-border/50 shadow-inner">
                        <Textarea 
                          className="min-h-[150px] bg-transparent border-none p-0 text-[15px] leading-relaxed text-foreground/80 focus:ring-0 placeholder:text-muted-foreground/10 transition-all font-medium"
                          placeholder="Estado detallado de la actuación judicial..."
                          value={editedDesc}
                          onChange={(e) => setEditedDesc(e.target.value)}
                          onBlur={() => handleSave({ description: editedDesc })}
                        />
                      </div>
                   </div>

                   {/* Gestiones Técnicas */}
                   <div className="space-y-6 pt-4 border-t border-border/50">
                      <div className="flex items-center justify-between group cursor-pointer" onClick={() => setIsSubtasksOpen(!isSubtasksOpen)}>
                         <div className="flex items-center gap-6">
                            <div className="flex items-center gap-3 text-muted-foreground font-black text-[14px] uppercase tracking-[0.3em]">
                               {isSubtasksOpen ? <ChevronUp className="h-6 w-6 text-primary" /> : <ChevronDown className="h-6 w-6 text-primary" />} Gestiones Técnicas
                            </div>
                            <div className="flex items-center gap-4 text-[11px] text-muted-foreground font-black tracking-widest bg-card/20 px-6 py-2 rounded-full border border-border/50 shadow-inner">
                               <span>{doneSub}/{totalSub} COMPLETADAS</span>
                               <Progress value={progressSub} className="w-48 h-1.5 bg-muted/30 ring-1 ring-border/20" />
                            </div>
                         </div>
                         <div className="flex items-center gap-4" onClick={(e) => e.stopPropagation()}>
                            <Button variant="outline" size="icon" onClick={refreshTask} className="h-9 w-9 rounded-xl bg-card/40 border-border/50 hover:bg-card/60 transition-all shadow-lg"><RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} /></Button>
                            <Button size="sm" onClick={() => { setIsSubtasksOpen(true); setShowSubtaskForm(true); }} className="h-10 px-6 rounded-xl bg-primary text-primary-foreground font-black text-[10px] tracking-widest uppercase hover:scale-105 active:scale-95 transition-all shadow-xl shadow-primary/20">
                               + GESTIÓN
                            </Button>
                         </div>
                      </div>

                      {isSubtasksOpen && (
                        <div className="space-y-6 animate-in fade-in duration-300">
                          <div className="bg-card/10 rounded-[2rem] border border-border/50 overflow-hidden shadow-2xl">
                             <div className="grid grid-cols-[1fr_120px_180px_100px_140px_70px] gap-6 px-10 py-4 border-b border-border/50 text-[10px] font-black uppercase text-muted-foreground tracking-widest bg-muted/20">
                                <div>Actividad</div>
                                <div className="text-center">Etiquetas</div>
                                <div className="text-center">Responsable</div>
                                <div className="text-center">Prioridad</div>
                                <div className="text-right">Vencimiento</div>
                                <div></div>
                             </div>
                             <div className="divide-y divide-border/50">
                                {displayTask.subtasks?.length ? (
                                   displayTask.subtasks.map(st => (
                                     <div key={st.id} className="grid grid-cols-[1fr_120px_180px_100px_140px_70px] gap-6 px-10 py-3 hover:bg-muted/30 transition-all cursor-pointer group text-[13.5px] border-l-2 border-transparent hover:border-primary items-center">
                                        <div className="flex items-center gap-5 text-foreground overflow-hidden">
                                            <div 
                                              className={cn("h-5 w-5 rounded-md border-2 border-border/80 flex items-center justify-center transition-all hover:border-primary cursor-pointer flex-shrink-0", ['completado', 'completo', 'finalizado', 'terminado', 'closed', 'done'].includes(st.status?.toLowerCase() || '') && 'bg-[#2da44e] border-[#2da44e]')}
                                              onClick={(e) => toggleSubtaskStatus(st, e)}
                                            >
                                              {['completado', 'completo', 'finalizado', 'terminado', 'closed', 'done'].includes(st.status?.toLowerCase() || '') && <Check className="h-3 w-3 text-white" />}
                                           </div>
                                           {editingSubtaskId === st.id ? (
                                              <Input 
                                                value={editSubtaskTitle}
                                                onChange={(e) => setEditSubtaskTitle(e.target.value)}
                                                onClick={(e) => e.stopPropagation()}
                                                onKeyDown={async (e) => {
                                                  if (e.key === 'Enter') {
                                                      e.preventDefault();
                                                      try {
                                                          await updateTask(st.id, { title: editSubtaskTitle });
                                                          setEditingSubtaskId(null);
                                                          await refreshTask();
                                                      } catch (error) {
                                                          console.error("Error updating subtask", error);
                                                      }
                                                  } else if (e.key === 'Escape') {
                                                      setEditingSubtaskId(null);
                                                  }
                                                }}
                                                autoFocus
                                                className="h-7 text-[11px] flex-1 min-w-0 font-bold"
                                              />
                                           ) : (
                                              <span className={cn("font-bold tracking-tight truncate", ['completado', 'completo', 'finalizado', 'terminado', 'closed', 'done'].includes(st.status?.toLowerCase() || '') && "line-through text-muted-foreground opacity-50")}>{st.title}</span>
                                           )}
                                        </div>
                                        <div className="flex justify-center items-center" onClick={(e) => e.stopPropagation()}>
                                           <Popover>
                                              <PopoverTrigger asChild>
                                                 <div className="flex flex-wrap gap-1 items-center justify-center cursor-pointer min-h-[30px] w-full hover:bg-muted/30 rounded-xl p-1 transition-all border border-border/20">
                                                    {st.tags?.length ? (
                                                      st.tags.map((t: any) => (
                                                        <span 
                                                          key={t.name} 
                                                          style={{ backgroundColor: t.color || '#3b82f6' }} 
                                                          className="text-[8px] font-extrabold text-white px-1.5 py-0.5 rounded shadow-sm uppercase tracking-tighter"
                                                        >
                                                           {t.name}
                                                        </span>
                                                      ))
                                                    ) : (
                                                      <span className="text-[9px] text-muted-foreground/30 font-black tracking-widest uppercase hover:text-primary transition-colors">+ TAG</span>
                                                    )}
                                                 </div>
                                              </PopoverTrigger>
                                              <PopoverContent className="w-64 bg-popover border-border/80 rounded-2xl p-4 shadow-2xl">
                                                 <ScrollArea className="h-48">
                                                    <div className="space-y-1.5">
                                                       {allTags.map(t => (
                                                         <div 
                                                           key={t.id} 
                                                           className="flex items-center justify-between p-1.5 hover:bg-muted/50 rounded-lg cursor-pointer transition-all border border-transparent" 
                                                           onClick={() => toggleSubtaskTag(st, t.name)}
                                                         >
                                                            <div className="flex items-center gap-2">
                                                               <div className="h-3 w-3 rounded-full" style={{ backgroundColor: t.color || '#3b82f6' }} />
                                                               <span className="text-[11px] font-bold text-foreground">{t.name}</span>
                                                            </div>
                                                            {st.tags?.some((gt: any) => gt.name === t.name) && <Check className="h-4 w-4 text-[#2da44e]" />}
                                                         </div>
                                                       ))}
                                                    </div>
                                                 </ScrollArea>
                                              </PopoverContent>
                                           </Popover>
                                        </div>
                                        <div className="flex justify-center items-center" onClick={(e) => e.stopPropagation()}>
                                           <select
                                             className="bg-transparent border-none text-[11px] font-bold text-muted-foreground hover:text-foreground transition-colors uppercase tracking-tighter cursor-pointer max-w-[150px] focus:ring-0 p-0 text-center"
                                             value={st.assignee_id?.toString() || ''}
                                             onChange={async (e) => {
                                               const val = e.target.value;
                                               const newAssigneeId = val ? parseInt(val) : null;
                                               try {
                                                 await updateTask(st.id, { assignee_id: newAssigneeId });
                                                 await refreshTask();
                                                 if (onTaskUpdate) onTaskUpdate({ ...displayTask });
                                               } catch (err) {
                                                 console.error("Error updating subtask assignee:", err);
                                               }
                                             }}
                                           >
                                             <option value="" className="bg-popover text-foreground">Sin asignar</option>
                                             {users.map(u => (
                                               <option key={u.id} value={u.id.toString()} className="bg-popover text-foreground">
                                                 {u.nombre || u.username}
                                               </option>
                                             ))}
                                           </select>
                                        </div>
                                        <div 
                                           className="flex justify-center items-center cursor-pointer hover:scale-110 active:scale-95 transition-all"
                                           onClick={async (e) => {
                                             e.stopPropagation();
                                             const priorities = ['low', 'normal', 'high', 'urgent'];
                                             const currentIdx = priorities.indexOf(st.priority?.toLowerCase() || 'normal');
                                             const nextPriority = priorities[(currentIdx + 1) % priorities.length];
                                             try {
                                               await updateTask(st.id, { priority: nextPriority });
                                               await refreshTask();
                                               if (onTaskUpdate) onTaskUpdate({ ...displayTask });
                                             } catch (err) {
                                               console.error("Error updating subtask priority:", err);
                                             }
                                           }}
                                        >
                                           <Flag className={cn(
                                             "h-5 w-5 transition-all",
                                             st.priority === 'urgent' && 'text-purple-500 fill-purple-500',
                                             st.priority === 'high' && 'text-red-500 fill-red-500',
                                             st.priority === 'normal' && 'text-blue-500 fill-blue-500',
                                             (st.priority === 'low' || !st.priority) && 'text-muted-foreground/30'
                                           )} />
                                        </div>
                                        <div className="flex justify-end items-center" onClick={(e) => e.stopPropagation()}>
                                           <input 
                                             type="date"
                                             className="bg-transparent border-none text-right text-[11px] font-bold text-primary tracking-tighter uppercase focus:ring-0 p-0 cursor-pointer w-[125px]"
                                             value={st.due_date ? format(parseISO(st.due_date.toString()), 'yyyy-MM-dd') : ''}
                                             onChange={async (e) => {
                                               try {
                                                 const newDate = e.target.value ? new Date(e.target.value).toISOString() : null;
                                                 await updateTask(st.id, { due_date: newDate });
                                                 await refreshTask();
                                                 if (onTaskUpdate) onTaskUpdate({ ...displayTask });
                                               } catch (err) {
                                                 console.error("Error updating subtask due date:", err);
                                               }
                                             }}
                                           />
                                         </div>
                                         <div className="flex items-center justify-end gap-1 transition-opacity">
                                           <button
                                             onClick={(e) => {
                                              e.stopPropagation();
                                              setEditingSubtaskId(st.id);
                                              setEditSubtaskTitle(st.title);
                                            }}
                                            className="p-1 hover:bg-primary/20 text-muted-foreground hover:text-primary rounded transition-all duration-200"
                                          >
                                            <Edit3 className="h-3.5 w-3.5" />
                                          </button>
                                          <button
                                            onClick={async (e) => {
                                              e.stopPropagation();
                                              if (window.confirm("¿Estás seguro de eliminar esta gestión?")) {
                                                try {
                                                  await deleteTask(st.id);
                                                  await refreshTask();
                                                } catch (error) {
                                                  console.error("Error al eliminar gestión", error);
                                                }
                                              }
                                            }}
                                            className="p-1 hover:bg-destructive/20 text-muted-foreground hover:text-destructive rounded transition-all duration-200"
                                          >
                                            <Trash2 className="h-3.5 w-3.5" />
                                          </button>
                                        </div>
                                     </div>
                                   ))
                                ) : (
                                   <div className="p-12 text-center">
                                      <p className="text-muted-foreground italic font-black text-[12px] tracking-widest uppercase">Sin gestiones sincronizadas</p>
                                   </div>
                                )}
                             </div>
                          </div>
                          
                          {showSubtaskForm && (
                            <div className="p-8 bg-card/20 border border-primary/30 rounded-[2.5rem] space-y-6 shadow-2xl animate-in zoom-in-95 duration-500">
                               <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                                  <div className="lg:col-span-2 space-y-2">
                                     <label className="text-[10px] font-black text-primary uppercase ml-4 tracking-widest">Actividad Técnica</label>
                                     <Input placeholder="Nombre de la gestión..." value={newSubtaskTitle} onChange={(e) => setNewSubtaskTitle(e.target.value)} className="bg-background border-border/50 h-12 rounded-[1.5rem] px-6 text-[14px] font-black text-foreground shadow-inner focus:border-primary/60 transition-all" />
                                  </div>
                                  <div className="space-y-2">
                                     <label className="text-[10px] font-black text-primary uppercase ml-4 tracking-widest">Término</label>
                                     <Input type="date" value={newSubtaskDate} onChange={(e) => setNewSubtaskDate(e.target.value)} className="bg-background border-border/50 h-12 rounded-[1.5rem] px-6 text-[14px] font-black text-foreground shadow-inner focus:border-primary/60 transition-all" />
                                  </div>
                                  <div className="space-y-2">
                                     <label className="text-[10px] font-black text-primary uppercase ml-4 tracking-widest">Prioridad</label>
                                     <Select value={newSubtaskPriority} onValueChange={setNewSubtaskPriority}>
                                        <SelectTrigger className="bg-background border-border/50 h-12 rounded-[1.5rem] px-6 text-[14px] font-black text-foreground shadow-inner border">
                                           <SelectValue placeholder="Normal" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-popover border-border text-popover-foreground rounded-xl">
                                           <SelectItem value="low">Baja</SelectItem>
                                           <SelectItem value="normal">Normal</SelectItem>
                                           <SelectItem value="high">Alta</SelectItem>
                                           <SelectItem value="urgent">Urgente</SelectItem>
                                        </SelectContent>
                                     </Select>
                                  </div>
                               </div>
                               <div className="flex items-center gap-8">
                                  <div className="flex-1 space-y-2">
                                     <label className="text-[10px] font-black text-primary uppercase ml-4 tracking-widest">Abogado Responsable</label>
                                     <Select value={newSubtaskAssigneeId?.toString()} onValueChange={(v) => setNewSubtaskAssigneeId(parseInt(v))}>
                                        <SelectTrigger className="bg-background border-border/50 h-12 rounded-[1.5rem] px-6 text-[14px] font-black text-foreground shadow-inner border">
                                           <SelectValue placeholder="Asignar al equipo..." />
                                        </SelectTrigger>
                                        <SelectContent className="bg-popover border-border text-popover-foreground rounded-xl">
                                           {users.map(u => <SelectItem key={u.id} value={u.id.toString()}>{u.nombre || u.username}</SelectItem>)}
                                        </SelectContent>
                                     </Select>
                                  </div>
                                  <div className="flex items-end gap-4 h-full pt-6">
                                     <Button variant="ghost" onClick={() => setShowSubtaskForm(false)} className="h-12 px-6 rounded-xl text-[11px] font-black uppercase text-muted-foreground hover:text-foreground transition-all">Descartar</Button>
                                     <Button onClick={handleCreateSubtask} className="h-12 px-10 rounded-xl bg-primary text-primary-foreground font-black text-[12px] uppercase tracking-widest shadow-xl shadow-primary/40 hover:scale-105 active:scale-95 transition-all">VINCULAR</Button>
                                  </div>
                               </div>
                            </div>
                          )}
                        </div>
                      )}
                   </div>

                   {/* Checklist */}
                   <div className="space-y-6 pt-4 border-t border-border/50">
                      <div className="flex items-center justify-between group cursor-pointer" onClick={() => setIsChecklistOpen(!isChecklistOpen)}>
                         <div className="flex items-center gap-6">
                            <div className="flex items-center gap-3 text-muted-foreground font-black text-[14px] uppercase tracking-[0.3em]">
                               {isChecklistOpen ? <ChevronUp className="h-6 w-6 text-primary" /> : <ChevronDown className="h-6 w-6 text-primary" />} Lista de Control
                            </div>
                            <div className="flex items-center gap-4 text-[11px] text-muted-foreground font-black tracking-widest bg-card/20 px-6 py-2 rounded-full border border-border/50 shadow-inner">
                               <span>{doneCheck}/{totalCheck} COMPLETADAS</span>
                               <Progress value={progressCheck} className="w-48 h-1.5 bg-muted/30 ring-1 ring-border/20" />
                            </div>
                         </div>
                         <Button variant="ghost" onClick={(e) => { e.stopPropagation(); setIsChecklistOpen(true); }} className="text-primary font-black uppercase text-[9px] tracking-widest hover:bg-primary/10 transition-all">+ AÑADIR ITEM</Button>
                      </div>

                      {isChecklistOpen && (
                        <div className="px-8 space-y-3 animate-in fade-in duration-300">
                           {displayTask.checklists?.map(item => (
                             <div key={item.id} className="flex items-center gap-6 py-3 px-6 hover:bg-muted/20 rounded-2xl transition-all border border-transparent hover:border-border/30 group">
                                <Checkbox 
                                  checked={item.is_completed} 
                                  onCheckedChange={(v) => updateChecklistItem(item.id, { is_completed: !!v }).then(refreshTask)} 
                                  className="h-6 w-6 border-border data-[state=checked]:bg-primary rounded-md" 
                                />
                                <span className={cn("text-[14.5px] flex-1 font-bold tracking-tight", item.is_completed ? "line-through text-muted-foreground italic" : "text-foreground/80")}>
                                  {item.content}
                                </span>
                                <Button variant="ghost" size="icon" onClick={() => deleteChecklistItem(item.id).then(refreshTask)} className="h-8 w-8 text-muted-foreground/30 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all">
                                   <Trash2 className="h-4 w-4" />
                                </Button>
                             </div>
                           ))}
                           <div className="flex items-center gap-6 py-4 px-8 bg-card/10 border border-dashed border-border/50 rounded-2xl group hover:border-primary/40 transition-all mt-4">
                              <Plus className="h-6 w-6 text-muted-foreground/20 group-hover:text-primary" />
                              <Input 
                                 placeholder="Añadir paso técnico rápido..." 
                                 value={newChecklist} 
                                 onChange={(e) => setNewChecklist(e.target.value)} 
                                 onKeyDown={(e) => e.key === 'Enter' && handleAddChecklist()} 
                                 className="bg-transparent border-none p-0 text-[14.5px] font-bold focus:ring-0 text-foreground/40 placeholder:text-muted-foreground/10"
                              />
                           </div>
                        </div>
                      )}
                   </div>
                </div>
             </ScrollArea>
          </div>

          {/* ACTIVITY PANEL (30%) */}
          <div className="flex-1 flex flex-col bg-background border-l border-border/50 shadow-2xl overflow-hidden">
             <div className="h-20 flex items-center justify-between px-8 border-b border-border/50 bg-card/20">
                <div className="flex items-center gap-4">
                   <Activity className="h-5 w-5 text-primary opacity-70" />
                   <span className="text-[12px] font-black uppercase tracking-[0.4em] text-muted-foreground">Historial Judicial</span>
                </div>
                <div className="flex items-center gap-6 text-muted-foreground">
                   <RefreshCw onClick={refreshTask} className={cn("h-5 w-5 hover:text-foreground cursor-pointer transition-all", isLoading && "animate-spin")} title="Sincronizar comentarios" />
                   <Settings className="h-5 w-5 hover:text-foreground cursor-pointer transition-all" />
                </div>
             </div>

             <ScrollArea className="flex-1 px-8 py-8">
                <div className="space-y-10">
                   {displayTask.comments?.map(comment => (
                     <div key={comment.id} className="group relative">
                        <div className="flex items-center gap-4 text-[12px] mb-4">
                           <div className="h-9 w-9 rounded-xl bg-primary/10 flex items-center justify-center text-[14px] font-black text-primary border border-primary/20 shadow-xl group-hover:bg-primary group-hover:text-primary-foreground transition-all">
                              {comment.user_name?.[0] || 'U'}
                           </div>
                           <div className="flex flex-col">
                              <span className="text-foreground font-black uppercase tracking-widest text-[11px]">{(comment.user_name || 'SISTEMA')}</span>
                              <span className="text-muted-foreground text-[10px] font-bold tracking-tighter">{isValid(parseISO(comment.created_at.toString())) ? format(parseISO(comment.created_at.toString()), "d MMM, p", { locale: es }) : ''}</span>
                           </div>
                        </div>
                        
                        <div className="p-7 bg-card/30 border border-border/50 rounded-[2rem] rounded-tl-none text-[15px] font-medium text-foreground/70 leading-relaxed shadow-xl group-hover:bg-card/50 transition-all relative border-l-2 border-l-primary/10 hover:border-l-primary/40">
                           {editingCommentId === comment.id ? (
                             <div className="space-y-4">
                                <Textarea value={editingCommentText} onChange={(e) => setEditingCommentText(e.target.value)} className="bg-background border-primary/40 text-[14px] min-h-[120px] rounded-2xl p-5 shadow-inner text-foreground" />
                                <div className="flex justify-end gap-4">
                                   <Button variant="ghost" onClick={() => setEditingCommentId(null)} className="h-9 px-6 rounded-xl text-[10px] font-black uppercase text-muted-foreground">Descartar</Button>
                                   <Button onClick={() => handleUpdateComment(comment.id)} className="h-9 px-8 rounded-xl bg-primary text-primary-foreground font-black text-[10px] uppercase shadow-lg">ACTUALIZAR</Button>
                               </div>
                             </div>
                           ) : (
                             <>
                               {comment.content}
                               <div className="absolute top-4 right-6 opacity-0 group-hover:opacity-100 transition-all flex gap-3">
                                  <Button variant="ghost" size="icon" onClick={() => { setEditingCommentId(comment.id); setEditingCommentText(comment.content); }} className="h-8 w-8 rounded-xl bg-background/80 flex items-center justify-center hover:text-primary border border-border/50 shadow-xl"><Edit3 className="h-4 w-4" /></Button>
                                  <Button variant="ghost" size="icon" onClick={() => handleDeleteComment(comment.id)} className="h-8 w-8 rounded-xl bg-background/80 flex items-center justify-center hover:text-red-500 border border-border/50 shadow-xl"><Trash2 className="h-4 w-4" /></Button>
                               </div>
                             </>
                           )}
                        </div>
                     </div>
                   ))}
                   {(!displayTask.comments || displayTask.comments.length === 0) && (
                      <div className="p-24 text-center opacity-5">
                         <MessageSquare className="h-20 w-20 mx-auto text-muted-foreground" />
                      </div>
                   )}
                </div>
             </ScrollArea>

             <div className="p-8 bg-background border-t border-border/50">
                <div className="bg-card border border-border/50 rounded-[2.5rem] p-8 space-y-6 shadow-xl focus-within:border-primary/40 transition-all">
                   <Textarea 
                     value={newComment}
                     onChange={(e) => setNewComment(e.target.value)}
                     placeholder={isNote ? "Escribe una nota interna para el equipo..." : "Añade un comentario público..."}
                     className="bg-transparent border-none focus:ring-0 p-0 text-[16px] min-h-[90px] resize-none text-foreground font-medium placeholder:text-muted-foreground/10"
                   />
                   <div className="flex items-center justify-between">
                      <div className="flex items-center gap-6 text-muted-foreground">
                         <label className="cursor-pointer hover:text-foreground transition-all">
                            <AttachmentIcon className="h-5 w-5" />
                            <input type="file" className="hidden" onChange={(e) => toast({ title: "Archivo seleccionado", description: e.target.files?.[0]?.name })} />
                         </label>
                         
                         <Popover>
                            <PopoverTrigger asChild>
                               <Zap className="h-5 w-5 text-purple-600 hover:scale-125 cursor-pointer transition-all" />
                            </PopoverTrigger>
                            <PopoverContent className="w-64 p-4 bg-popover border-border text-popover-foreground rounded-2xl shadow-2xl">
                               <div className="space-y-3">
                                  <div className="text-[9px] font-black uppercase text-muted-foreground tracking-[0.2em]">Comandos Rápidos (Slash)</div>
                                  <div className="grid grid-cols-1 gap-1">
                                     <div className="p-2 hover:bg-muted rounded-lg cursor-pointer text-[12px] font-bold flex items-center gap-3" onClick={() => addEmoji(" /firmar")}>🖋️ Firmar actuación</div>
                                     <div className="p-2 hover:bg-muted rounded-lg cursor-pointer text-[12px] font-bold flex items-center gap-3" onClick={() => addEmoji(" /urgente")}>🚨 Marcar como Urgente</div>
                                     <div className="p-2 hover:bg-muted rounded-lg cursor-pointer text-[12px] font-bold flex items-center gap-3" onClick={() => addEmoji(" /revisar")}>👀 Solicitar revisión</div>
                                  </div>
                               </div>
                            </PopoverContent>
                         </Popover>

                         <Popover>
                            <PopoverTrigger asChild>
                               <Smile className="h-5 w-5 hover:text-foreground cursor-pointer transition-all" />
                            </PopoverTrigger>
                            <PopoverContent className="w-56 p-4 bg-popover border-border text-popover-foreground rounded-2xl shadow-2xl">
                               <div className="grid grid-cols-5 gap-3">
                                  {COMMON_EMOJIS.map(emoji => (
                                    <button 
                                      key={emoji} 
                                      onClick={() => addEmoji(emoji)}
                                      className="text-2xl hover:scale-125 transition-transform p-1 rounded-lg hover:bg-muted"
                                    >
                                       {emoji}
                                    </button>
                                  ))}
                               </div>
                            </PopoverContent>
                         </Popover>

                         <div 
                           onClick={() => setIsNote(!isNote)}
                           className={cn(
                             "flex items-center gap-3 px-4 py-2 rounded-xl cursor-pointer text-[10px] font-black uppercase tracking-widest border transition-all",
                             isNote ? "bg-primary/10 text-primary border-primary/20" : "bg-card/50 text-muted-foreground border-border/50"
                           )}
                         >
                            <MessageCircle className={cn("h-4 w-4", isNote ? "text-primary" : "text-muted-foreground/30")} /> {isNote ? "NOTA INTERNA" : "COMENTARIO"}
                         </div>
                      </div>
                      <Button size="icon" onClick={handleAddComment} disabled={!newComment.trim()} className={cn("h-12 w-12 rounded-2xl shadow-xl transition-all", newComment.trim() ? "bg-primary text-primary-foreground scale-110" : "bg-muted text-muted-foreground opacity-20")}>
                        <Send className="h-6 w-6" />
                      </Button>
                   </div>
                </div>
             </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
