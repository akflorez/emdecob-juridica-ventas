import { useState, useEffect, useRef } from 'react';
import { 
  Sparkles, 
  Bot, 
  BrainCircuit, 
  AlertTriangle, 
  Clock, 
  FileText, 
  ShieldAlert, 
  ShieldCheck, 
  Search, 
  Send, 
  TrendingUp, 
  Zap, 
  CheckCircle2, 
  ChevronRight, 
  HelpCircle, 
  Scale, 
  ArrowUpRight,
  Filter,
  RefreshCw,
  Info,
  Loader2,
  ArrowRight
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { 
  getAIDashboardStats, 
  queryAIProcesses, 
  type AIProcessItem, 
  type AIDashboardStatsResponse 
} from '@/services/api';

export default function TableroIAPage() {
  const { toast } = useToast();
  const resultsRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activePrompt, setActivePrompt] = useState<string | null>(null);
  const [selectedKpi, setSelectedKpi] = useState<string | null>(null);
  const [isAiAnalyzing, setIsAiAnalyzing] = useState(false);
  const [isLoadingInitial, setIsLoadingInitial] = useState(true);
  
  const [stats, setStats] = useState<AIDashboardStatsResponse>({
    total_analyzed: 0,
    inactive_over_6_months: 0,
    high_risk_count: 0,
    upcoming_terms_count: 0,
    ai_summaries_pct: 100,
    summary_text: "Iniciando análisis de Inteligencia Artificial sobre los procesos de tu cartera jurídica..."
  });
  
  const [filteredData, setFilteredData] = useState<AIProcessItem[]>([]);
  const [aiAnalysisSummary, setAiAnalysisSummary] = useState<string | null>(null);

  const QUICK_PROMPTS = [
    {
      icon: Clock,
      label: "¿Cuáles procesos llevan más de seis meses sin movimiento?",
      prompt: "procesos_sin_movimiento"
    },
    {
      icon: ShieldAlert,
      label: "Muéstrame las sentencias y autos relevantes del último periodo",
      prompt: "sentencias_desfavorables"
    },
    {
      icon: AlertTriangle,
      label: "¿Qué procesos requieren atención o impulso urgente?",
      prompt: "atencion_urgente"
    },
    {
      icon: Zap,
      label: "Identificar términos y actuaciones con seguimiento prioritario",
      prompt: "terminos_vencer"
    }
  ];

  // Cargar datos reales al montar
  useEffect(() => {
    loadRealAIData();
  }, []);

  const loadRealAIData = async () => {
    setIsLoadingInitial(true);
    try {
      const [statsRes, queryRes] = await Promise.all([
        getAIDashboardStats(),
        queryAIProcesses("", "")
      ]);
      setStats(statsRes);
      setFilteredData(queryRes.cases || []);
      setAiAnalysisSummary(queryRes.summary || statsRes.summary_text);
    } catch (error: any) {
      console.error("[TableroIA] Error loading AI data:", error);
      toast({
        title: "Error al cargar datos de IA",
        description: error?.message || "No se pudieron obtener las métricas de IA",
        variant: "destructive"
      });
    } finally {
      setIsLoadingInitial(false);
    }
  };

  const handleQuerySelect = async (promptKey: string, label: string) => {
    setActivePrompt(label);
    setIsAiAnalyzing(true);

    try {
      const res = await queryAIProcesses("", promptKey);
      setFilteredData(res.cases || []);
      setAiAnalysisSummary(res.summary);
      toast({
        title: "Análisis IA Completado",
        description: `Se encontraron ${res.count} procesos coincidentes en tu cartera.`,
      });
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } catch (error: any) {
      toast({
        title: "Error en consulta IA",
        description: error?.message || "Error al consultar la IA",
        variant: "destructive"
      });
    } finally {
      setIsAiAnalyzing(false);
    }
  };

  const handleCustomSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    
    setSelectedKpi(null);
    setActivePrompt(searchQuery);
    setIsAiAnalyzing(true);

    try {
      const res = await queryAIProcesses(searchQuery, "");
      setFilteredData(res.cases || []);
      setAiAnalysisSummary(res.summary);
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } catch (error: any) {
      toast({
        title: "Error en búsqueda",
        description: error?.message || "Error al procesar la búsqueda",
        variant: "destructive"
      });
    } finally {
      setIsAiAnalyzing(false);
    }
  };

  const handleResetFilters = async () => {
    setSelectedKpi('todos');
    setActivePrompt(null);
    setSearchQuery('');
    await loadRealAIData();
    toast({
      title: "Filtros restablecidos",
      description: "Mostrando todos los procesos analizados de tu cartera."
    });
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  };

  const handleOpenCaseDetail = (caseId: number) => {
    window.open(`/casos/id/${caseId}`, "_blank");
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* Banner Principal de Inteligencia Artificial */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-slate-900 via-emerald-950 to-slate-900 border border-emerald-500/30 p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl -z-0 pointer-events-none" />
        
        <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="space-y-3 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-400/30 text-emerald-300 text-xs font-bold uppercase tracking-widest">
              <Sparkles className="w-4 h-4 text-emerald-400 animate-pulse" />
              <span>Inteligencia Artificial Jurídica v2.5 • Activa</span>
            </div>
            
            <h1 className="text-3xl md:text-4xl font-extrabold text-white font-serif-juricob tracking-tight">
              Tablero de IA & Analítica Predictiva Judicial
            </h1>
            
            <p className="text-slate-300 text-sm md:text-base leading-relaxed">
              Monitoreo inteligente, resumen automático de actuaciones, clasificación de riesgo y alertas automáticas de vencimiento calculadas en tiempo real sobre tus radicados.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto">
            <Button onClick={handleResetFilters} variant="outline" className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-950/50 bg-slate-900/80 rounded-xl flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4" />
              <span>Restablecer Filtros</span>
            </Button>
          </div>
        </div>
      </div>

      {/* KPI Cards (Métricas Clave de IA Reales e Interactivas) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        
        {/* Card 1: Términos a Vencer */}
        <Card 
          onClick={() => {
            setSelectedKpi('terminos');
            handleQuerySelect('terminos_vencer', 'Términos a Vencer (Próximos 5 días hábiles)');
          }}
          className={`cursor-pointer transition-all duration-200 transform hover:-translate-y-1 hover:shadow-xl ${
            selectedKpi === 'terminos'
              ? 'border-amber-500 ring-2 ring-amber-500/50 bg-amber-500/10'
              : 'border-amber-500/20 bg-card hover:border-amber-500/60'
          }`}
        >
          <CardContent className="p-6 flex flex-col justify-between h-full space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Términos a Vencer</p>
                <h3 className="text-3xl font-extrabold text-amber-500 mt-1">
                  {isLoadingInitial ? "..." : stats.upcoming_terms_count}
                </h3>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 font-medium">⚠️ Próximos 5 días hábiles</p>
              </div>
              <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500 flex-shrink-0">
                <Clock className="w-6 h-6" />
              </div>
            </div>
            <div className="pt-2 border-t border-amber-500/20 flex items-center justify-between text-xs text-amber-600 dark:text-amber-400 font-bold">
              <span>👉 Ver cuáles son</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Riesgo Alto */}
        <Card 
          onClick={() => {
            setSelectedKpi('riesgo');
            handleQuerySelect('atencion_urgente', 'Procesos con Riesgo Alto Procesal');
          }}
          className={`cursor-pointer transition-all duration-200 transform hover:-translate-y-1 hover:shadow-xl ${
            selectedKpi === 'riesgo'
              ? 'border-red-500 ring-2 ring-red-500/50 bg-red-500/10'
              : 'border-red-500/20 bg-card hover:border-red-500/60'
          }`}
        >
          <CardContent className="p-6 flex flex-col justify-between h-full space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Riesgo Alto Procesal</p>
                <h3 className="text-3xl font-extrabold text-red-500 mt-1">
                  {isLoadingInitial ? "..." : stats.high_risk_count}
                </h3>
                <p className="text-xs text-red-500 mt-1 font-medium">🚨 Requieren impulso prioritario</p>
              </div>
              <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-500 flex-shrink-0">
                <ShieldAlert className="w-6 h-6" />
              </div>
            </div>
            <div className="pt-2 border-t border-red-500/20 flex items-center justify-between text-xs text-red-500 font-bold">
              <span>👉 Ver cuáles son</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </CardContent>
        </Card>

        {/* Card 3: Inactivos > 6 Meses */}
        <Card 
          onClick={() => {
            setSelectedKpi('inactivos');
            handleQuerySelect('procesos_sin_movimiento', 'Procesos Inactivos > 6 Meses');
          }}
          className={`cursor-pointer transition-all duration-200 transform hover:-translate-y-1 hover:shadow-xl ${
            selectedKpi === 'inactivos'
              ? 'border-indigo-500 ring-2 ring-indigo-500/50 bg-indigo-500/10'
              : 'border-indigo-500/20 bg-card hover:border-indigo-500/60'
          }`}
        >
          <CardContent className="p-6 flex flex-col justify-between h-full space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Inactivos &gt; 6 Meses</p>
                <h3 className="text-3xl font-extrabold text-indigo-500 mt-1">
                  {isLoadingInitial ? "..." : stats.inactive_over_6_months}
                </h3>
                <p className="text-xs text-indigo-500 mt-1 font-medium">❄️ Sin movimiento en Rama</p>
              </div>
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-500 flex-shrink-0">
                <BrainCircuit className="w-6 h-6" />
              </div>
            </div>
            <div className="pt-2 border-t border-indigo-500/20 flex items-center justify-between text-xs text-indigo-500 font-bold">
              <span>👉 Ver cuáles son</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </CardContent>
        </Card>

        {/* Card 4: Resúmenes Generados / Todos */}
        <Card 
          onClick={() => {
            setSelectedKpi('resumenes');
            handleResetFilters();
          }}
          className={`cursor-pointer transition-all duration-200 transform hover:-translate-y-1 hover:shadow-xl ${
            selectedKpi === 'resumenes'
              ? 'border-emerald-500 ring-2 ring-emerald-500/50 bg-emerald-500/10'
              : 'border-emerald-500/20 bg-card hover:border-emerald-500/60'
          }`}
        >
          <CardContent className="p-6 flex flex-col justify-between h-full space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Resúmenes Generados</p>
                <h3 className="text-3xl font-extrabold text-emerald-500 mt-1">100%</h3>
                <p className="text-xs text-emerald-500 mt-1 font-medium">✨ Síntesis automática por IA</p>
              </div>
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-500 flex-shrink-0">
                <Sparkles className="w-6 h-6" />
              </div>
            </div>
            <div className="pt-2 border-t border-emerald-500/20 flex items-center justify-between text-xs text-emerald-500 font-bold">
              <span>👉 Ver todos ({stats.total_analyzed})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* SECCIÓN DEL ASISTENTE VIRTUAL IA */}
      <Card className="border-emerald-500/30 bg-card shadow-xl overflow-hidden">
        <CardHeader className="bg-slate-900/90 text-white p-6 border-b border-emerald-500/20">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-400">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <CardTitle className="text-xl font-bold flex items-center gap-2">
                <span>Asistente Jurídico Virtual con IA</span>
                <Badge variant="outline" className="border-emerald-400 text-emerald-400 text-[10px]">IA Conectada a Base de Datos</Badge>
              </CardTitle>
              <CardDescription className="text-slate-300 text-xs mt-0.5">
                Haz preguntas en lenguaje natural sobre tus expedientes o selecciona una de las consultas más frecuentes.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-6 space-y-6">
          
          {/* Campo de Consulta en Lenguaje Natural */}
          <form onSubmit={handleCustomSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Escribe tu consulta (Ej: ¿Cuáles procesos tienen riesgo alto o vencimiento esta semana?)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-12 h-13 text-base rounded-2xl border-emerald-500/30 focus:border-emerald-500 bg-background"
              />
            </div>
            <Button type="submit" disabled={isAiAnalyzing} className="h-13 px-6 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-2xl flex items-center gap-2 shadow-lg">
              {isAiAnalyzing ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              <span className="hidden sm:inline">Consultar IA</span>
            </Button>
          </form>

          {/* Chips de Consultas Rápidas */}
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
              <span>Consultas Recomendadas por la IA:</span>
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {QUICK_PROMPTS.map((qp, idx) => {
                const IconComp = qp.icon;
                const isSelected = activePrompt === qp.label;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleQuerySelect(qp.prompt, qp.label)}
                    className={`p-3.5 rounded-2xl border text-left flex items-center justify-between gap-3 transition-all ${
                      isSelected 
                        ? 'bg-emerald-500/15 border-emerald-500 text-emerald-400 font-bold shadow-md' 
                        : 'bg-muted/40 border-border/60 hover:bg-emerald-500/10 hover:border-emerald-500/40 text-foreground'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-500 flex items-center justify-center flex-shrink-0">
                        <IconComp className="w-4 h-4" />
                      </div>
                      <span className="text-xs font-medium">{qp.label}</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </button>
                );
              })}
            </div>
          </div>

          {/* Resumen Ejecutivo del Asistente */}
          {aiAnalysisSummary && (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-900 dark:text-emerald-200 text-sm flex items-start gap-3 animate-in fade-in duration-300">
              <Info className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">
                <div dangerouslySetInnerHTML={{ __html: aiAnalysisSummary.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
              </div>
            </div>
          )}

        </CardContent>
      </Card>

      {/* TABLA Y CARDS DE RESULTADOS ANALIZADOS POR IA */}
      <div ref={resultsRef} className="space-y-4 pt-2">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold font-serif-juricob text-foreground flex items-center gap-2">
            <Scale className="w-6 h-6 text-emerald-500" />
            <span>Procesos Analizados con IA ({filteredData.length})</span>
          </h2>
          {activePrompt && (
            <Badge variant="secondary" className="px-3 py-1 text-xs font-medium">
              Filtro IA: {activePrompt}
            </Badge>
          )}
        </div>

        {isLoadingInitial ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
            <span className="ml-3 text-sm text-muted-foreground">Procesando y analizando expedientes con IA...</span>
          </div>
        ) : filteredData.length === 0 ? (
          <Card className="p-12 text-center border-dashed">
            <BrainCircuit className="w-12 h-12 mx-auto text-muted-foreground/40 mb-3" />
            <p className="text-muted-foreground text-sm font-medium">No se encontraron procesos que coincidan con el criterio seleccionado.</p>
            <Button onClick={handleResetFilters} variant="outline" size="sm" className="mt-4">
              Ver todos los procesos
            </Button>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-5">
            {filteredData.map((item) => (
              <Card key={item.id} className="border-border/80 bg-card hover:border-emerald-500/40 transition-all shadow-md overflow-hidden">
                <CardContent className="p-6 space-y-4">
                  
                  {/* Header del Caso */}
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border/60 pb-4">
                    <div>
                      <div className="flex items-center gap-3 flex-wrap">
                        <span className="text-sm font-extrabold font-mono text-emerald-600 dark:text-emerald-400">
                          {item.radicado}
                        </span>
                        <Badge className={
                          item.nivel_riesgo === 'Alto' ? 'bg-red-500/20 text-red-500 border-red-500/40' :
                          item.nivel_riesgo === 'Medio' ? 'bg-amber-500/20 text-amber-500 border-amber-500/40' :
                          'bg-emerald-500/20 text-emerald-500 border-emerald-500/40'
                        }>
                          Riesgo {item.nivel_riesgo}
                        </Badge>
                        {item.is_sic && (
                          <Badge variant="outline" className="border-blue-500 text-blue-500 text-[10px]">
                            SIC Consumidor
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground font-semibold mt-1">
                        {item.juzgado}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className="border-amber-500/40 text-amber-600 dark:text-amber-400 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        <span>Vence en {item.termino_dias_restantes} días</span>
                      </Badge>

                      {item.dias_sin_movimiento >= 180 && (
                        <Badge variant="outline" className="border-indigo-500/40 text-indigo-600 dark:text-indigo-400">
                          ❄️ {item.dias_sin_movimiento} días inactivo
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* Partes del Proceso */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="bg-muted/40 p-3 rounded-xl border border-border/40">
                      <span className="text-muted-foreground font-bold uppercase tracking-wider block mb-1">Demandante:</span>
                      <span className="font-semibold text-foreground">{item.demandante}</span>
                    </div>
                    <div className="bg-muted/40 p-3 rounded-xl border border-border/40">
                      <span className="text-muted-foreground font-bold uppercase tracking-wider block mb-1">Demandado:</span>
                      <span className="font-semibold text-foreground">{item.demandado}</span>
                    </div>
                  </div>

                  {/* Resumen e Indicador IA */}
                  <div className="space-y-3 pt-2">
                    <div className="p-4 rounded-xl bg-slate-900 text-slate-100 space-y-2 border border-emerald-500/20">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                          <Sparkles className="w-4 h-4" /> Resumen de Actuación (IA)
                        </span>
                      </div>
                      <p className="text-xs md:text-sm leading-relaxed text-slate-200">
                        {item.resumen_ia}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-900 dark:text-emerald-300 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Zap className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                        <span><strong>Recomendación IA:</strong> {item.recomendacion_ia}</span>
                      </div>
                      <Button 
                        size="sm" 
                        onClick={() => handleOpenCaseDetail(item.id)}
                        className="bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs h-8 flex-shrink-0"
                      >
                        <span>Ver Expediente</span>
                        <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
                      </Button>
                    </div>
                  </div>

                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* COMPARATIVA DE VALOR DE MERCADO */}
      <Card className="border-emerald-500/30 bg-gradient-to-br from-slate-900 via-slate-950 to-emerald-950 text-white p-8 rounded-3xl shadow-2xl relative overflow-hidden">
        <div className="relative z-10 space-y-4">
          <Badge className="bg-emerald-500 text-slate-950 font-bold uppercase tracking-widest">
            🚀 Ventaja Competitiva Comercial
          </Badge>
          <h3 className="text-2xl font-bold font-serif-juricob">
            Inteligencia Operativa Jurídica Conectada en Vivo
          </h3>
          <p className="text-slate-300 text-sm md:text-base leading-relaxed max-w-4xl">
            Al incorporar Inteligencia Artificial conectada en tiempo real a tu base de datos, Juricob transforma la información judicial en <strong>estrategias operativas concretas</strong>: alertas de riesgo de desistimiento tácito (Art. 317 CGP), control de vencimiento de términos y recomendaciones jurídicas precisas para cada expediente.
          </p>
        </div>
      </Card>

    </div>
  );
}
