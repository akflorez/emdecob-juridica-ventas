import { Calendar as BigCalendar, momentLocalizer } from 'react-big-calendar';
import moment from 'moment';
import 'moment/locale/es';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar as CalendarIcon, Clock, Filter, Plus, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

// Configuración de moment en español
moment.locale('es');
const localizer = momentLocalizer(moment);

import { useState, useEffect } from 'react';
import { getTasks, type Task as TaskType, createTask, updateTask } from '@/services/api';
import { toast } from "sonner";
import { RefreshCw } from 'lucide-react';
import { TaskDrawer } from '@/components/TaskDrawer';

function CustomToolbar(toolbarProps: any) {
  const { label, view, views, onNavigate, onView } = toolbarProps;

  const viewLabels: Record<string, string> = {
    month: 'Mes',
    week: 'Semana',
    day: 'Día',
    agenda: 'Agenda'
  };

  return (
    <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mb-6 pb-4 border-b border-border/50">
      {/* Title */}
      <div className="flex items-center gap-3">
        <div className="bg-primary/10 p-2 rounded-lg text-primary border border-primary/10 hidden sm:block">
          <CalendarIcon className="h-5 w-5" />
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground capitalize">
          {label}
        </h2>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {/* Navigation buttons */}
        <div className="flex items-center bg-muted/40 p-1 rounded-lg border border-border/60 shadow-sm">
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80 rounded"
            onClick={() => onNavigate('PREV')}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button 
            variant="ghost" 
            size="sm" 
            className="h-8 px-3 font-semibold text-xs text-muted-foreground hover:text-foreground hover:bg-background/80 rounded mx-1"
            onClick={() => onNavigate('TODAY')}
          >
            Hoy
          </Button>
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80 rounded"
            onClick={() => onNavigate('NEXT')}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {/* View switching buttons */}
        <div className="flex items-center bg-muted/40 p-1 rounded-lg border border-border/60 shadow-sm">
          {views.map((v: string) => {
            const isActive = view === v;
            return (
              <Button
                key={v}
                variant={isActive ? 'default' : 'ghost'}
                size="sm"
                className={`h-8 px-3 text-xs font-semibold rounded transition-all ${
                  isActive 
                    ? 'shadow-sm bg-background text-foreground hover:bg-background hover:text-foreground font-bold border border-border/50' 
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/30'
                }`}
                onClick={() => onView(v)}
              >
                {viewLabels[v] || v}
              </Button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CustomEvent({ event }: any) {
  return (
    <div className="flex flex-col h-full justify-between py-0.5 px-0.5">
      <span className="font-semibold text-[11px] leading-tight truncate">{event.title}</span>
    </div>
  );
}

export default function AgendaView() {
  const [tasks, setTasks] = useState<TaskType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<TaskType | null>(null);

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    setIsLoading(true);
    try {
      console.log('[AGENDA] Fetching tasks globally...');
      const data = await getTasks({});
      console.log('[AGENDA] Received:', data?.length || 0, 'tasks');
      setTasks(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('[AGENDA] Error:', error);
      toast.error("No se pudo cargar la agenda.");
      setTasks([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTaskUpdate = (t: TaskType) => {
    setTasks(prev => {
      const exists = prev.some(x => x.id === t.id);
      if (exists) return prev.map(x => x.id === t.id ? t : x);
      return [t, ...prev];
    });
    setSelectedTask(t);
    fetchTasks(); // Refrescar para asegurar orden
  };

  const displayTasks = tasks.filter(t => t.parent_id != null);

  const events = displayTasks.map(t => {
    const d = t.due_date ? new Date(t.due_date) : new Date();
    return {
      id: t.id,
      title: (t.parent_id ? '↳ ' : '') + t.title + (!t.due_date ? ' (Sin Fecha)' : ''),
      start: d,
      end: d,
      resource: t.priority,
      task: t
    };
  });

  const todayTasks = displayTasks.filter(t => {
    if (!t.due_date) return false;
    const d = new Date(t.due_date);
    const today = new Date();
    return d.toDateString() === today.toDateString();
  });

  return (
    <div className="flex flex-col h-full space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <CalendarIcon className="h-8 w-8 text-primary" />
            Agenda y Calendario
          </h1>
          <p className="text-muted-foreground">Vista unificada de todas las tareas y vencimientos del equipo.</p>
        </div>
        
        <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={fetchTasks} disabled={isLoading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} /> Actualizar
            </Button>
            <Button size="sm" onClick={() => setSelectedTask({ title: '', status: 'to do', priority: 'normal' } as any)}>
                <Plus className="mr-2 h-4 w-4" /> Programar Tarea
            </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Estadísticas Rápidas */}
        <div className="lg:col-span-1 space-y-5">
            <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/20 shadow-sm">
                <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-2 text-primary">
                        <Clock className="h-3.5 w-3.5" /> Para Hoy
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-3xl font-extrabold tracking-tight">{todayTasks.length} Tareas</div>
                    <p className="text-xs text-muted-foreground mt-1">
                      <span className="font-semibold text-destructive">{todayTasks.filter(t => t.priority === 'urgent' || t.priority === 'high').length} críticas</span> pendientes
                    </p>
                </CardContent>
            </Card>

            <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground px-2">Próximos Vencimientos</h3>
                <div className="space-y-3.5 max-h-[450px] overflow-y-auto custom-scrollbar pr-1">
                    {displayTasks.slice(0, 10).map((t) => {
                        const isUrgent = t.priority === 'urgent' || t.priority === 'high' || t.priority === 'alta';
                        const isNormal = t.priority === 'normal' || t.priority === 'medium' || t.priority === 'media';
                        let priorityBorder = 'border-l-[4px] border-l-blue-500';
                        if (isUrgent) priorityBorder = 'border-l-[4px] border-l-red-500';
                        else if (isNormal) priorityBorder = 'border-l-[4px] border-l-emerald-500';
                        
                        return (
                            <div 
                              key={t.id} 
                              className={`p-3.5 rounded-lg border bg-card hover:bg-muted/30 cursor-pointer shadow-sm hover:shadow transition-all hover:scale-[1.01] duration-200 text-xs ${priorityBorder}`}
                              onClick={() => setSelectedTask(tasks.find(parent => parent.id === t.parent_id) || t)}
                            >
                                <div className="flex justify-between items-start mb-1 gap-2">
                                    <span className="font-bold truncate flex-1 text-foreground/90">{t.title}</span>
                                    <Badge variant="outline" className={`text-[8px] h-4 px-2 uppercase font-extrabold rounded ${
                                      isUrgent ? 'text-red-600 border-red-500/30 bg-red-500/5 dark:text-red-400' : 
                                      isNormal ? 'text-emerald-600 border-emerald-500/30 bg-emerald-500/5 dark:text-emerald-400' : 
                                      'text-blue-600 border-blue-500/30 bg-blue-500/5 dark:text-blue-400'
                                    }`}>
                                      {t.priority || 'Normal'}
                                    </Badge>
                                </div>
                                <p className="text-muted-foreground mt-2 flex items-center gap-1.5 font-medium text-[10px]">
                                  <CalendarIcon className="h-3 w-3 text-muted-foreground/75" />
                                  {t.due_date ? new Date(t.due_date).toLocaleDateString('es-CO', {day: 'numeric', month: 'short'}) : 'Programado para Hoy'}
                                </p>
                            </div>
                        );
                    })}
                    {displayTasks.length === 0 && (
                        <p className="text-xs text-muted-foreground text-center py-6 bg-muted/20 border border-dashed rounded-lg">No hay tareas programadas.</p>
                    )}
                </div>
            </div>
        </div>

        {/* Calendario Principal */}
        <Card className="lg:col-span-3 min-h-[600px] shadow-md border border-border/50 rounded-xl overflow-hidden bg-card/40 backdrop-blur-md">
            <CardContent className="p-0">
                <div className="h-[650px] p-5 text-sm" id="main-calendar">
                    <BigCalendar
                        localizer={localizer}
                        events={events}
                        startAccessor="start"
                        endAccessor="end"
                        messages={{
                            next: "Sig",
                            previous: "Ant",
                            today: "Hoy",
                            month: "Mes",
                            week: "Semana",
                            day: "Día",
                            agenda: "Agenda",
                            date: "Fecha",
                            time: "Hora",
                            event: "Evento"
                        }}
                        components={{
                            toolbar: CustomToolbar,
                            event: CustomEvent
                        }}
                        onSelectEvent={(e: any) => setSelectedTask(tasks.find(parent => parent.id === e.task.parent_id) || e.task)}
                        style={{ height: '100%' }}
                        eventPropGetter={(event) => {
                            const p = event.resource?.toLowerCase();
                            let borderLeft = '3px solid #3b82f6';
                            let backgroundColor = 'rgba(59, 130, 246, 0.08)';
                            let color = '#2563eb';
                            
                            if (p === 'urgent' || p === 'high' || p === 'alta') {
                                borderLeft = '3px solid #ef4444';
                                backgroundColor = 'rgba(239, 68, 68, 0.08)';
                                color = '#dc2626';
                            } else if (p === 'proyectos') {
                                borderLeft = '3px solid #8b5cf6';
                                backgroundColor = 'rgba(139, 92, 246, 0.08)';
                                color = '#7c3aed';
                            } else if (p === 'normal' || p === 'medium' || p === 'media') {
                                borderLeft = '3px solid #10b981';
                                backgroundColor = 'rgba(16, 185, 129, 0.08)';
                                color = '#059669';
                            }
                            
                            return { 
                                style: { 
                                    backgroundColor, 
                                    color, 
                                    borderLeft, 
                                    borderTop: 'none',
                                    borderRight: 'none',
                                    borderBottom: 'none',
                                    borderRadius: '6px',
                                    paddingLeft: '8px',
                                    fontSize: '11px'
                                } 
                            };
                        }}
                    />
                </div>
            </CardContent>
        </Card>
      </div>

      <TaskDrawer 
        task={selectedTask}
        open={!!selectedTask}
        onOpenChange={(open) => !open && setSelectedTask(null)}
        onTaskUpdate={handleTaskUpdate}
      />
    </div>
  );
}
